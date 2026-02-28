import asyncio

import pytest

from csm_bot.config import clear_config, get_config_async
from csm_bot.module_types import ModuleType


@pytest.mark.asyncio
async def test_get_config_async_retries_when_rpc_times_out(monkeypatch, fake_contract_addresses):
    clear_config()

    monkeypatch.setenv("WEB3_SOCKET_PROVIDER", "wss://example.invalid/ws")
    monkeypatch.setenv("MODULE_ADDRESS", "0x0000000000000000000000000000000000000001")

    attempts = 0
    async def fake_discover_contract_addresses(provider_url: str, module_address: str):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise asyncio.TimeoutError
        return fake_contract_addresses(module_address)

    monkeypatch.setattr(
        "csm_bot.config._discover_contract_addresses",
        fake_discover_contract_addresses,
    )
    monkeypatch.setattr("csm_bot.config.RPC_DISCOVERY_RETRY_DELAY_SECONDS", 0)

    cfg = await get_config_async()

    assert attempts == 2
    assert cfg.module_address == "0x0000000000000000000000000000000000000001"
    clear_config()


@pytest.mark.asyncio
async def test_get_config_async_prefers_module_envs(monkeypatch, stub_discover_contract_addresses):
    clear_config()

    monkeypatch.setenv("WEB3_SOCKET_PROVIDER", "wss://example.invalid/ws")
    monkeypatch.setenv("MODULE_ADDRESS", "0x0000000000000000000000000000000000000001")
    monkeypatch.setenv("CSM_ADDRESS", "0x0000000000000000000000000000000000000002")
    monkeypatch.setenv("MODULE_UI_URL", "https://module.example")
    monkeypatch.setenv("CSM_UI_URL", "https://legacy.example")

    cfg = await get_config_async()

    assert cfg.module_address == "0x0000000000000000000000000000000000000001"
    assert cfg.module_ui_url == "https://module.example"
    assert cfg.module_type == ModuleType.COMMUNITY
    clear_config()


@pytest.mark.asyncio
async def test_get_config_async_falls_back_to_csm_ui(monkeypatch, stub_discover_contract_addresses):
    clear_config()

    monkeypatch.setenv("WEB3_SOCKET_PROVIDER", "wss://example.invalid/ws")
    monkeypatch.setenv("MODULE_ADDRESS", "0x0000000000000000000000000000000000000001")
    monkeypatch.setenv("CSM_UI_URL", "https://legacy.example")
    monkeypatch.delenv("MODULE_UI_URL", raising=False)

    cfg = await get_config_async()

    assert cfg.module_ui_url == "https://legacy.example"
    clear_config()
