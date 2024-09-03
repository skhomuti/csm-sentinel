import os

from eth_utils import humanize_wei
from web3 import AsyncWeb3

from csm_bot.models import (
    Event, ETHERSCAN_BLOCK_URL_TEMPLATE, BEACONCHAIN_URL_TEMPLATE, ETHERSCAN_TX_URL_TEMPLATE,
    ACCOUNTING_ABI,
)
from csm_bot.models import CSM_ABI
from csm_bot.texts import EVENT_MESSAGES, EVENT_MESSAGE_FOOTER, EVENT_MESSAGE_FOOTER_TX_ONLY, EVENT_EMITS


class EventMessages:
    def __init__(self, w3: AsyncWeb3):
        self.w3 = w3
        self.csm = self.w3.eth.contract(address=os.getenv("CSM_ADDRESS"), abi=CSM_ABI)
        self.accounting = self.w3.eth.contract(address=os.getenv("ACCOUNTING_ADDRESS"), abi=ACCOUNTING_ABI)

    async def default(self, event: Event):
        return EVENT_EMITS.format(event.event, event.args)

    async def get_event_message(self, event: Event):
        callback = CSM_EVENTS_TO_FOLLOW.get(event.event, self.default)
        return await callback(self, event)

    @staticmethod
    def footer(event: Event):
        tx_link = ETHERSCAN_TX_URL_TEMPLATE.format(event.tx.hex())
        if 'nodeOperatorId' not in event.args:
            return EVENT_MESSAGE_FOOTER_TX_ONLY(tx_link)
        return EVENT_MESSAGE_FOOTER(event.args['nodeOperatorId'], tx_link).as_markdown()

    async def deposited_signing_keys_count_changed(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        return template(event.args['depositedKeysCount']) + self.footer(event)

    async def el_rewards_stealing_penalty_cancelled(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        remaining_amount = humanize_wei(await self.accounting.functions.getActualLockedBond(event.args['nodeOperatorId']).call())
        return template(remaining_amount) + self.footer(event)

    async def el_rewards_stealing_penalty_reported(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        block_hash = self.w3.to_hex(event.args['proposedBlockHash'])
        block_link = ETHERSCAN_BLOCK_URL_TEMPLATE.format(block_hash)
        return template(humanize_wei(event.args['stolenAmount']), block_link) + self.footer(event)

    async def el_rewards_stealing_penalty_settled(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        logs = await self.accounting.events.BondBurned().get_logs(from_block=event.block)
        burnt_event = next(filter(lambda x: x.args['nodeOperatorId'] == event.args['nodeOperatorId'], logs), None)
        if burnt_event:
            amount = burnt_event.args["burnedAmount"]
        else:
            amount = 0
        return template(humanize_wei(amount)) + self.footer(event)

    async def initial_slashing_submitted(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        key = self.w3.to_hex(await self.csm.functions.getSigningKeys(event.args["nodeOperatorId"], event.args['keyIndex'], 1).call())
        key_url = BEACONCHAIN_URL_TEMPLATE.format(key)
        return template(key, key_url) + self.footer(event)

    async def key_removal_charge_applied(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        amount = await self.csm.functions.keyRemovalCharge().call(block_identifier=event.block)
        return template(humanize_wei(amount)) + self.footer(event)

    async def node_operator_manager_address_change_proposed(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        return template(event.args['newProposedAddress']) + self.footer(event)

    async def node_operator_manager_address_changed(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        return template(event.args['newAddress']) + self.footer(event)

    async def node_operator_reward_address_change_proposed(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        return template(event.args['newProposedAddress']) + self.footer(event)

    async def node_operator_reward_address_changed(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        return template(event.args['newAddress']) + self.footer(event)

    async def stuck_signing_keys_count_changed(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        return template(event.args['stuckKeysCount']) + self.footer(event)

    async def vetted_signing_keys_count_decreased(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        return template() + self.footer(event)

    async def withdrawal_submitted(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        key = self.w3.to_hex(await self.csm.functions.getSigningKeys(event.args["nodeOperatorId"], event.args['keyIndex'], 1).call())
        key_url = BEACONCHAIN_URL_TEMPLATE.format(key)
        return template(key, key_url, humanize_wei(event.args['amount'])) + self.footer(event)

    async def total_signing_keys_count_changed(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        return template(event.args['totalKeysCount']) + self.footer(event)


CSM_EVENTS_TO_FOLLOW = {
        'DepositedSigningKeysCountChanged': EventMessages.deposited_signing_keys_count_changed,
        'ELRewardsStealingPenaltyCancelled': EventMessages.el_rewards_stealing_penalty_cancelled,
        'ELRewardsStealingPenaltyReported': EventMessages.el_rewards_stealing_penalty_reported,
        'ELRewardsStealingPenaltySettled': EventMessages.el_rewards_stealing_penalty_settled,
        'InitialSlashingSubmitted': EventMessages.initial_slashing_submitted,
        'KeyRemovalChargeApplied': EventMessages.key_removal_charge_applied,
        'NodeOperatorManagerAddressChangeProposed': EventMessages.node_operator_manager_address_change_proposed,
        'NodeOperatorManagerAddressChanged': EventMessages.node_operator_manager_address_changed,
        'NodeOperatorRewardAddressChangeProposed': EventMessages.node_operator_reward_address_change_proposed,
        'NodeOperatorRewardAddressChanged': EventMessages.node_operator_reward_address_changed,
        'StuckSigningKeysCountChanged': EventMessages.stuck_signing_keys_count_changed,
        'VettedSigningKeysCountDecreased': EventMessages.vetted_signing_keys_count_decreased,
        'WithdrawalSubmitted': EventMessages.withdrawal_submitted,
        'TotalSigningKeysCountChanged': EventMessages.total_signing_keys_count_changed,
}
