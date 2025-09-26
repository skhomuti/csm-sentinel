"""Utilities supporting the integration tests."""

import asyncio
import os
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from hexbytes import HexBytes
from web3 import AsyncHTTPProvider, AsyncWeb3, WebSocketProvider
from web3.types import RPCEndpoint, TxParams, TxReceipt

from csm_bot.events import EventMessages
from csm_bot.models import Block, Event
from csm_bot.rpc import Subscription


@dataclass
class AnvilInstance:
    process: asyncio.subprocess.Process
    http_url: str
    ws_url: str


async def wait_for_port(host: str, port: int, timeout: float = 15.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        try:
            reader, writer = await asyncio.open_connection(host, port)
        except OSError:
            if asyncio.get_running_loop().time() >= deadline:
                raise TimeoutError(f"Timed out waiting for {host}:{port}")
            await asyncio.sleep(0.1)
            continue
        writer.close()
        await writer.wait_closed()
        return


def _normalise_fork_url(fork_url: str) -> str:
    if fork_url.startswith("ws://"):
        return "http://" + fork_url[len("ws://") :]
    if fork_url.startswith("wss://"):
        return "https://" + fork_url[len("wss://") :]
    return fork_url


async def start_anvil(fork_block: int, port: int, fork_url: str) -> AnvilInstance:
    if not fork_url:
        raise RuntimeError("WEB3_SOCKET_PROVIDER must be configured for integration tests")

    fork_source = _normalise_fork_url(fork_url)
    cmd = [
        "anvil",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--fork-url",
        fork_source,
        "--fork-block-number",
        str(fork_block)
    ]
    process = await asyncio.create_subprocess_exec(*cmd)
    try:
        await wait_for_port("127.0.0.1", port)
    except Exception:
        process.terminate()
        raise
    return AnvilInstance(process=process, http_url=f"http://127.0.0.1:{port}", ws_url=f"ws://127.0.0.1:{port}")


async def stop_anvil(instance: AnvilInstance) -> None:
    instance.process.terminate()
    try:
        await asyncio.wait_for(instance.process.wait(), timeout=5.0)
    except asyncio.TimeoutError:  # pragma: no cover - defensive cleanup
        instance.process.kill()
        await instance.process.wait()


async def build_subscription(ws_url: str) -> "EventReplayHarness":
    persistent_w3 = AsyncWeb3(WebSocketProvider(ws_url, max_connection_retries=-1))
    w3 = AsyncWeb3(WebSocketProvider(ws_url, max_connection_retries=-1))
    return EventReplayHarness(persistent_w3, w3)


class EventReplayHarness(Subscription):
    """Minimal replay helper mirroring subscription entrypoints."""

    message: str = None

    def __init__(self, persistent_w3: AsyncWeb3, w3: AsyncWeb3) -> None:
        super().__init__(persistent_w3)
        self.event_messages = EventMessages(w3)
        self.processed_events: list[tuple[Event, str]] = []

    async def process_event_log(self, event: Event):
        event.tx = HexBytes("0xdeadbeef")
        self.processed_events.append((event, await self.event_messages.get_event_message(event)))

    async def process_new_block(self, block: Block):
        pass

    async def disconnect(self) -> None:
        provider = self._w3.provider
        if provider is None:
            return
        with suppress(Exception):
            await provider.disconnect()


def _build_web3(provider_url: str) -> AsyncWeb3:
    if provider_url.startswith("ws://") or provider_url.startswith("wss://"):
        provider = WebSocketProvider(provider_url, max_connection_retries=-1)
    else:
        provider = AsyncHTTPProvider(provider_url)
    return AsyncWeb3(provider)


async def replay_transaction_on_anvil(
    *,
    fork_provider_url: str,
    anvil_http_url: str,
    tx_hash: str,
    timeout: float = 120.0,
) -> TxReceipt:
    """Rebroadcast the desired historical transaction on the configured local fork."""

    target_hash = HexBytes(tx_hash)

    fork_w3 = _build_web3(fork_provider_url)
    try:
        provider = fork_w3.provider
        if isinstance(provider, WebSocketProvider) and not await provider.is_connected():
            await provider.connect()
        tx = await fork_w3.eth.get_transaction(target_hash)
    finally:
        provider = fork_w3.provider
        if isinstance(provider, WebSocketProvider):
            await provider.disconnect()

    local_w3 = AsyncWeb3(AsyncHTTPProvider(anvil_http_url))

    from_address = tx["from"]
    await local_w3.provider.make_request(RPCEndpoint("anvil_impersonateAccount"), [from_address])
    try:
        params = _build_replay_tx_params(tx)
        submitted_tx_hash = await local_w3.eth.send_transaction(params)
        receipt = await local_w3.eth.wait_for_transaction_receipt(submitted_tx_hash, timeout=timeout)
    finally:
        with suppress(Exception):
            await local_w3.provider.make_request(RPCEndpoint("anvil_stopImpersonatingAccount"), [from_address])

    return receipt


def _build_replay_tx_params(tx) -> TxParams[str, Any]:
    params: TxParams[str, Any] = {
        "from": tx["from"],
        "to": tx["to"],
        "value": tx["value"],
        "data": tx["input"],
        "gas": tx["gas"],
        "nonce": tx["nonce"],
    }

    chain_id = tx.get("chainId")
    if chain_id is not None:
        params["chainId"] = chain_id

    tx_type = tx.get("type")
    if tx_type is not None:
        params["type"] = hex(tx_type) if isinstance(tx_type, int) else tx_type

    max_fee = tx.get("maxFeePerGas")
    if max_fee is not None:
        params["maxFeePerGas"] = max_fee

    max_priority_fee = tx.get("maxPriorityFeePerGas")
    if max_priority_fee is not None:
        params["maxPriorityFeePerGas"] = max_priority_fee

    gas_price = tx.get("gasPrice")
    if tx_type in (None, 0, "0x0", 1, "0x1") and gas_price is not None:
        params["gasPrice"] = gas_price

    access_list = tx.get("accessList")
    if access_list:
        params["accessList"] = access_list

    return params
