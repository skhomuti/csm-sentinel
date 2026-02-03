import pytest

from csm_bot.app.contracts import ContractAddresses
from csm_bot.app import module_adapter as adapter
from csm_bot.module_types import ModuleType


def _dummy_addresses(module_type: ModuleType) -> ContractAddresses:
    return ContractAddresses(
        module="0x0000000000000000000000000000000000000001",
        accounting="0x0000000000000000000000000000000000000002",
        parameters_registry="0x0000000000000000000000000000000000000003",
        fee_distributor="0x0000000000000000000000000000000000000004",
        exit_penalties="0x0000000000000000000000000000000000000005",
        lido_locator="0x0000000000000000000000000000000000000006",
        staking_router="0x0000000000000000000000000000000000000007",
        vebo="0x0000000000000000000000000000000000000008",
        staking_module_id=1,
        module_type=module_type,
    )


def _dummy_contracts() -> adapter.ModuleContracts:
    return adapter.ModuleContracts(
        module=object(),
        accounting=object(),
        parameters_registry=object(),
        fee_distributor=object(),
        exit_penalties=object(),
        lido_locator=object(),
        staking_router=object(),
        vebo=object(),
    )


def test_community_module_adapter_instantiation():
    addresses = _dummy_addresses(ModuleType.COMMUNITY)
    contracts = _dummy_contracts()
    result = adapter.CommunityModuleAdapter(
        addresses=addresses,
        contracts=contracts,
        module_ui_url=None,
    )
    assert result.module_type == ModuleType.COMMUNITY


def test_curated_module_adapter_instantiation():
    addresses = _dummy_addresses(ModuleType.CURATED)
    contracts = _dummy_contracts()
    with pytest.raises(RuntimeError, match="Curated module adapter is not implemented"):
        adapter.CuratedModuleAdapter(
            addresses=addresses,
            contracts=contracts,
            module_ui_url=None,
        )


def test_adapter_build_event_list_text_filters_allowed_events():
    class LimitedAdapter(adapter.BaseModuleAdapter):
        def allowed_events(self) -> set[str]:
            return {"Initialized"}

    addresses = _dummy_addresses(ModuleType.COMMUNITY)
    contracts = _dummy_contracts()
    limited = LimitedAdapter(
        module_type=ModuleType.COMMUNITY,
        addresses=addresses,
        contracts=contracts,
        module_ui_url="https://example.invalid",
    )

    text = limited.build_event_list_text()
    assert "CSM v2 launched on mainnet" in text
    assert "Keys were deposited" not in text
