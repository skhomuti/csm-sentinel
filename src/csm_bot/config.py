import os
from dataclasses import dataclass
from functools import lru_cache


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
    web3_socket_provider: str | None

    # Addresses and IDs
    csm_address: str | None
    accounting_address: str | None
    parameters_registry_address: str | None
    vebo_address: str | None
    fee_distributor_address: str | None
    exit_penalties_address: str | None
    csm_staking_module_id: int | None

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


@lru_cache(maxsize=1)
def get_config() -> Config:
    return Config(
        filestorage_path=os.getenv("FILESTORAGE_PATH", ".storage"),
        token=os.getenv("TOKEN"),
        web3_socket_provider=os.getenv("WEB3_SOCKET_PROVIDER"),
        csm_address=os.getenv("CSM_ADDRESS"),
        accounting_address=os.getenv("ACCOUNTING_ADDRESS"),
        parameters_registry_address=os.getenv("PARAMETERS_REGISTRY_ADDRESS"),
        vebo_address=os.getenv("VEBO_ADDRESS"),
        fee_distributor_address=os.getenv("FEE_DISTRIBUTOR_ADDRESS"),
        exit_penalties_address=os.getenv("EXIT_PENALTIES_ADDRESS"),
        csm_staking_module_id=(int(os.getenv("CSM_STAKING_MODULE_ID")) if os.getenv("CSM_STAKING_MODULE_ID") else None),
        etherscan_url=os.getenv("ETHERSCAN_URL"),
        beaconchain_url=os.getenv("BEACONCHAIN_URL"),
        csm_ui_url=os.getenv("CSM_UI_URL"),
        block_batch_size=int(os.getenv("BLOCK_BATCH_SIZE", 10_000)),
        block_from=(int(os.getenv("BLOCK_FROM")) if os.getenv("BLOCK_FROM") else None),
        admin_ids=_parse_admin_ids(os.getenv("ADMIN_IDS", "")),
    )
