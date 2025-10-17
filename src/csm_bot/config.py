import asyncio
import logging
import os
from dataclasses import dataclass

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
    csm_address: str
    accounting_address: str
    parameters_registry_address: str
    vebo_address: str
    fee_distributor_address: str
    exit_penalties_address: str
    lido_locator_address: str
    staking_router_address: str
    csm_staking_module_id: int

    # URLs
    etherscan_url: str | None
    beaconchain_url: str | None
    csm_ui_url: str | None

    # Other
    block_batch_size: int
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
    csm_address = os.getenv("CSM_ADDRESS")

    if not web3_socket_provider:
        raise RuntimeError("WEB3_SOCKET_PROVIDER must be configured")
    if not csm_address:
        raise RuntimeError("CSM_ADDRESS must be configured")

    try:
        addresses = await asyncio.wait_for(
            _discover_contract_addresses(web3_socket_provider, csm_address),
            timeout=RPC_DISCOVERY_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as exc:
        raise RuntimeError("Timed out discovering contract addresses from WEB3 provider") from exc

    return Config(
        filestorage_path=filestorage_path,
        token=token,
        web3_socket_provider=web3_socket_provider,
        csm_address=addresses.csm,
        accounting_address=addresses.accounting,
        parameters_registry_address=addresses.parameters_registry,
        vebo_address=addresses.vebo,
        fee_distributor_address=addresses.fee_distributor,
        exit_penalties_address=addresses.exit_penalties,
        lido_locator_address=addresses.lido_locator,
        staking_router_address=addresses.staking_router,
        csm_staking_module_id=addresses.csm_staking_module_id,
        etherscan_url=os.getenv("ETHERSCAN_URL"),
        beaconchain_url=os.getenv("BEACONCHAIN_URL"),
        csm_ui_url=os.getenv("CSM_UI_URL"),
        block_batch_size=int(os.getenv("BLOCK_BATCH_SIZE", 10_000)),
        block_from=(int(os.getenv("BLOCK_FROM")) if os.getenv("BLOCK_FROM") else None),
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


async def _discover_contract_addresses(provider_url: str, csm_address: str):
    from csm_bot.app.contracts import discover_contract_addresses_from_url

    return await discover_contract_addresses_from_url(provider_url, csm_address)
