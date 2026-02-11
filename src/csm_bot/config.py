import asyncio
import logging
import os
from dataclasses import dataclass

from eth_typing import ChecksumAddress

from csm_bot.module_types import ModuleType

logger = logging.getLogger(__name__)


def _parse_admin_ids(raw: str) -> set[int]:
    ids: set[int] = set()
    for token in raw.replace(" ", ",").split(","):
        if not token:
            continue
        try:
            ids.add(int(token))
        except ValueError:
            # Ignore invalid entries silently at config load time
            continue
    return ids


@dataclass(frozen=True)
class Config:
    # Paths and tokens
    filestorage_path: str
    token: str | None
    web3_socket_provider: str

    # Addresses and IDs
    module_address: ChecksumAddress
    accounting_address: ChecksumAddress
    parameters_registry_address: ChecksumAddress
    vebo_address: ChecksumAddress
    fee_distributor_address: ChecksumAddress
    exit_penalties_address: ChecksumAddress
    lido_locator_address: ChecksumAddress
    staking_router_address: ChecksumAddress
    staking_module_id: int
    module_type: ModuleType

    # URLs
    etherscan_url: str | None
    beaconchain_url: str | None
    module_ui_url: str | None

    # Other
    block_batch_size: int
    process_blocks_requests_per_second: float | None
    block_from: int | None
    admin_ids: set[int]

    # Derived URL templates
    @property
    def etherscan_block_url_template(self) -> str | None:
        return None if not self.etherscan_url else f"{self.etherscan_url}/block/{{}}"

    @property
    def etherscan_tx_url_template(self) -> str | None:
        return None if not self.etherscan_url else f"{self.etherscan_url}/tx/{{}}"

    @property
    def beaconchain_url_template(self) -> str | None:
        return None if not self.beaconchain_url else f"{self.beaconchain_url}/validator/{{}}"


_CONFIG: Config | None = None
RPC_DISCOVERY_TIMEOUT_SECONDS = 30


async def _build_config_from_env() -> Config:
    filestorage_path = os.getenv("FILESTORAGE_PATH", ".storage")
    token = os.getenv("TOKEN")
    web3_socket_provider = os.getenv("WEB3_SOCKET_PROVIDER")
    raw_module_address = os.getenv("MODULE_ADDRESS")
    raw_csm_address = os.getenv("CSM_ADDRESS")
    if raw_csm_address:
        logger.warning("CSM_ADDRESS is deprecated; use MODULE_ADDRESS instead.")
    module_address = raw_module_address or raw_csm_address

    if not web3_socket_provider:
        raise RuntimeError("WEB3_SOCKET_PROVIDER must be configured")
    if not module_address:
        raise RuntimeError("MODULE_ADDRESS or CSM_ADDRESS must be configured")

    try:
        addresses = await asyncio.wait_for(
            _discover_contract_addresses(web3_socket_provider, module_address),
            timeout=RPC_DISCOVERY_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as exc:
        raise RuntimeError("Timed out discovering contract addresses from WEB3 provider") from exc

    process_blocks_requests_per_second = os.getenv("PROCESS_BLOCKS_REQUESTS_PER_SECOND")
    if process_blocks_requests_per_second:
        process_blocks_requests_per_second = float(process_blocks_requests_per_second)
        if process_blocks_requests_per_second <= 0:
            raise RuntimeError("PROCESS_BLOCKS_REQUESTS_PER_SECOND must be positive")
    else:
        process_blocks_requests_per_second = None

    raw_module_ui_url = os.getenv("MODULE_UI_URL")
    raw_csm_ui_url = os.getenv("CSM_UI_URL")
    if raw_csm_ui_url:
        logger.warning("CSM_UI_URL is deprecated; use MODULE_UI_URL instead.")
    module_ui_url = raw_module_ui_url or raw_csm_ui_url

    raw_block_from = os.getenv("BLOCK_FROM")
    block_from = int(raw_block_from) if raw_block_from else None

    return Config(
        filestorage_path=filestorage_path,
        token=token,
        web3_socket_provider=web3_socket_provider,
        module_address=addresses.module,
        accounting_address=addresses.accounting,
        parameters_registry_address=addresses.parameters_registry,
        vebo_address=addresses.vebo,
        fee_distributor_address=addresses.fee_distributor,
        exit_penalties_address=addresses.exit_penalties,
        lido_locator_address=addresses.lido_locator,
        staking_router_address=addresses.staking_router,
        staking_module_id=addresses.staking_module_id,
        module_type=addresses.module_type,
        etherscan_url=os.getenv("ETHERSCAN_URL"),
        beaconchain_url=os.getenv("BEACONCHAIN_URL"),
        module_ui_url=module_ui_url,
        block_batch_size=int(os.getenv("BLOCK_BATCH_SIZE", 10_000)),
        process_blocks_requests_per_second=process_blocks_requests_per_second,
        block_from=block_from,
        admin_ids=_parse_admin_ids(os.getenv("ADMIN_IDS", "")),
    )


def get_config() -> Config:
    global _CONFIG
    if _CONFIG is None:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            _CONFIG = asyncio.run(_build_config_from_env())
        else:
            raise RuntimeError("get_config() cannot be called from an async context, use get_config_async() instead")
    return _CONFIG


async def get_config_async() -> Config:
    global _CONFIG
    if _CONFIG is None:
        _CONFIG = await _build_config_from_env()
    return _CONFIG


def set_config(config: Config) -> None:
    global _CONFIG
    _CONFIG = config


def clear_config() -> None:
    """Basically for tests."""
    global _CONFIG
    _CONFIG = None


async def _discover_contract_addresses(provider_url: str, module_address: str):
    from csm_bot.app.contracts import discover_contract_addresses_from_url

    return await discover_contract_addresses_from_url(provider_url, module_address)
