import asyncio
from collections.abc import Awaitable, Callable

import pytest_asyncio

from csm_bot.config import get_config_async

from .helpers import AnvilInstance, start_anvil, stop_anvil


@pytest_asyncio.fixture
async def anvil_launcher(unused_tcp_port_factory) -> Callable[[int], Awaitable[AnvilInstance]]:
    instances: list[AnvilInstance] = []
    cfg = await get_config_async()
    fork_url = cfg.web3_socket_provider

    async def _launch(fork_block: int) -> AnvilInstance:
        port = unused_tcp_port_factory()
        instance = await start_anvil(fork_block, port, fork_url)
        instances.append(instance)
        return instance

    yield _launch

    await asyncio.gather(*(stop_anvil(instance) for instance in instances), return_exceptions=True)
