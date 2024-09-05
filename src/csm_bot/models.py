import dataclasses
import json
import os

from hexbytes import HexBytes


CSM_ABI = json.load(open("abi/CSModule.json"))
ACCOUNTING_ABI = json.load(open("abi/CSAccounting.json"))
VEBO_ABI = json.load(open("abi/VEBO.json"))

ETHERSCAN_BLOCK_URL_TEMPLATE = os.getenv("ETHERSCAN_URL") + "/block/{}"
ETHERSCAN_TX_URL_TEMPLATE = os.getenv("ETHERSCAN_URL") + "/tx/{}"
BEACONCHAIN_URL_TEMPLATE = os.getenv("BEACONCHAIN_URL") + "/validator/{}"


@dataclasses.dataclass
class Block:
    number: int


@dataclasses.dataclass
class Event:
    event: str
    args: dict
    block: int
    tx: HexBytes
