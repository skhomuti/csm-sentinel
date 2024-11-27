import asyncio
import datetime
import os

from eth_utils import humanize_wei
from web3 import AsyncWeb3

from csm_bot.models import (
    Event, ETHERSCAN_BLOCK_URL_TEMPLATE, BEACONCHAIN_URL_TEMPLATE, ETHERSCAN_TX_URL_TEMPLATE,
    ACCOUNTING_ABI,
)
from csm_bot.models import CSM_ABI
from csm_bot.texts import EVENT_MESSAGES, EVENT_MESSAGE_FOOTER, EVENT_MESSAGE_FOOTER_TX_ONLY, EVENT_EMITS

# This is a dictionary that will be populated with the events to follow
EVENTS_TO_FOLLOW = {}


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


class RegisterEvent:
    def __init__(self, event_name):
        self.event_name = event_name

    def __call__(self, func):
        EVENTS_TO_FOLLOW[self.event_name] = func
        return func


class EventMessages:
    def __init__(self, w3: AsyncWeb3):
        self.connectProvider = ConnectOnDemand(w3)
        self.w3 = w3
        self.csm = self.w3.eth.contract(address=os.getenv("CSM_ADDRESS"), abi=CSM_ABI, decode_tuples=True)
        self.accounting = self.w3.eth.contract(address=os.getenv("ACCOUNTING_ADDRESS"), abi=ACCOUNTING_ABI, decode_tuples=True)

    async def default(self, event: Event):
        return EVENT_EMITS.format(event.event, event.args)

    async def get_event_message(self, event: Event):
        callback = EVENTS_TO_FOLLOW.get(event.event, self.default)
        async with self.connectProvider:
            return await callback(self, event)

    @staticmethod
    def footer(event: Event):
        tx_link = ETHERSCAN_TX_URL_TEMPLATE.format("0x" + event.tx.hex())
        if 'nodeOperatorId' not in event.args:
            return EVENT_MESSAGE_FOOTER_TX_ONLY(tx_link).as_markdown()
        return EVENT_MESSAGE_FOOTER(event.args['nodeOperatorId'], tx_link).as_markdown()

    @RegisterEvent('DepositedSigningKeysCountChanged')
    async def deposited_signing_keys_count_changed(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        return template(event.args['depositedKeysCount']) + self.footer(event)

    @RegisterEvent('ELRewardsStealingPenaltyCancelled')
    async def el_rewards_stealing_penalty_cancelled(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        remaining_amount = humanize_wei(await self.accounting.functions.getActualLockedBond(event.args['nodeOperatorId']).call())
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
        logs = await self.accounting.events.BondBurned().get_logs(from_block=event.block)
        burnt_event = next(filter(lambda x: x.args['nodeOperatorId'] == event.args['nodeOperatorId'], logs), None)
        if burnt_event:
            amount = burnt_event.args["burnedAmount"]
        else:
            amount = 0
        return template(humanize_wei(amount)) + self.footer(event)

    @RegisterEvent('InitialSlashingSubmitted')
    async def initial_slashing_submitted(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        key = self.w3.to_hex(await self.csm.functions.getSigningKeys(event.args["nodeOperatorId"], event.args['keyIndex'], 1).call())
        key_url = BEACONCHAIN_URL_TEMPLATE.format(key)
        return template(key, key_url) + self.footer(event)

    @RegisterEvent('KeyRemovalChargeApplied')
    async def key_removal_charge_applied(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        amount = await self.csm.functions.keyRemovalCharge().call(block_identifier=event.block)
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
        template: callable = EVENT_MESSAGES.get(event.event)
        return template(event.args['stuckKeysCount']) + self.footer(event)

    @RegisterEvent('VettedSigningKeysCountDecreased')
    async def vetted_signing_keys_count_decreased(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        return template() + self.footer(event)

    @RegisterEvent('WithdrawalSubmitted')
    async def withdrawal_submitted(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        key = self.w3.to_hex(await self.csm.functions.getSigningKeys(event.args["nodeOperatorId"], event.args['keyIndex'], 1).call())
        key_url = BEACONCHAIN_URL_TEMPLATE.format(key)
        return template(key, key_url, humanize_wei(event.args['amount'])) + self.footer(event)

    @RegisterEvent('TotalSigningKeysCountChanged')
    async def total_signing_keys_count_changed(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        node_operator = await self.csm.functions.getNodeOperator(event.args["nodeOperatorId"]).call(block_identifier=event.block - 1)
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
        template: callable = EVENT_MESSAGES.get(event.event)
        return template() + self.footer(event)

    @RegisterEvent("DistributionDataUpdated")
    async def distribution_data_updated(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        return template() + self.footer(event)
