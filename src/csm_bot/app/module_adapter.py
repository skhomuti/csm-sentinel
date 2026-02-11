from dataclasses import dataclass
from collections.abc import Awaitable, Callable
from typing import Any, Protocol, TYPE_CHECKING

from web3 import AsyncWeb3

from csm_bot.app.contracts import ContractAddresses, discover_contract_addresses, _build_web3
from csm_bot.models import (
    ACCOUNTING_ABI,
    MODULE_ABI,
    EXIT_PENALTIES_ABI,
    FEE_DISTRIBUTOR_ABI,
    LIDO_LOCATOR_ABI,
    PARAMETERS_REGISTRY_ABI,
    STAKING_ROUTER_ABI,
    VEBO_ABI,
)
from csm_bot.module_types import ModuleType
from csm_bot.texts import EVENT_DESCRIPTIONS, build_event_list_text

if TYPE_CHECKING:
    from csm_bot.config import Config
    from csm_bot.events import EventMessages, NotificationPlan
    from csm_bot.models import Event

EventHandler = Callable[["EventMessages", "Event"], Awaitable["NotificationPlan | str | None"]]


@dataclass(frozen=True, slots=True)
class ModuleContracts:
    module: Any
    accounting: Any
    parameters_registry: Any
    fee_distributor: Any
    exit_penalties: Any
    lido_locator: Any
    staking_router: Any
    vebo: Any


class ModuleAdapter(Protocol):
    module_type: ModuleType
    addresses: ContractAddresses
    contracts: ModuleContracts
    module_ui_url: str | None

    def allowed_events(self) -> set[str]:
        ...

    def build_event_list_text(self) -> str:
        ...

    def get_event_handler(self, event_name: str) -> EventHandler | None:
        ...

    async def event_enricher(
        self,
        event: "Event",
        messages: "EventMessages",
    ) -> "NotificationPlan | str | None":
        ...


class BaseModuleAdapter:
    def __init__(
        self,
        *,
        module_type: ModuleType,
        addresses: ContractAddresses,
        contracts: ModuleContracts,
        module_ui_url: str | None,
        event_handlers: dict[str, EventHandler] | None = None,
    ) -> None:
        self.module_type = module_type
        self.addresses = addresses
        self.contracts = contracts
        self.module_ui_url = module_ui_url
        self._event_handlers = event_handlers or {}

    def allowed_events(self) -> set[str]:
        return set(EVENT_DESCRIPTIONS.keys())

    def build_event_list_text(self) -> str:
        return build_event_list_text(self.allowed_events(), self.module_ui_url)

    def get_event_handler(self, event_name: str) -> EventHandler | None:
        return self._event_handlers.get(event_name)

    async def event_enricher(
        self,
        event: "Event",
        messages: "EventMessages",
    ) -> "NotificationPlan | str | None":
        handler = self.get_event_handler(event.event)
        if handler is None:
            return None
        return await handler(messages, event)


class CommunityModuleAdapter(BaseModuleAdapter):
    def __init__(
        self,
        *,
        addresses: ContractAddresses,
        contracts: ModuleContracts,
        module_ui_url: str | None,
    ) -> None:
        if addresses.module_type != ModuleType.COMMUNITY:
            raise RuntimeError(
                f"Expected community module, got {addresses.module_type!s}"
            )
        super().__init__(
            module_type=ModuleType.COMMUNITY,
            addresses=addresses,
            contracts=contracts,
            module_ui_url=module_ui_url,
        )


class CuratedModuleAdapter(BaseModuleAdapter):
    def __init__(
        self,
        *,
        addresses: ContractAddresses,
        contracts: ModuleContracts,
        module_ui_url: str | None,
    ) -> None:
        raise RuntimeError("Curated module adapter is not implemented yet.")


def build_module_contracts(w3: AsyncWeb3, addresses: ContractAddresses) -> ModuleContracts:
    return ModuleContracts(
        module=w3.eth.contract(address=addresses.module, abi=MODULE_ABI, decode_tuples=True),
        accounting=w3.eth.contract(
            address=addresses.accounting,
            abi=ACCOUNTING_ABI,
            decode_tuples=True,
        ),
        parameters_registry=w3.eth.contract(
            address=addresses.parameters_registry,
            abi=PARAMETERS_REGISTRY_ABI,
            decode_tuples=True,
        ),
        fee_distributor=w3.eth.contract(
            address=addresses.fee_distributor,
            abi=FEE_DISTRIBUTOR_ABI,
        ),
        exit_penalties=w3.eth.contract(
            address=addresses.exit_penalties,
            abi=EXIT_PENALTIES_ABI,
        ),
        lido_locator=w3.eth.contract(
            address=addresses.lido_locator,
            abi=LIDO_LOCATOR_ABI,
        ),
        staking_router=w3.eth.contract(
            address=addresses.staking_router,
            abi=STAKING_ROUTER_ABI,
        ),
        vebo=w3.eth.contract(
            address=addresses.vebo,
            abi=VEBO_ABI,
        ),
    )


def build_module_adapter_from_addresses(
    addresses: ContractAddresses,
    w3: AsyncWeb3,
    module_ui_url: str | None,
) -> ModuleAdapter:
    contracts = build_module_contracts(w3, addresses)
    if addresses.module_type == ModuleType.COMMUNITY:
        return CommunityModuleAdapter(
            addresses=addresses,
            contracts=contracts,
            module_ui_url=module_ui_url,
        )
    if addresses.module_type == ModuleType.CURATED:
        return CuratedModuleAdapter(
            addresses=addresses,
            contracts=contracts,
            module_ui_url=module_ui_url,
        )
    raise RuntimeError(f"Unsupported module type: {addresses.module_type!s}")


def build_module_adapter_from_config(cfg: "Config", w3: AsyncWeb3) -> ModuleAdapter:
    addresses = ContractAddresses(
        module=cfg.module_address,
        accounting=cfg.accounting_address,
        parameters_registry=cfg.parameters_registry_address,
        fee_distributor=cfg.fee_distributor_address,
        exit_penalties=cfg.exit_penalties_address,
        lido_locator=cfg.lido_locator_address,
        staking_router=cfg.staking_router_address,
        vebo=cfg.vebo_address,
        staking_module_id=cfg.staking_module_id,
        module_type=cfg.module_type,
    )
    return build_module_adapter_from_addresses(addresses, w3, cfg.module_ui_url)


async def build_module_adapter(
    provider_url: str,
    module_address: str,
    module_ui_url: str | None = None,
    w3: AsyncWeb3 | None = None,
) -> ModuleAdapter:
    if w3 is None:
        w3 = await _build_web3(provider_url)
    addresses = await discover_contract_addresses(w3, module_address)
    return build_module_adapter_from_addresses(addresses, w3, module_ui_url)
