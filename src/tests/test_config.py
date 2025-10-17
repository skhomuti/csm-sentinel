import asyncio

import pytest

from csm_bot.config import clear_config, get_config_async


@pytest.mark.asyncio
async def test_get_config_async_fails_when_rpc_times_out(monkeypatch):
    clear_config()

    monkeypatch.setenv("WEB3_SOCKET_PROVIDER", "wss://example.invalid/ws")
    monkeypatch.setenv("CSM_ADDRESS", "0x0000000000000000000000000000000000000001")

    async def fake_discover_contract_addresses(provider_url: str, csm_address: str):
        raise asyncio.TimeoutError

    monkeypatch.setattr(
        "csm_bot.config._discover_contract_addresses",
        fake_discover_contract_addresses,
    )

    with pytest.raises(RuntimeError, match="Timed out"):
        await get_config_async()
