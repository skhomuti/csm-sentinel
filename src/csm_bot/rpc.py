import asyncio
import os

from web3 import AsyncWeb3, WebSocketProvider
from eth_utils import event_abi_to_log_topic, get_all_event_abis
from web3._utils.events import get_event_data
from web3.types import EventData
from websockets import ConnectionClosedError

from csm_bot.events import CSM_EVENTS_TO_FOLLOW
from csm_bot.models import Event, Block, CSM_ABI


async def csm_topics_to_follow(csm_abi) -> dict:
    topics = {}
    for event in get_all_event_abis(csm_abi):
        if event["name"] in CSM_EVENTS_TO_FOLLOW.keys():
            topics[event_abi_to_log_topic(event)] = event
    return topics


class Subscription:
    def __init__(self, provider: AsyncWeb3):
        self.provider = provider

    async def subscribe(self):
        abi_by_topics = await csm_topics_to_follow(CSM_ABI)
        filter_params = {
            "address": os.getenv("CSM_ADDRESS"),
        }
        async for w3 in self.provider:
            print("Web3 provider connected")
            subscription_id_logs = await w3.eth.subscribe("logs", filter_params)
            subscription_id_heads = await w3.eth.subscribe("newHeads")
            print("Subscription ids:", subscription_id_logs, subscription_id_heads)

            try:
                async for payload in w3.socket.process_subscriptions():
                    subscription_id = payload["subscription"]
                    result = payload["result"]
                    if subscription_id == subscription_id_logs:
                        event_topic = result["topics"][0]
                        event_abi = abi_by_topics.get(event_topic)
                        if not event_abi:
                            continue
                        event_data: EventData = get_event_data(w3.codec, event_abi, result)
                        await self.process_event_log(Event(event=event_data["event"],
                                                           args=event_data["args"],
                                                           block=event_data["blockNumber"],
                                                           tx=event_data["transactionHash"]))
                    elif subscription_id == subscription_id_heads:
                        await self.process_new_block(Block(number=result["number"]))
            except ConnectionClosedError as e:
                print("Web3 provider disconnected...", e)
                continue

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
