import logging
import json
from dataclasses import dataclass

from web3 import WebSocketProvider, AsyncWeb3, AsyncHTTPProvider

from csm_bot.models import CSM_ABI, LIDO_LOCATOR_ABI, STAKING_ROUTER_ABI

logger = logging.getLogger(__name__)

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


@dataclass(frozen=True, slots=True)
class ContractAddresses:
    csm: str
    accounting: str
    parameters_registry: str
    fee_distributor: str
    exit_penalties: str
    lido_locator: str
    staking_router: str
    vebo: str
    csm_staking_module_id: int

    def as_dict(self) -> dict[str, str | int]:
        return {
            "csm": self.csm,
            "accounting": self.accounting,
            "parameters_registry": self.parameters_registry,
            "fee_distributor": self.fee_distributor,
            "exit_penalties": self.exit_penalties,
            "lido_locator": self.lido_locator,
            "staking_router": self.staking_router,
            "vebo": self.vebo,
            "csm_staking_module_id": self.csm_staking_module_id,
        }


async def discover_contract_addresses(w3: AsyncWeb3, csm_address: str) -> ContractAddresses:
    """Asynchronously discover dependent contract addresses using the provided provider."""

    if not await w3.is_connected():
        await w3.provider.connect()

    checksum = w3.to_checksum_address
    csm = w3.eth.contract(address=checksum(csm_address), abi=CSM_ABI, decode_tuples=True)

    accounting = await csm.functions.ACCOUNTING().call()
    parameters_registry = await csm.functions.PARAMETERS_REGISTRY().call()
    fee_distributor = await csm.functions.FEE_DISTRIBUTOR().call()
    exit_penalties = await csm.functions.EXIT_PENALTIES().call()
    lido_locator = await csm.functions.LIDO_LOCATOR().call()

    locator = w3.eth.contract(address=checksum(_ensure_address(lido_locator, "LIDO_LOCATOR")), abi=LIDO_LOCATOR_ABI)
    vebo = await locator.functions.validatorsExitBusOracle().call()
    staking_router = await locator.functions.stakingRouter().call()

    staking_router_contract = w3.eth.contract(
        address=checksum(_ensure_address(staking_router, "stakingRouter")),
        abi=STAKING_ROUTER_ABI,
    )
    modules = await staking_router_contract.functions.getStakingModules().call()

    module_id = _find_staking_module_id(modules, checksum(csm_address))

    addresses = ContractAddresses(
        csm=checksum(_ensure_address(csm_address, "CSM_ADDRESS")),
        accounting=checksum(_ensure_address(accounting, "ACCOUNTING()")),
        parameters_registry=checksum(_ensure_address(parameters_registry, "PARAMETERS_REGISTRY()")),
        fee_distributor=checksum(_ensure_address(fee_distributor, "FEE_DISTRIBUTOR()")),
        exit_penalties=checksum(_ensure_address(exit_penalties, "EXIT_PENALTIES()")),
        lido_locator=checksum(_ensure_address(lido_locator, "LIDO_LOCATOR()")),
        staking_router=checksum(_ensure_address(staking_router, "stakingRouter()")),
        vebo=checksum(_ensure_address(vebo, "validatorsExitBusOracle()")),
        csm_staking_module_id=module_id,
    )

    _log_discovered_addresses(addresses)
    return addresses


async def discover_contract_addresses_from_url(provider_url: str, csm_address: str) -> ContractAddresses:
    w3 = await _build_web3(provider_url)
    return await discover_contract_addresses(w3, csm_address)


def _ensure_address(raw_address: str, source: str) -> str:
    if not raw_address or raw_address == ZERO_ADDRESS:
        raise RuntimeError(f"Failed to discover address from {source}")
    return raw_address


def _find_staking_module_id(modules: list[tuple], csm_address: str) -> int:
    for module in modules:
        # getStakingModules returns tuple entries with well known layout
        module_id, module_address = module[0], module[1]
        if module_address.lower() == csm_address.lower():
            return int(module_id)
    raise RuntimeError("Failed to resolve CSM staking module ID from staking router modules")


def _log_discovered_addresses(addresses: ContractAddresses) -> None:
    printable = json.dumps(addresses.as_dict(), indent=2, sort_keys=True)
    logger.info("Discovered contract addresses:\n%s", printable)


async def _build_web3(provider_url: str) -> AsyncWeb3:
    if provider_url.startswith(("ws://", "wss://")):
        provider = WebSocketProvider(provider_url, max_connection_retries=-1)
    else:
        provider = AsyncHTTPProvider(provider_url)
    return AsyncWeb3(provider)
