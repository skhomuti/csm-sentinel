"""Shared pytest configuration for the test suite."""

from pathlib import Path

from dotenv import load_dotenv
import pytest

from csm_bot.app.contracts import ContractAddresses
from csm_bot.module_types import ModuleType

# Load local environment variables before tests run.
env_file = Path(".env")
if env_file.exists():
    load_dotenv(env_file, override=False)


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: mark tests that require a locally forked Anvil node",
    )


@pytest.fixture
def fake_contract_addresses():
    def _make(module_address: str = "0x0000000000000000000000000000000000000001"):
        return ContractAddresses(
            module=module_address,
            accounting="0x0000000000000000000000000000000000000002",
            parameters_registry="0x0000000000000000000000000000000000000003",
            fee_distributor="0x0000000000000000000000000000000000000004",
            exit_penalties="0x0000000000000000000000000000000000000005",
            lido_locator="0x0000000000000000000000000000000000000006",
            staking_router="0x0000000000000000000000000000000000000007",
            vebo="0x0000000000000000000000000000000000000008",
            staking_module_id=3,
            module_type=ModuleType.COMMUNITY,
        )

    return _make


@pytest.fixture
def stub_discover_contract_addresses(monkeypatch, fake_contract_addresses):
    async def _fake_discover(provider_url: str, module_address: str):
        return fake_contract_addresses(module_address)

    monkeypatch.setattr(
        "csm_bot.config._discover_contract_addresses",
        _fake_discover,
    )
    return _fake_discover
