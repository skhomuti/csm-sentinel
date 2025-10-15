import asyncio
import logging
import os

import signal
from asyncio import BaseEventLoop

import web3.exceptions
from web3 import AsyncWeb3, WebSocketProvider
from eth_utils import event_abi_to_log_topic, get_all_event_abis
from web3.utils.subscriptions import (
    NewHeadsSubscription,
    LogsSubscription, NewHeadsSubscriptionContext, LogsSubscriptionContext,
)
from web3._utils.events import get_event_data
from web3.types import EventData, FilterParams
from websockets import ConnectionClosed

from csm_bot.events import EVENTS_TO_FOLLOW
from csm_bot.utils import normalize_block_number
from csm_bot.config import get_config
from csm_bot.models import (
    Event,
    Block,
    CSM_ABI,
    VEBO_ABI,
    FEE_DISTRIBUTOR_ABI,
    EXIT_PENALTIES_ABI,
    ACCOUNTING_ABI,
)

logger = logging.getLogger(__name__)
logging.getLogger("web3.providers.persistent.subscription_manager").setLevel(logging.WARNING)


def topics_to_follow(*abis) -> dict:
    topics = {}
    for event in [event for abi in abis for event in get_all_event_abis(abi)]:
        if event["name"] in EVENTS_TO_FOLLOW.keys():
            topics[event_abi_to_log_topic(event)] = event
    return topics


class Subscription:
    def __init__(self, w3: AsyncWeb3):
        super().__init__()
        self._shutdown_event = asyncio.Event()
        self._w3 = w3
        self.abi_by_topics = topics_to_follow(
            CSM_ABI,
            ACCOUNTING_ABI,
            FEE_DISTRIBUTOR_ABI,
            VEBO_ABI,
            EXIT_PENALTIES_ABI,
        )
        self.cfg = get_config()

    @property
    async def w3(self):
        if not await self._w3.provider.is_connected():
            await self._w3.provider.connect()
            logger.info("Web3 provider connected")
        yield self._w3

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

    @staticmethod
    def _filter_vebo_exit_requests(event: Event):
        cfg = get_config()
        return cfg.csm_staking_module_id is not None and event.args["stakingModuleId"] == cfg.csm_staking_module_id

    @reconnect
    async def subscribe(self):
        if self._shutdown_event.is_set():
            return
        async for w3 in self.w3:
            vebo = w3.eth.contract(address=self.cfg.vebo_address, abi=VEBO_ABI)
            fee_distributor = w3.eth.contract(address=self.cfg.fee_distributor_address, abi=FEE_DISTRIBUTOR_ABI)

            subs_csm = LogsSubscription(
                address=self.cfg.csm_address,
                handler=self._handle_event_log_subscription
            )
            subs_acc = LogsSubscription(
                address=self.cfg.accounting_address,
                handler=self._handle_event_log_subscription
            )
            subs_vebo = LogsSubscription(
                address=self.cfg.vebo_address,
                topics=[vebo.events.ValidatorExitRequest().topic],
                handler=self._handle_event_log_subscription,
                handler_context={"predicate": self._filter_vebo_exit_requests}
            )
            subs_fd = LogsSubscription(
                address=self.cfg.fee_distributor_address,
                topics=[fee_distributor.events.DistributionLogUpdated().topic],
                handler=self._handle_event_log_subscription
            )
            subs_ep = LogsSubscription(
                address=self.cfg.exit_penalties_address,
                handler=self._handle_event_log_subscription,
            )

            subs_heads = NewHeadsSubscription(handler=self._handle_new_block_subscription)
            await w3.subscription_manager.subscribe([subs_csm, subs_acc, subs_vebo, subs_fd, subs_ep, subs_heads])
            logger.info("Subscriptions started")

            await w3.subscription_manager.handle_subscriptions()

            if self._shutdown_event.is_set():
                break


    async def process_blocks_from(self, start_block: int, end_block: int | None = None):
        w3 = await anext(self.w3)
        end_block = end_block or await w3.eth.get_block_number()
        if start_block == end_block:
            logger.info("No blocks to process")
            return
        logger.info("Processing blocks from %s to %s", start_block, end_block)
        batch_size = self.cfg.block_batch_size
        for batch_start in range(start_block, end_block + 1, batch_size):
            batch_end = min(batch_start + batch_size - 1, end_block)
            contracts = [
                self.cfg.csm_address,
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
                    if contract == self.cfg.vebo_address and not self._filter_vebo_exit_requests(event):
                        continue
                    await self.process_event_log(event)
                    await asyncio.sleep(0)
            if self._shutdown_event.is_set():
                break
            await self.process_new_block(Block(number=batch_end))
            logger.debug("Processed blocks up to %s", batch_end)


    async def _handle_new_block_subscription(self, context: NewHeadsSubscriptionContext):
        num = context.result["number"]
        await self.process_new_block(Block(number=normalize_block_number(num)))

    async def _handle_event_log_subscription(self, context: LogsSubscriptionContext):
        event_topic = context.result["topics"][0]
        event_abi = self.abi_by_topics.get(event_topic)
        if not event_abi:
            return
        event_data: EventData = get_event_data(self._w3.codec, event_abi, context.result)

        event = Event(event=event_data["event"],
                      args=event_data["args"],
                      block=event_data["blockNumber"],
                      tx=event_data["transactionHash"],
                      address=event_data["address"])
        if hasattr(context, "predicate") and not context.predicate(event):
            return
        await self.process_event_log(event)

    async def process_event_log(self, event: Event):
        raise NotImplementedError

    async def process_new_block(self, block: Block):
        raise NotImplementedError


class TerminalSubscription(Subscription):
    async def process_event_log(self, event: Event):
        logger.warning(f"Event %s emitted with data: %s", event.event, event.args)

    async def process_new_block(self, block):
        logger.warning(f"Current block number: %s", block.number)


if __name__ == '__main__':
    provider = AsyncWeb3(WebSocketProvider(os.getenv("WEB3_SOCKET_PROVIDER")))

    asyncio.run(TerminalSubscription(provider).subscribe())
