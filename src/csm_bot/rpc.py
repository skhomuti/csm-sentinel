import asyncio
import logging
import os

import signal
from asyncio import BaseEventLoop
from typing import Any, cast

import web3.exceptions
from web3 import AsyncWeb3, WebSocketProvider
from eth_utils import event_abi_to_log_topic, get_all_event_abis
from web3.utils.subscriptions import (
    LogsSubscription,
    LogsSubscriptionContext,
)
from web3._utils.events import get_event_data
from web3.types import EventData, FilterParams
from websockets import ConnectionClosed

from csm_bot.config import Config, get_config
from csm_bot.texts import EVENT_DESCRIPTIONS
from csm_bot.models import (
    Event,
    Block,
    MODULE_ABI,
    VEBO_ABI,
    FEE_DISTRIBUTOR_ABI,
    EXIT_PENALTIES_ABI,
    ACCOUNTING_ABI,
)

logger = logging.getLogger(__name__)
logging.getLogger("web3.providers.persistent.subscription_manager").setLevel(logging.WARNING)


def topics_to_follow(allowed_events: set[str], *abis) -> dict:
    topics = {}
    for event in [event for abi in abis for event in get_all_event_abis(abi)]:
        if event["name"] in allowed_events:
            topics[event_abi_to_log_topic(event)] = event
    return topics


class Subscription:
    def __init__(
        self,
        w3: AsyncWeb3,
        allowed_events: set[str],
        *,
        backfill_w3: AsyncWeb3 | None = None,
    ):
        super().__init__()
        self._shutdown_event = asyncio.Event()
        self._subscriptions_started = asyncio.Event()
        self._w3 = w3
        self._backfill_w3 = backfill_w3 or w3
        self.abi_by_topics = topics_to_follow(
            allowed_events,
            MODULE_ABI,
            ACCOUNTING_ABI,
            FEE_DISTRIBUTOR_ABI,
            VEBO_ABI,
            EXIT_PENALTIES_ABI,
        )
        self.cfg: Config = get_config()
        rps_limit = self.cfg.process_blocks_requests_per_second
        self._process_blocks_request_interval = (1 / rps_limit) if rps_limit else None
        self._last_process_blocks_request_ts: float | None = None

    def start_catchup(self, until_block: int) -> None:
        """Hook for subclasses to prepare for catch-up/backfill mode.

        The base implementation is a no-op.
        """

        _ = until_block

    def finish_catchup(self) -> None:
        """Hook for subclasses to finish catch-up/backfill mode.

        The base implementation is a no-op.
        """

    async def wait_until_subscribed(self, *, timeout: float = 10.0) -> None:
        """Wait until subscriptions are established (or raise on timeout)."""

        await asyncio.wait_for(self._subscriptions_started.wait(), timeout=timeout)

    async def get_block_number(self) -> int:
        """Return the latest block number from the provider."""

        w3 = await anext(self.backfill_w3)
        return await w3.eth.get_block_number()

    @property
    async def w3(self):
        if not await self._w3.provider.is_connected():
            await self._w3.provider.connect()
            logger.info("Web3 provider connected")
        yield self._w3

    @property
    async def backfill_w3(self):
        if not await self._backfill_w3.provider.is_connected():
            await self._backfill_w3.provider.connect()
            logger.info("Web3 backfill provider connected")
        yield self._backfill_w3

    def setup_signal_handlers(self, loop):
        loop.add_signal_handler(signal.SIGINT, self._signal_handler, loop)
        loop.add_signal_handler(signal.SIGTERM, self._signal_handler, loop)

    def _signal_handler(self, loop: BaseEventLoop):
        async def _safe_unsubscribe_all():
            try:
                await self._w3.subscription_manager.unsubscribe_all()
            except ConnectionClosed:
                pass

        logger.info("Signal received, shutting down...")
        loop.create_task(_safe_unsubscribe_all())
        self._shutdown_event.set()

    @staticmethod
    def reconnect(func):
        async def wrapper(self, *args, **kwargs):
            while True:
                try:
                    return await func(self, *args, **kwargs)
                except ConnectionClosed:
                    if self._shutdown_event.is_set():
                        break
                    logger.info("Web3 provider disconnected, reconnecting...")

        return wrapper

    async def shutdown(self):
        await self._shutdown_event.wait()

    def request_shutdown(self) -> None:
        """Trigger shutdown (e.g., from a supervising task)."""

        self._shutdown_event.set()

    @staticmethod
    def _filter_vebo_exit_requests(event: Event):
        cfg = get_config()
        return (
            cfg.staking_module_id is not None
            and event.args["stakingModuleId"] == cfg.staking_module_id
        )

    @reconnect
    async def subscribe(self):
        if self._shutdown_event.is_set():
            return
        async for w3 in self.w3:
            vebo = w3.eth.contract(address=self.cfg.vebo_address, abi=VEBO_ABI)
            fee_distributor = w3.eth.contract(
                address=self.cfg.fee_distributor_address, abi=FEE_DISTRIBUTOR_ABI
            )

            subs_module = LogsSubscription(
                address=self.cfg.module_address, handler=self._handle_event_log_subscription
            )
            subs_acc = LogsSubscription(
                address=self.cfg.accounting_address, handler=self._handle_event_log_subscription
            )
            subs_vebo = LogsSubscription(
                address=self.cfg.vebo_address,
                topics=[vebo.events.ValidatorExitRequest().topic],
                handler=self._handle_event_log_subscription,
                handler_context={"predicate": self._filter_vebo_exit_requests},
            )
            subs_fd = LogsSubscription(
                address=self.cfg.fee_distributor_address,
                topics=[fee_distributor.events.DistributionLogUpdated().topic],
                handler=self._handle_event_log_subscription,
            )
            subs_ep = LogsSubscription(
                address=self.cfg.exit_penalties_address,
                handler=self._handle_event_log_subscription,
            )

            await w3.subscription_manager.subscribe(
                [subs_module, subs_acc, subs_vebo, subs_fd, subs_ep]
            )
            logger.info("Subscriptions started")
            self._subscriptions_started.set()

            await w3.subscription_manager.handle_subscriptions()

            if self._shutdown_event.is_set():
                break

    async def process_blocks_from(self, start_block: int, end_block: int | None = None):
        w3 = await anext(self.backfill_w3)
        end_block = end_block or await w3.eth.get_block_number()
        if start_block >= end_block:
            logger.info("No blocks to process")
            return
        logger.info("Processing blocks from %s to %s", start_block, end_block)
        batch_size = self.cfg.block_batch_size
        for batch_start in range(start_block, end_block + 1, batch_size):
            batch_end = min(batch_start + batch_size - 1, end_block)
            contracts = [
                self.cfg.module_address,
                self.cfg.accounting_address,
                self.cfg.fee_distributor_address,
                self.cfg.vebo_address,
                self.cfg.exit_penalties_address,
            ]

            for contract in contracts:
                logger.info(
                    "Fetching logs for %s blocks %s-%s",
                    contract,
                    batch_start,
                    batch_end,
                )
                filter_params = FilterParams(
                    fromBlock=batch_start,
                    toBlock=batch_end,
                    address=contract,
                )
                await self._throttle_process_blocks_request()
                try:
                    logs = await w3.eth.get_logs(filter_params)
                except web3.exceptions.Web3Exception as e:
                    logger.error("Error fetching logs: %s", e)
                    self._shutdown_event.set()
                    break
                for log in logs:
                    event_topic = log["topics"][0]
                    event_abi = self.abi_by_topics.get(event_topic)
                    if not event_abi:
                        continue
                    event_data: EventData = get_event_data(w3.codec, event_abi, log)
                    event = Event(
                        event=event_data["event"],
                        args=event_data["args"],
                        block=event_data["blockNumber"],
                        tx=event_data["transactionHash"],
                        address=event_data["address"],
                    )
                    if contract == self.cfg.vebo_address and not self._filter_vebo_exit_requests(
                        event
                    ):
                        continue
                    await self.process_event_log(event)
                    await asyncio.sleep(0)
            if self._shutdown_event.is_set():
                break
            await self.process_new_block(Block(number=batch_end))
            logger.debug("Processed blocks up to %s", batch_end)

    async def _throttle_process_blocks_request(self):
        if self._process_blocks_request_interval is None:
            return
        loop = asyncio.get_running_loop()
        now = loop.time()
        if self._last_process_blocks_request_ts is not None:
            elapsed = now - self._last_process_blocks_request_ts
            sleep_for = self._process_blocks_request_interval - elapsed
            if sleep_for > 0:
                logger.debug("Throttling process_blocks_from requests for %.3fs", sleep_for)
                await asyncio.sleep(sleep_for)
                now = loop.time()
        self._last_process_blocks_request_ts = now

    async def _handle_event_log_subscription(self, context: LogsSubscriptionContext):
        # web3 stubs type `context.result` too broadly; treat as a log receipt-like mapping.
        result = cast(dict[str, Any], context.result)
        event_topic = result["topics"][0]
        event_abi = self.abi_by_topics.get(event_topic)
        if not event_abi:
            return
        event_data: EventData = get_event_data(self._w3.codec, event_abi, result)

        event = Event(
            event=event_data["event"],
            args=event_data["args"],
            block=event_data["blockNumber"],
            tx=event_data["transactionHash"],
            address=event_data["address"],
        )
        if hasattr(context, "predicate") and not context.predicate(event):
            return
        await self.process_event_log_from_subscription(event)

    async def process_event_log(self, event: Event):
        raise NotImplementedError

    async def process_new_block(self, block: Block):
        """Called at the end of each backfill batch. No-op by default."""

    async def process_event_log_from_subscription(self, event: Event):
        """Handle a log event received via the live subscription."""

        await self.process_event_log(event)


class TerminalSubscription(Subscription):
    async def process_event_log(self, event: Event):
        logger.warning("Event %s emitted with data: %s", event.event, event.args)

    async def process_new_block(self, block):
        logger.warning("Current block number: %s", block.number)


if __name__ == "__main__":
    provider = AsyncWeb3(WebSocketProvider(os.getenv("WEB3_SOCKET_PROVIDER")))

    allowed_events = set(EVENT_DESCRIPTIONS.keys())
    asyncio.run(TerminalSubscription(provider, allowed_events).subscribe())
