import dataclasses
import json

from eth_typing import ChecksumAddress
from hexbytes import HexBytes

MODULE_ABI = json.load(open("abi/CSModuleV2.json"))
ACCOUNTING_ABI = json.load(open("abi/CSAccountingV2.json"))
FEE_DISTRIBUTOR_ABI = json.load(open("abi/CSFeeDistributorV2.json"))
EXIT_PENALTIES_ABI = json.load(open("abi/CSExitPenalties.json"))
PARAMETERS_REGISTRY_ABI = json.load(open("abi/CSParametersRegistry.json"))
VEBO_ABI = json.load(open("abi/VEBO.json"))
LIDO_LOCATOR_ABI = json.load(open("abi/LidoLocator.json"))
STAKING_ROUTER_ABI = json.load(open("abi/StakingRouter.json"))


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

@dataclasses.dataclass
class EventHandler:
    """Dataclass to represent an event handler."""
    event: str
    handler: callable
