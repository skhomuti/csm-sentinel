import logging
import json
from dataclasses import dataclass

from eth_typing import ChecksumAddress
from web3 import WebSocketProvider, AsyncWeb3, AsyncHTTPProvider

from csm_bot.models import MODULE_ABI, LIDO_LOCATOR_ABI, STAKING_ROUTER_ABI
from csm_bot.module_types import ModuleType, decode_module_type

logger = logging.getLogger(__name__)

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


@dataclass(frozen=True, slots=True)
class ContractAddresses:
    module: ChecksumAddress
    accounting: ChecksumAddress
    parameters_registry: ChecksumAddress
    fee_distributor: ChecksumAddress
    exit_penalties: ChecksumAddress
    lido_locator: ChecksumAddress
    staking_router: ChecksumAddress
    vebo: ChecksumAddress
    staking_module_id: int
    module_type: ModuleType

    def as_dict(self) -> dict[str, str | int]:
        return {
            "module": self.module,
            "accounting": self.accounting,
            "parameters_registry": self.parameters_registry,
            "fee_distributor": self.fee_distributor,
            "exit_penalties": self.exit_penalties,
            "lido_locator": self.lido_locator,
            "staking_router": self.staking_router,
            "vebo": self.vebo,
            "staking_module_id": self.staking_module_id,
            "module_type": self.module_type.value,
        }


async def discover_contract_addresses(w3: AsyncWeb3, module_address: str) -> ContractAddresses:
    """Asynchronously discover dependent contract addresses using the provided provider."""

    if not await w3.is_connected():
        await w3.provider.connect()

    checksum = w3.to_checksum_address
    module_contract = w3.eth.contract(address=checksum(module_address), abi=MODULE_ABI, decode_tuples=True)

    module_type_raw = await module_contract.functions.getType().call()
    module_type = decode_module_type(module_type_raw)

    accounting = await module_contract.functions.ACCOUNTING().call()
    parameters_registry = await module_contract.functions.PARAMETERS_REGISTRY().call()
    fee_distributor = await module_contract.functions.FEE_DISTRIBUTOR().call()
    exit_penalties = await module_contract.functions.EXIT_PENALTIES().call()
    lido_locator = await module_contract.functions.LIDO_LOCATOR().call()

    locator = w3.eth.contract(address=checksum(_ensure_address(lido_locator, "LIDO_LOCATOR")), abi=LIDO_LOCATOR_ABI)
    vebo = await locator.functions.validatorsExitBusOracle().call()
    staking_router = await locator.functions.stakingRouter().call()

    staking_router_contract = w3.eth.contract(
        address=checksum(_ensure_address(staking_router, "stakingRouter")),
        abi=STAKING_ROUTER_ABI,
    )
    modules = await staking_router_contract.functions.getStakingModules().call()

    module_id = _find_staking_module_id(modules, checksum(module_address))

    addresses = ContractAddresses(
        module=checksum(_ensure_address(module_address, "MODULE_ADDRESS")),
        accounting=checksum(_ensure_address(accounting, "ACCOUNTING()")),
        parameters_registry=checksum(_ensure_address(parameters_registry, "PARAMETERS_REGISTRY()")),
        fee_distributor=checksum(_ensure_address(fee_distributor, "FEE_DISTRIBUTOR()")),
        exit_penalties=checksum(_ensure_address(exit_penalties, "EXIT_PENALTIES()")),
        lido_locator=checksum(_ensure_address(lido_locator, "LIDO_LOCATOR()")),
        staking_router=checksum(_ensure_address(staking_router, "stakingRouter()")),
        vebo=checksum(_ensure_address(vebo, "validatorsExitBusOracle()")),
        staking_module_id=module_id,
        module_type=module_type,
    )

    _log_discovered_addresses(addresses)
    return addresses


async def discover_contract_addresses_from_url(provider_url: str, module_address: str) -> ContractAddresses:
    w3 = await _build_web3(provider_url)
    return await discover_contract_addresses(w3, module_address)


def _ensure_address(raw_address: str, source: str) -> str:
    if not raw_address or raw_address == ZERO_ADDRESS:
        raise RuntimeError(f"Failed to discover address from {source}")
    return raw_address


def _find_staking_module_id(modules: list[tuple], module_address: str) -> int:
    for module in modules:
        # getStakingModules returns tuple entries with well known layout
        module_id, staking_module_address = module[0], module[1]
        if staking_module_address.lower() == module_address.lower():
            return int(module_id)
    raise RuntimeError("Failed to resolve staking module ID from staking router modules")


def _log_discovered_addresses(addresses: ContractAddresses) -> None:
    printable = json.dumps(addresses.as_dict(), indent=2, sort_keys=True)
    logger.info("Discovered contract addresses:\n%s", printable)


async def _build_web3(provider_url: str) -> AsyncWeb3:
    if provider_url.startswith(("ws://", "wss://")):
        provider = WebSocketProvider(provider_url, max_connection_retries=-1)
    else:
        provider = AsyncHTTPProvider(provider_url)
    return AsyncWeb3(provider)
