import asyncio
import datetime
import logging
import os

import aiohttp
from eth_utils import humanize_wei
from web3 import AsyncWeb3
from async_lru import alru_cache

from csm_bot.models import (
    Event,
    ETHERSCAN_BLOCK_URL_TEMPLATE,
    BEACONCHAIN_URL_TEMPLATE,
    ETHERSCAN_TX_URL_TEMPLATE,
    ACCOUNTING_ABI,
    EventFilter,
    EventHandler,
    CSM_ABI,
    ACCOUNTING_V2_ABI,
    CSM_V2_ABI,
    PARAMETERS_REGISTRY_ABI,
)
from csm_bot.texts import EVENT_MESSAGES, EVENT_MESSAGE_FOOTER, EVENT_MESSAGE_FOOTER_TX_ONLY, EVENT_EMITS

# This is a dictionary that will be populated with the events to follow
EVENTS_TO_FOLLOW: dict[str, EventHandler] = {}

logger = logging.getLogger(__name__)

class ConnectOnDemand:
    connected_clients = 0

    def __init__(self, provider: AsyncWeb3):
        self._provider = provider
        self._lock = asyncio.Lock()

    async def __aenter__(self):
        async with self._lock:
            self.connected_clients += 1
            if not await self._provider.provider.is_connected():
                await self._provider.provider.connect()
            return self._provider

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        async with self._lock:
            self.connected_clients -= 1
            if await self._provider.provider.is_connected() and self.connected_clients == 0:
                await self._provider.provider.disconnect()


def _format_date(date: datetime.datetime):
    return date.strftime("%a %d %b %Y, %I:%M%p UTC")


class IPFSDistributionFilter(EventFilter):
    """Filter that checks if node operator exists in IPFS distribution data."""
    
    async def should_notify(self, event, node_operator_id: int, event_messages) -> bool:
        """Check if node operator ID exists in the IPFS distribution data."""
        try:
            distribution_log = await self._fetch_distribution_log(event.args.get("logCid"))
        except Exception as e:
            logger.warning("Failed to fetch IPFS distribution data for event %s: %s",
                         event.event, e)
            return False
        
        # Check if node operator ID exists in the operators list
        operators = distribution_log.get("operators", {})
        return str(node_operator_id) in operators

    @alru_cache(maxsize=3)
    async def _fetch_distribution_log(self, log_cid: str):
        """Fetch distribution data from IPFS using logCid."""
        ipfs_url = f"https://ipfs.io/ipfs/{log_cid}"
        
        # Use timeout to prevent hanging requests
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(ipfs_url) as response:
                if response.status != 200:
                    raise aiohttp.ClientError(f"HTTP {response.status} when fetching {ipfs_url}")
                return await response.json()
    

class RegisterEvent:
    def __init__(self, event_name, event_filter: EventFilter = None):
        self.event_name = event_name
        self.event_filter = event_filter

    def __call__(self, func):
        EVENTS_TO_FOLLOW[self.event_name] = EventHandler(self.event_name, func, self.event_filter)
        return func


class EventMessages:
    def __init__(self, w3: AsyncWeb3):
        self.connectProvider = ConnectOnDemand(w3)
        self.w3 = w3

        self.csm_v1 = self.w3.eth.contract(address=os.getenv("CSM_ADDRESS"), abi=CSM_ABI, decode_tuples=True)
        self.csm_v2 = self.w3.eth.contract(address=os.getenv("CSM_ADDRESS"), abi=CSM_V2_ABI, decode_tuples=True)

        self.accounting_v1 = self.w3.eth.contract(address=os.getenv("ACCOUNTING_ADDRESS"), abi=ACCOUNTING_ABI, decode_tuples=True)
        self.accounting_v2 = self.w3.eth.contract(address=os.getenv("ACCOUNTING_ADDRESS"), abi=ACCOUNTING_V2_ABI, decode_tuples=True)

        self.parametersRegistry = self.w3.eth.contract(address=os.getenv("PARAMETERS_REGISTRY_ADDRESS"), abi=PARAMETERS_REGISTRY_ABI, decode_tuples=True)

    async def is_v2(self, block_identifier: int | None = None):
        try:
            version = await self.csm_v2.functions.getInitializedVersion().call(
                block_identifier=block_identifier
            )
            return version == 2
        except Exception as e:
            print(f"Error checking CSM version: {e}. Defaulting to CSM_V1 ABI.")
            return False

    async def default(self, event: Event):
        return EVENT_EMITS.format(event.event, event.args)

    async def get_event_message(self, event: Event):
        event_handler = EVENTS_TO_FOLLOW.get(event.event)
        if event_handler is not None:
            handler = event_handler.handler
        else:
            handler = self.default
        async with self.connectProvider:
            return await handler(self, event)

    @staticmethod
    def footer(event: Event):
        tx_link = ETHERSCAN_TX_URL_TEMPLATE.format("0x" + event.tx.hex())
        if 'nodeOperatorId' not in event.args:
            return EVENT_MESSAGE_FOOTER_TX_ONLY(tx_link).as_markdown()
        return EVENT_MESSAGE_FOOTER(event.args['nodeOperatorId'], tx_link).as_markdown()

    async def should_notify_node_operator(self, event: Event, node_operator_id: int) -> bool:
        """Check if a node operator should be notified for this event based on any registered filters."""
        event_filter: EventFilter = EVENTS_TO_FOLLOW.get(event.event).filter
        if event_filter:
            try:
                async with self.connectProvider:
                    return await event_filter.should_notify(event, node_operator_id, self)
            except Exception as e:
                logger.warning("Failed to apply filter for event %s and node operator %s: %s",
                             event.event, node_operator_id, e)
                # If we can't determine, don't send notification to be safe
                return False
        # No filter registered, allow notification
        return True

    @RegisterEvent('DepositedSigningKeysCountChanged')
    async def deposited_signing_keys_count_changed(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        return template(event.args['depositedKeysCount']) + self.footer(event)

    @RegisterEvent('ELRewardsStealingPenaltyCancelled')
    async def el_rewards_stealing_penalty_cancelled(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        remaining_amount = humanize_wei(await self.accounting_v2.functions.getActualLockedBond(event.args['nodeOperatorId']).call())
        return template(remaining_amount) + self.footer(event)

    @RegisterEvent('ELRewardsStealingPenaltyReported')
    async def el_rewards_stealing_penalty_reported(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        block_hash = self.w3.to_hex(event.args['proposedBlockHash'])
        block_link = ETHERSCAN_BLOCK_URL_TEMPLATE.format(block_hash)
        return template(humanize_wei(event.args['stolenAmount']), block_link) + self.footer(event)

    @RegisterEvent('ELRewardsStealingPenaltySettled')
    async def el_rewards_stealing_penalty_settled(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        logs = await self.accounting_v2.events.BondBurned().get_logs(from_block=event.block)
        burnt_event = next(filter(lambda x: x.args['nodeOperatorId'] == event.args['nodeOperatorId'], logs), None)
        if burnt_event:
            amount = burnt_event.args["burnedAmount"]
        else:
            amount = 0
        return template(humanize_wei(amount)) + self.footer(event)

    @RegisterEvent('InitialSlashingSubmitted')
    async def initial_slashing_submitted(self, event: Event):
        if await self.is_v2(event.block):
            return None
        template: callable = EVENT_MESSAGES.get(event.event)
        key = self.w3.to_hex(await self.csm_v1.functions.getSigningKeys(event.args["nodeOperatorId"], event.args['keyIndex'], 1).call())
        key_url = BEACONCHAIN_URL_TEMPLATE.format(key)
        return template(key, key_url) + self.footer(event)

    @RegisterEvent('KeyRemovalChargeApplied')
    async def key_removal_charge_applied(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        if await self.is_v2(event.block):
            curve_id = await self.accounting_v2.functions.getBondCurveId(
                event.args['nodeOperatorId']
            ).call(block_identifier=event.block)
            amount = await self.parametersRegistry.functions.getKeyRemovalCharge(curve_id).call(
                block_identifier=event.block
            )
        else:
            amount = await self.csm_v1.functions.keyRemovalCharge().call(block_identifier=event.block)
        return template(humanize_wei(amount)) + self.footer(event)

    @RegisterEvent('NodeOperatorManagerAddressChangeProposed')
    async def node_operator_manager_address_change_proposed(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        return template(event.args['newProposedAddress']) + self.footer(event)

    @RegisterEvent('NodeOperatorManagerAddressChanged')
    async def node_operator_manager_address_changed(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        return template(event.args['newAddress']) + self.footer(event)

    @RegisterEvent('NodeOperatorRewardAddressChangeProposed')
    async def node_operator_reward_address_change_proposed(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        return template(event.args['newProposedAddress']) + self.footer(event)

    @RegisterEvent('NodeOperatorRewardAddressChanged')
    async def node_operator_reward_address_changed(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        return template(event.args['newAddress']) + self.footer(event)

    @RegisterEvent('StuckSigningKeysCountChanged')
    async def stuck_signing_keys_count_changed(self, event: Event):
        if await self.is_v2(event.block):
            return None
        template: callable = EVENT_MESSAGES.get(event.event)
        return template(event.args['stuckKeysCount']) + self.footer(event)

    @RegisterEvent('VettedSigningKeysCountDecreased')
    async def vetted_signing_keys_count_decreased(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        return template() + self.footer(event)

    @RegisterEvent('WithdrawalSubmitted')
    async def withdrawal_submitted(self, event: Event):
        # TODO add exit penalties applied
        if await self.is_v2(event.block):
            csm = self.csm_v2
        else:
            csm = self.csm_v1
        template: callable = EVENT_MESSAGES.get(event.event)
        key = self.w3.to_hex(await csm.functions.getSigningKeys(event.args["nodeOperatorId"], event.args['keyIndex'], 1).call())
        key_url = BEACONCHAIN_URL_TEMPLATE.format(key)
        return template(key, key_url, humanize_wei(event.args['amount'])) + self.footer(event)

    @RegisterEvent('TotalSigningKeysCountChanged')
    async def total_signing_keys_count_changed(self, event: Event):
        if await self.is_v2(event.block):
            csm = self.csm_v2
        else:
            csm = self.csm_v1

        template: callable = EVENT_MESSAGES.get(event.event)
        node_operator = await csm.functions.getNodeOperator(event.args["nodeOperatorId"]).call(block_identifier=event.block - 1)
        return template(event.args['totalKeysCount'], node_operator.totalAddedKeys) + self.footer(event)

    @RegisterEvent('ValidatorExitRequest')
    async def validator_exit_request(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        key = self.w3.to_hex(event.args['validatorPubkey'])
        key_url = BEACONCHAIN_URL_TEMPLATE.format(key)
        request_date = datetime.datetime.fromtimestamp(event.args['timestamp'], datetime.UTC)
        exit_until = request_date + datetime.timedelta(days=4)
        return template(key, key_url, _format_date(request_date), _format_date(exit_until)) + self.footer(event)

    @RegisterEvent('PublicRelease')
    async def public_release(self, event: Event):
        if await self.is_v2(event.block):
            return None
        template: callable = EVENT_MESSAGES.get(event.event)
        return template() + self.footer(event)

    @RegisterEvent("DistributionLogUpdated", IPFSDistributionFilter())
    async def distribution_data_updated(self, event: Event):
        # TODO add StrikesDataUpdated
        template: callable = EVENT_MESSAGES.get(event.event)
        return template() + self.footer(event)

    @RegisterEvent("TargetValidatorsCountChanged")
    async def target_validators_count_changed(self, event: Event):
        if await self.is_v2(event.block):
            csm = self.csm_v2
        else:
            csm = self.csm_v1

        node_operator = await csm.functions.getNodeOperator(event.args["nodeOperatorId"]).call(
            block_identifier=event.block - 1)
        mode_before = node_operator.targetLimitMode
        limit_before = node_operator.targetLimit

        template: callable = EVENT_MESSAGES.get(event.event)
        return template(mode_before, limit_before, event.args['targetLimitMode'], event.args['targetValidatorsCount']) + self.footer(event)

    @RegisterEvent("Initialized")
    async def initialized(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        if event.args['version'] != 2:
            return None
        if event.address != os.getenv("CSM_ADDRESS"):
            return None
        return template() + self.footer(event)
