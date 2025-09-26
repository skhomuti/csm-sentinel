import asyncio
from collections.abc import Awaitable, Callable

import pytest
import pytest_asyncio

from csm_bot.config import get_config

from .helpers import AnvilInstance, start_anvil, stop_anvil


@pytest_asyncio.fixture
async def anvil_launcher(unused_tcp_port_factory) -> Callable[[int], Awaitable[AnvilInstance]]:
    instances: list[AnvilInstance] = []
    cfg = get_config()
    fork_url = cfg.web3_socket_provider

    async def _launch(fork_block: int) -> AnvilInstance:
        port = unused_tcp_port_factory()
        try:
            instance = await start_anvil(fork_block, port, fork_url)
        except RuntimeError as exc:
            pytest.skip(str(exc))
        except FileNotFoundError as exc:
            pytest.skip(str(exc))
        instances.append(instance)
        return instance

    yield _launch

    await asyncio.gather(*(stop_anvil(instance) for instance in instances), return_exceptions=True)
