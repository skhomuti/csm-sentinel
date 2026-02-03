import asyncio
import datetime
import logging
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import aiohttp
from eth_utils import humanize_wei
from web3 import AsyncWeb3
from async_lru import alru_cache

from csm_bot.models import (
    Event,
    EventHandler,
)
from csm_bot.texts import (
    EVENT_MESSAGES,
    EVENT_MESSAGE_FOOTER,
    EVENT_MESSAGE_FOOTER_TX_ONLY,
    EVENT_EMITS,
)
from csm_bot.config import get_config

if TYPE_CHECKING:
    from csm_bot.app.module_adapter import ModuleAdapter

# This is a dictionary that will be populated with the events to follow
EVENTS_TO_FOLLOW: dict[str, EventHandler] = {}

logger = logging.getLogger(__name__)

DistributionLogFetcher = Callable[[str], Awaitable[dict | list]]


@dataclass
class NotificationPlan:
    """Container describing how subscribers should be notified for an event."""

    # Optional general broadcast message
    broadcast: str | None = None
    # If set, restrict broadcast to these node operator IDs (as strings)
    broadcast_node_operator_ids: set[str] | None = None
    # Specific messages for individual node operators (keyed by node operator ID as string)
    per_node_operator: dict[str, str] = field(default_factory=dict)

    def add_node_operator_message(self, node_operator_id: int | str, message: str) -> None:
        """Register a node-operator specific message, storing the ID as a string."""

        self.per_node_operator[str(node_operator_id)] = message

    def with_broadcast_targets(
        self, node_operator_ids: Iterable[int | str]
    ) -> "NotificationPlan":
        """Limit broadcast delivery to the provided node operator identifiers."""

        self.broadcast_node_operator_ids = {str(no_id) for no_id in node_operator_ids}
        return self

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
        EVENTS_TO_FOLLOW[self.event_name] = EventHandler(self.event_name, func)
        return func


class EventMessages:
    def __init__(
        self,
        w3: AsyncWeb3,
        module_adapter: "ModuleAdapter",
        distribution_log_fetcher: "DistributionLogFetcher | None" = None,
    ):
        self.connectProvider = ConnectOnDemand(w3)
        self.w3 = w3
        self.module_adapter = module_adapter
        self._distribution_log_fetcher = distribution_log_fetcher or self._default_distribution_log_fetcher

        # Config snapshot
        self.cfg = get_config()
        self.module_address = module_adapter.addresses.module
        self.accounting_address = module_adapter.addresses.accounting
        self.parameters_registry_address = module_adapter.addresses.parameters_registry

        # Contracts (module-specific adapter)
        self.module = module_adapter.contracts.module
        self.accounting = module_adapter.contracts.accounting
        self.parametersRegistry = module_adapter.contracts.parameters_registry

    @alru_cache(maxsize=3)
    async def _fetch_distribution_log(self, log_cid: str):
        """Retrieve a distribution log from IPFS using the provided CID."""

        if not log_cid:
            raise ValueError("log_cid must be provided")

        return await self._distribution_log_fetcher(log_cid)

    async def _default_distribution_log_fetcher(self, log_cid: str):
        ipfs_url = f"https://ipfs.io/ipfs/{log_cid}"
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(ipfs_url) as response:
                if response.status != 200:
                    raise aiohttp.ClientError(f"HTTP {response.status} when fetching {ipfs_url}")
                return await response.json()

    @staticmethod
    def _validator_sort_key(validator_id: str) -> tuple[int, int | str]:
        validator_str = str(validator_id)
        if validator_str.isdigit():
            return 0, int(validator_str)
        return 1, validator_str

    async def default(self, event: Event):
        return NotificationPlan(broadcast=EVENT_EMITS.format(event.event, event.args))

    async def get_notification_plan(self, event: Event):
        if event.event not in self.module_adapter.allowed_events():
            return None
        async with self.connectProvider:
            result = await self.module_adapter.event_enricher(event, self)
            if result is None:
                event_handler = EVENTS_TO_FOLLOW.get(event.event)
                if event_handler is not None:
                    handler = event_handler.handler
                else:
                    handler = self.default
                result = await handler(self, event)

        if result is None:
            return None

        plan = result if isinstance(result, NotificationPlan) else NotificationPlan(broadcast=result)

        if (
            plan.broadcast
            and plan.broadcast_node_operator_ids is None
            and "nodeOperatorId" in event.args
        ):
            plan.with_broadcast_targets({event.args["nodeOperatorId"]})

        return plan

    def footer(self, event: Event):
        tx_template = self._require_template(self.cfg.etherscan_tx_url_template, "ETHERSCAN_URL")
        tx_link = tx_template.format("0x" + event.tx.hex())
        if 'nodeOperatorId' not in event.args:
            return EVENT_MESSAGE_FOOTER_TX_ONLY(tx_link).as_markdown()
        return EVENT_MESSAGE_FOOTER(event.args['nodeOperatorId'], tx_link).as_markdown()

    @staticmethod
    def _require_template(template: str | None, env_var: str) -> str:
        if template is None:
            raise RuntimeError(f"{env_var} must be configured")
        return template

    @RegisterEvent('DepositedSigningKeysCountChanged')
    async def deposited_signing_keys_count_changed(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        return template(event.args['depositedKeysCount']) + self.footer(event)

    @RegisterEvent('ELRewardsStealingPenaltyCancelled')
    async def el_rewards_stealing_penalty_cancelled(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        remaining_amount = humanize_wei(
            await self.accounting.functions
            .getActualLockedBond(event.args['nodeOperatorId'])
            .call(block_identifier=event.block)
        )
        return template(remaining_amount) + self.footer(event)

    @RegisterEvent('ELRewardsStealingPenaltyReported')
    async def el_rewards_stealing_penalty_reported(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        block_hash = self.w3.to_hex(event.args['proposedBlockHash'])
        block_template = self._require_template(self.cfg.etherscan_block_url_template, "ETHERSCAN_URL")
        block_link = block_template.format(block_hash)
        return template(humanize_wei(event.args['stolenAmount']), block_link) + self.footer(event)

    @RegisterEvent('ELRewardsStealingPenaltySettled')
    async def el_rewards_stealing_penalty_settled(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        logs = await self.accounting.events.BondBurned().get_logs(from_block=event.block, to_block=event.block)
        burnt_event = next(filter(lambda x: x.args['nodeOperatorId'] == event.args['nodeOperatorId'], logs), None)
        if burnt_event:
            amount = burnt_event.args["burnedAmount"]
        else:
            amount = 0
        return template(humanize_wei(amount)) + self.footer(event)

    @RegisterEvent('BondCurveSet')
    async def bond_curve_set(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        return template(event.args['curveId']) + self.footer(event)

    @RegisterEvent('KeyRemovalChargeApplied')
    async def key_removal_charge_applied(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        curve_id = await self.accounting.functions.getBondCurveId(event.args['nodeOperatorId']).call(
            block_identifier=event.block
        )
        amount = await self.parametersRegistry.functions.getKeyRemovalCharge(curve_id).call(
            block_identifier=event.block
        )
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

    @RegisterEvent('VettedSigningKeysCountDecreased')
    async def vetted_signing_keys_count_decreased(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        return template() + self.footer(event)

    @RegisterEvent('WithdrawalSubmitted')
    async def withdrawal_submitted(self, event: Event):
        # TODO add exit penalties applied
        template: callable = EVENT_MESSAGES.get(event.event)
        key = self.w3.to_hex(
            await self.module.functions
            .getSigningKeys(event.args["nodeOperatorId"], event.args['keyIndex'], 1)
            .call(block_identifier=event.block)
        )
        beacon_template = self._require_template(self.cfg.beaconchain_url_template, "BEACONCHAIN_URL")
        key_url = beacon_template.format(key)
        return template(key, key_url, humanize_wei(event.args['amount'])) + self.footer(event)

    @RegisterEvent('TotalSigningKeysCountChanged')
    async def total_signing_keys_count_changed(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        node_operator = await self.module.functions.getNodeOperator(event.args["nodeOperatorId"]).call(
            block_identifier=event.block - 1
        )
        return template(event.args['totalKeysCount'], node_operator.totalAddedKeys) + self.footer(event)

    @RegisterEvent('ValidatorExitRequest')
    async def validator_exit_request(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        key = self.w3.to_hex(event.args['validatorPubkey'])
        beacon_template = self._require_template(self.cfg.beaconchain_url_template, "BEACONCHAIN_URL")
        key_url = beacon_template.format(key)
        request_date = datetime.datetime.fromtimestamp(event.args['timestamp'], datetime.UTC)
        exit_until = request_date + datetime.timedelta(days=4)
        return template(key, key_url, _format_date(request_date), _format_date(exit_until)) + self.footer(event)

    @RegisterEvent('ValidatorExitDelayProcessed')
    async def validator_exit_delay_processed(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        key = self.w3.to_hex(event.args['pubkey'])
        beacon_template = self._require_template(self.cfg.beaconchain_url_template, "BEACONCHAIN_URL")
        key_url = beacon_template.format(key)
        penalty = humanize_wei(event.args['delayPenalty'])
        return template(key, key_url, penalty) + self.footer(event)

    @RegisterEvent('TriggeredExitFeeRecorded')
    async def triggered_exit_fee_recorded(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        key = self.w3.to_hex(event.args['pubkey'])
        beacon_template = self._require_template(self.cfg.beaconchain_url_template, "BEACONCHAIN_URL")
        key_url = beacon_template.format(key)
        paid_fee = humanize_wei(event.args['withdrawalRequestPaidFee'])
        recorded_fee = humanize_wei(event.args['withdrawalRequestRecordedFee'])
        return template(key, key_url, paid_fee, recorded_fee) + self.footer(event)

    @RegisterEvent('StrikesPenaltyProcessed')
    async def strikes_penalty_processed(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        key = self.w3.to_hex(event.args['pubkey'])
        beacon_template = self._require_template(self.cfg.beaconchain_url_template, "BEACONCHAIN_URL")
        key_url = beacon_template.format(key)
        penalty = humanize_wei(event.args['strikesPenalty'])
        return template(key, key_url, penalty) + self.footer(event)

    @RegisterEvent("DistributionLogUpdated")
    async def distribution_log_updated(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        base_message = template()
        footer = self.footer(event)

        plan = NotificationPlan(broadcast=f"{base_message}{footer}")

        log_cid = event.args.get("logCid")
        try:
            distribution_log = await self._fetch_distribution_log(log_cid)
        except Exception as exc:
            logger.warning(
                "Failed to enrich DistributionLogUpdated for logCid %s: %s",
                log_cid,
                exc,
            )
            return plan

        entries = distribution_log if isinstance(distribution_log, list) else [distribution_log]

        all_operator_ids: set[str] = set()
        strikes_per_operator: dict = {}

        for entry in entries:
            operators = entry.get("operators", {}) or {}
            for operator_id, operator_data in operators.items():
                operator_id_str = str(operator_id)
                all_operator_ids.add(operator_id_str)

                validators = operator_data.get("validators", {}) or {}
                for validator_id, validator_data in validators.items():
                    strikes = int(validator_data.get("strikes", 0))

                    if strikes <= 0:
                        continue
                    strikes_per_operator.setdefault(operator_id_str, []).append(
                        (
                            str(validator_id),
                            strikes
                        )
                    )

        if all_operator_ids:
            plan.with_broadcast_targets(all_operator_ids)

        for operator_id, flagged in strikes_per_operator.items():
            flagged_sorted = sorted(flagged, key=lambda item: self._validator_sort_key(item[0]))
            plan.add_node_operator_message(
                operator_id,
                f"{template(operator_id, flagged_sorted)}{footer}"
            )

        return plan

    @RegisterEvent("TargetValidatorsCountChanged")
    async def target_validators_count_changed(self, event: Event):
        node_operator = await self.module.functions.getNodeOperator(event.args["nodeOperatorId"]).call(
            block_identifier=event.block - 1
        )
        mode_before = node_operator.targetLimitMode
        limit_before = node_operator.targetLimit

        template: callable = EVENT_MESSAGES.get(event.event)
        return template(mode_before, limit_before, event.args['targetLimitMode'], event.args['targetValidatorsCount']) + self.footer(event)

    @RegisterEvent("Initialized")
    async def initialized(self, event: Event):
        template: callable = EVENT_MESSAGES.get(event.event)
        if event.args['version'] != 2:
            return None
        # Normalize address comparison to avoid case-sensitivity issues
        if event.address.lower() != self.module_address.lower():
            return None
        return template() + self.footer(event)
