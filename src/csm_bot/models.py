import dataclasses
import json

from eth_typing import ChecksumAddress
from hexbytes import HexBytes

from csm_bot.config import get_config

CFG = get_config()

CSM_ABI = json.load(open("abi/CSModule.json"))
CSM_V2_ABI = json.load(open("abi/CSModuleV2.json"))

ACCOUNTING_ABI = json.load(open("abi/CSAccounting.json"))
ACCOUNTING_V2_ABI = json.load(open("abi/CSAccountingV2.json"))

FEE_DISTRIBUTOR_ABI = json.load(open("abi/CSFeeDistributor.json"))
FEE_DISTRIBUTOR_V2_ABI = json.load(open("abi/CSFeeDistributorV2.json"))

PARAMETERS_REGISTRY_ABI = json.load(open("abi/CSParametersRegistry.json"))
VEBO_ABI = json.load(open("abi/VEBO.json"))

ETHERSCAN_BLOCK_URL_TEMPLATE = CFG.etherscan_block_url_template
ETHERSCAN_TX_URL_TEMPLATE = CFG.etherscan_tx_url_template
BEACONCHAIN_URL_TEMPLATE = CFG.beaconchain_url_template


@dataclasses.dataclass
class Block:
    number: int


@dataclasses.dataclass
class Event:
    event: str
    args: dict
    block: int
    tx: HexBytes
    address: ChecksumAddress

    def readable(self):
        args = ", ".join(f"{key}={value}" for key, value in self.args.items())
        return f"{self.event}({args})"

class EventFilter:
    """Base class for event filters."""
    async def should_notify(self, event, node_operator_id: int, event_messages) -> bool:
        """Return True if the node operator should receive notifications for this event."""
        raise NotImplementedError

    async def finalize(self):
        """Optional cleanup method to be called when the filter is no longer needed."""
        pass

@dataclasses.dataclass
class EventHandler:
    """Dataclass to represent an event handler."""
    event: str
    handler: callable
    filter: EventFilter = None
