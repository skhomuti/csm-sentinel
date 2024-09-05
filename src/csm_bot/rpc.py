import asyncio
import os

import signal
from asyncio import BaseEventLoop

from web3 import AsyncWeb3, WebSocketProvider
from eth_utils import event_abi_to_log_topic, get_all_event_abis
from web3._utils.events import get_event_data
from web3._utils.filters import construct_event_filter_params
from web3.types import EventData
from web3.utils.abi import get_event_abi
from websockets import ConnectionClosedError

from csm_bot.events import EVENTS_TO_FOLLOW
from csm_bot.models import Event, Block, CSM_ABI, VEBO_ABI


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
        self.abi_by_topics = topics_to_follow(CSM_ABI, VEBO_ABI)

    @property
    async def w3(self):
        if not await self._w3.provider.is_connected():
            await self._w3.provider.connect()
            print("Web3 provider connected")
        yield self._w3

    def setup_signal_handlers(self, loop):
        loop.add_signal_handler(signal.SIGINT, self._signal_handler, loop)

    def _signal_handler(self, loop: BaseEventLoop):
        async def _disconnect():
            w3 = await anext(self.w3)
            await w3.provider.disconnect()
        print("Signal received, shutting down...")
        self._shutdown_event.set()
        loop.create_task(_disconnect())

    # add a reconnect decorator
    @staticmethod
    def reconnect(func):
        async def wrapper(self, *args, **kwargs):
            while True:
                try:
                    return await func(self, *args, **kwargs)
                except ConnectionClosedError:
                    if self._shutdown_event.is_set():
                        break
                    print("Web3 provider disconnected, reconnecting...")
        return wrapper

    async def shutdown(self):
        await self._shutdown_event.wait()

    @reconnect
    async def subscribe(self):
        async for w3 in self.w3:
            csm_filter = {
                "address": os.getenv("CSM_ADDRESS"),
            }
            _, vebo_filter = construct_event_filter_params(
                get_event_abi(VEBO_ABI, "ValidatorExitRequest"),
                w3.codec,
                address=os.getenv("VEBO_ADDRESS"),
                argument_filters={"stakingModuleId": int(os.getenv("CSM_STAKING_MODULE_ID"))},
            )

            subscription_id_csm = await w3.eth.subscribe("logs", csm_filter)
            subscription_id_vebo = await w3.eth.subscribe("logs", vebo_filter)
            subscription_id_heads = await w3.eth.subscribe("newHeads")
            print("Subscription ids:", subscription_id_csm, subscription_id_vebo, subscription_id_heads)

            async for payload in w3.socket.process_subscriptions():
                if self._shutdown_event.is_set():
                    break
                subscription_id = payload["subscription"]
                result = payload["result"]
                if subscription_id in (subscription_id_csm, subscription_id_vebo):
                    event_topic = result["topics"][0]
                    event_abi = self.abi_by_topics.get(event_topic)
                    if not event_abi:
                        continue
                    event_data: EventData = get_event_data(w3.codec, event_abi, result)
                    await self.process_event_log(Event(event=event_data["event"],
                                                       args=event_data["args"],
                                                       block=event_data["blockNumber"],
                                                       tx=event_data["transactionHash"]))
                elif subscription_id == subscription_id_heads:
                    await self.process_new_block(Block(number=result["number"]))

    async def process_blocks_from(self, start_block: int):
        w3 = await anext(self.w3)
        current_block = await w3.eth.get_block_number()
        if start_block == current_block:
            print("No blocks to process")
            return
        print(f"Processing blocks from {start_block} to {current_block}")
        filter_params = {
            "fromBlock": start_block,
            "toBlock": current_block,
            "address": os.getenv("CSM_ADDRESS"),
        }
        logs = await w3.eth.get_logs(filter_params)
        for log in logs:
            event_topic = log["topics"][0]
            event_abi = self.abi_by_topics.get(event_topic)
            if not event_abi:
                continue
            event_data: EventData = get_event_data(w3.codec, event_abi, log)
            await self.process_event_log(Event(event=event_data["event"],
                                               args=event_data["args"],
                                               block=event_data["blockNumber"],
                                               tx=event_data["transactionHash"]))
            await asyncio.sleep(0)
        await self.process_new_block(Block(number=current_block))

    async def process_event_log(self, event: Event):
        raise NotImplementedError

    async def process_new_block(self, block: Block):
        raise NotImplementedError


class TerminalSubscription(Subscription):
    async def process_event_log(self, event: Event):
        print(f"Event {event.event} emitted with data: {event.args}")

    async def process_new_block(self, block):
        print(f"Current block number: {block.number}")


if __name__ == '__main__':
    provider = AsyncWeb3(WebSocketProvider(os.getenv("WEB3_SOCKET_PROVIDER")))

    asyncio.run(TerminalSubscription(provider).subscribe())
