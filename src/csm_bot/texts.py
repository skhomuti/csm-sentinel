from dataclasses import dataclass
from enum import StrEnum

from aiogram.utils.formatting import Text, Bold, TextLink, Code, Italic
from web3.constants import ADDRESS_ZERO
from csm_bot.config import get_config

def markdown(*args, **kwargs) -> str:
    return Text(*args, **kwargs).as_markdown()


def nl(x: int = 2) -> str:
    return "\n" * x


class RegisterEventMessage:
    def __init__(self, event_name):
        self.event_name = event_name

    def __call__(self, func):
        EVENT_MESSAGES[self.event_name] = func
        return func


EVENT_MESSAGES = {}


@dataclass(frozen=True, slots=True)
class EventDefinition:
    name: str
    description: str

    group_title: "EventGroup"


class EventGroup(StrEnum):
    KEY_MANAGEMENT = "Key Management Events:"
    ADDRESS_AND_REWARD_CHANGES = "Address and Reward Changes:"
    SLASHING_AND_STEALING = "Slashing and Stealing Events:"
    WITHDRAWAL_AND_EXIT = "Withdrawal and Exit Requests:"
    COMMON_CSM = "Common CSM Events for all the Node Operators:"


GROUP_DESCRIPTIONS: dict[EventGroup, str] = {
    EventGroup.KEY_MANAGEMENT: "Changes related to keys and their status.",
    EventGroup.ADDRESS_AND_REWARD_CHANGES: "Changes or proposals regarding management and reward addresses.",
    EventGroup.SLASHING_AND_STEALING: "Alerts for validator status and MEV stealing penalties.",
    EventGroup.WITHDRAWAL_AND_EXIT: "Notifications for exit requests and confirmation of exits.",
    EventGroup.COMMON_CSM: "",
}


EVENT_CATALOG: list[EventDefinition] = [
    EventDefinition(
        name="VettedSigningKeysCountDecreased",
        description="- 🚨 Uploaded invalid keys",
        group_title=EventGroup.KEY_MANAGEMENT,
    ),
    EventDefinition(
        name="DepositedSigningKeysCountChanged",
        description="- 🤩 Node Operator's keys received deposits",
        group_title=EventGroup.KEY_MANAGEMENT,
    ),
    EventDefinition(
        name="TotalSigningKeysCountChanged",
        description="- 👀 New keys uploaded or removed",
        group_title=EventGroup.KEY_MANAGEMENT,
    ),
    EventDefinition(
        name="KeyRemovalChargeApplied",
        description="- 🔑 Applied charge for key removal",
        group_title=EventGroup.KEY_MANAGEMENT,
    ),
    EventDefinition(
        name="BondCurveSet",
        description="- ℹ️ Node Operator type changed",
        group_title=EventGroup.KEY_MANAGEMENT,
    ),
    EventDefinition(
        name="TargetValidatorsCountChanged",
        description="- 🚨 Target validators count changed",
        group_title=EventGroup.KEY_MANAGEMENT,
    ),
    EventDefinition(
        name="NodeOperatorManagerAddressChangeProposed",
        description="- ℹ️ New manager address proposed",
        group_title=EventGroup.ADDRESS_AND_REWARD_CHANGES,
    ),
    EventDefinition(
        name="NodeOperatorManagerAddressChanged",
        description="- ✅ Manager address changed",
        group_title=EventGroup.ADDRESS_AND_REWARD_CHANGES,
    ),
    EventDefinition(
        name="NodeOperatorRewardAddressChangeProposed",
        description="- ℹ️ New rewards address proposed",
        group_title=EventGroup.ADDRESS_AND_REWARD_CHANGES,
    ),
    EventDefinition(
        name="NodeOperatorRewardAddressChanged",
        description="- ✅ Rewards address changed",
        group_title=EventGroup.ADDRESS_AND_REWARD_CHANGES,
    ),
    EventDefinition(
        name="ELRewardsStealingPenaltyReported",
        description="- 🚨 Penalty for stealing EL rewards reported",
        group_title=EventGroup.SLASHING_AND_STEALING,
    ),
    EventDefinition(
        name="ELRewardsStealingPenaltySettled",
        description="- 🚨 EL rewards stealing penalty confirmed and applied",
        group_title=EventGroup.SLASHING_AND_STEALING,
    ),
    EventDefinition(
        name="ELRewardsStealingPenaltyCancelled",
        description="- 😮‍💨 Cancelled penalty for stealing EL rewards",
        group_title=EventGroup.SLASHING_AND_STEALING,
    ),
    EventDefinition(
        name="ValidatorExitRequest",
        description="- 🚨 One of the validators requested to exit",
        group_title=EventGroup.WITHDRAWAL_AND_EXIT,
    ),
    EventDefinition(
        name="ValidatorExitDelayProcessed",
        description="- 🚨 Exit delay processed; penalty queued for withdrawal",
        group_title=EventGroup.WITHDRAWAL_AND_EXIT,
    ),
    EventDefinition(
        name="TriggeredExitFeeRecorded",
        description="- 🚨 Triggered exit fee recorded; penalty will be charged on exit",
        group_title=EventGroup.WITHDRAWAL_AND_EXIT,
    ),
    EventDefinition(
        name="StrikesPenaltyProcessed",
        description="- 🚨 Strikes penalty processed; validator exited for poor performance",
        group_title=EventGroup.WITHDRAWAL_AND_EXIT,
    ),
    EventDefinition(
        name="WithdrawalSubmitted",
        description="- 👀 Key withdrawal information submitted",
        group_title=EventGroup.WITHDRAWAL_AND_EXIT,
    ),
    EventDefinition(
        name="DistributionLogUpdated",
        description="- 📈 New rewards distributed",
        group_title=EventGroup.COMMON_CSM,
    ),
    EventDefinition(
        name="Initialized",
        description="- 🎉 CSM v2 launched on mainnet",
        group_title=EventGroup.COMMON_CSM,
    ),
]

EVENT_DESCRIPTIONS = {event.name: event.description for event in EVENT_CATALOG}


def _group_event_catalog() -> list[tuple[EventGroup, list[EventDefinition]]]:
    grouped: dict[EventGroup, list[EventDefinition]] = {}
    for event in EVENT_CATALOG:
        grouped.setdefault(event.group_title, []).append(event)
    return list(grouped.items())


def build_event_list_text(allowed_events: set[str], module_ui_url: str | None = None) -> str:
    _ = module_ui_url
    parts: list = [
        "Here is the list of events you will receive notifications for:",
        nl(1),
        "A 🚨 means urgent action is required from you",
        nl(),
    ]

    for group_title, events in _group_event_catalog():
        active_events = [event for event in events if event.name in allowed_events]
        if not active_events:
            continue
        parts.extend([Bold(group_title.value), nl(1)])
        description = GROUP_DESCRIPTIONS.get(group_title, "")
        if description:
            parts.extend([description, nl(1)])
        for event in active_events:
            parts.extend([event.description, nl(1)])
        parts.append(nl())

    return markdown(*parts)


EVENT_LIST_TEXT = build_event_list_text(set(EVENT_DESCRIPTIONS.keys()))

WELCOME_TEXT = ("Welcome to the CSM Sentinel! " + nl() +
                "Here you can follow Node Operators and receive notifications about their events." + nl() +
                "To get started, please use the buttons below." + nl())
START_BUTTON_FOLLOW = "Follow"
START_BUTTON_UNFOLLOW = "Unfollow"
START_BUTTON_EVENTS = "Events"
BUTTON_BACK = "Back"
START_BUTTON_ADMIN = "Admin"
ADMIN_BUTTON_SUBSCRIPTIONS = "Subscriptions"
ADMIN_MENU_TEXT = "Admin tools:"
ADMIN_BUTTON_BROADCAST = "Broadcast"
ADMIN_BROADCAST_MENU_TEXT = "Choose broadcast target:"
ADMIN_BROADCAST_ALL = "All subscribers"
ADMIN_BROADCAST_BY_NO = "By node operator"
ADMIN_BROADCAST_ENTER_MESSAGE_ALL = "Please enter the message to send to all subscribers:"
ADMIN_BROADCAST_ENTER_NO_IDS = "Please enter comma-separated node operator IDs (e.g., 1,2,3):"
ADMIN_BROADCAST_NO_IDS_INVALID = "No valid node operator IDs provided."
ADMIN_BROADCAST_CONFIRM_HINT = "Review the message below and confirm before broadcasting."
ADMIN_BROADCAST_PREVIEW_ALL = "Broadcast preview for all subscribers:"
ADMIN_BROADCAST_PREVIEW_SELECTED = "Broadcast preview for: {targets}"
BUTTON_SEND_BROADCAST = "Send broadcast"
ADMIN_PRIVATE_CHAT_REQUIRED = "Admin tools are only available in a private chat with the bot. Please open a private chat to continue."
NO_NEW_BLOCKS_ADMIN_ALERT = (
    "⚠️ No new blocks processed in the last {minutes} minutes. Latest block: {block}"
)
FOLLOW_NODE_OPERATOR_TEXT = "Please enter the Node Operator id you want to follow:"
FOLLOW_NODE_OPERATOR_FOLLOWING = "Node Operators you are following: {}" + nl()
UNFOLLOW_NODE_OPERATOR_TEXT = "Please enter the Node Operator id you want to unfollow:"
UNFOLLOW_NODE_OPERATOR_NOT_FOLLOWING = "You are not following any Node Operators."
UNFOLLOW_NODE_OPERATOR_FOLLOWING = "Node Operators you are following: {}" + nl()
NODE_OPERATOR_FOLLOWED = "You are now following Node Operator #{}"
NODE_OPERATOR_CANT_FOLLOW = "Invalid Node Operator id. Please enter the correct id."
NODE_OPERATOR_UNFOLLOWED = "You are no longer following Node Operator #{}"
NODE_OPERATOR_CANT_UNFOLLOW = "Can't unfollow the Node Operator you are not following. \nPlease enter the correct id."
EVENT_EMITS = "Event {} emitted with data: \n{}"

def EVENT_MESSAGE_FOOTER(no_id, link) -> Text:
    return Text(nl(), f"nodeOperatorId: {no_id}\n", TextLink("Transaction", url=link))


def EVENT_MESSAGE_FOOTER_TX_ONLY(link) -> Text:
    return Text(nl(), TextLink("Transaction", url=link))


@RegisterEventMessage("DepositedSigningKeysCountChanged")
def deposited_signing_keys_count_changed(x):
    return markdown("🤩 ", Bold("Keys were deposited!"), nl(), f"New deposited keys count: {x}")


@RegisterEventMessage("ELRewardsStealingPenaltyCancelled")
def el_rewards_stealing_penalty_cancelled(remaining):
    return markdown("😮‍💨 ", Bold("EL rewards stealing penalty cancelled"), nl(),
                    "Remaining amount: ", Code(remaining))


@RegisterEventMessage("ELRewardsStealingPenaltyReported")
def el_rewards_stealing_penalty_reported(rewards, block_link):
    return markdown("🚨 ", Bold("Penalty for stealing EL rewards reported"), nl(),
                    Code(rewards), " rewards from the ", TextLink("block", url=block_link),
                    " were transferred to the wrong EL address", nl(1),
                    "See the ", TextLink("guide", url="https://docs.lido.fi/staking-modules/csm/guides/mev-stealing"),
                    " for more details")


@RegisterEventMessage("ELRewardsStealingPenaltySettled")
def el_rewards_stealing_penalty_settled(burnt):
    return markdown("🚨 ", Bold("EL rewards stealing penalty confirmed and applied"), nl(),
                    Code(burnt), " burnt from bond")


@RegisterEventMessage("KeyRemovalChargeApplied")
def key_removal_charge_applied(amount):
    return markdown("🔑 ", Bold("Key removal charge applied"), nl(),
                    "Amount of charge: ", Code(amount))


@RegisterEventMessage("BondCurveSet")
def bond_curve_set(curve_id: int):
    cfg = get_config()
    return markdown(
        "ℹ️ ", Bold("Node Operator type changed"), nl(),
        "New type id: ", Code(str(curve_id)), nl(1),
        "Operational requirements may now differ. Check the ",
        TextLink("CSM UI", url=cfg.module_ui_url or ""),
        " for updated guidance"
    )


@RegisterEventMessage("NodeOperatorManagerAddressChangeProposed")
def node_operator_manager_address_change_proposed(address):
    if address == ADDRESS_ZERO:
        return markdown("ℹ️ ", Bold("Proposed manager address revoked"))
    else:
        return markdown("ℹ️ ", Bold("New manager address proposed"), nl(),
                        "Proposed address: ", Code(address), nl(1),
                        "To complete the change, the Node Operator must confirm it from the new address.")


@RegisterEventMessage("NodeOperatorManagerAddressChanged")
def node_operator_manager_address_changed(address):
    return markdown("✅ ", Bold("Manager address changed"), nl(),
                    "New address: ", Code(address))


@RegisterEventMessage("NodeOperatorRewardAddressChangeProposed")
def node_operator_reward_address_change_proposed(address):
    if address == ADDRESS_ZERO:
        return markdown("ℹ️ ", Bold("Proposed reward address revoked"))
    else:
        return markdown("ℹ️ ", Bold("New rewards address proposed"), nl(),
                        "Proposed address: ", Code(address), nl(1),
                        "To complete the change, the Node Operator must confirm it from the new address.")


@RegisterEventMessage("NodeOperatorRewardAddressChanged")
def node_operator_reward_address_changed(address):
    return markdown("✅ ", Bold("Rewards address changed"), nl(),
                    "New address: ", Code(address))


@RegisterEventMessage("VettedSigningKeysCountDecreased")
def vetted_signing_keys_count_decreased():
    cfg = get_config()
    return markdown("🚨 ", Bold("Vetted keys count decreased"), nl(),
                    "Consider removing invalid keys. Check ",
                    TextLink("CSM UI", url=cfg.module_ui_url or ""), " for more details")


@RegisterEventMessage("WithdrawalSubmitted")
def withdrawal_submitted(key, key_url, amount):
    cfg = get_config()
    return markdown("👀 ", Bold("Information about validator withdrawal has been submitted"), nl(),
                    "Withdrawn key: ", TextLink(key, url=key_url),
                    " with exit balance: ", Code(amount), nl(),
                    "Check the amount of the bond released at ", TextLink("CSM UI", url=cfg.module_ui_url or ""))


@RegisterEventMessage("TotalSigningKeysCountChanged")
def total_signing_keys_count_changed(count, count_before):
    if count > count_before:
        return markdown("👀 ", Bold("New keys uploaded"), nl(),
                        "Keys count: ", Code(f"{count_before} -> {count}"))
    else:
        return markdown("🚨 ", Bold("Key removed"), nl(),
                        "Total keys: ", Code(count))


@RegisterEventMessage("ValidatorExitRequest")
def validator_exit_request(key, key_url, request_date, exit_until):
    return markdown("🚨 ", Bold("Validator exit requested"), nl(),
                    "Make sure to exit the key before ", exit_until, nl(1),
                    "Check the ", TextLink("Exiting CSM validators",
                                           url="https://dvt-homestaker.stakesaurus.com/bonded-validators-setup/lido-csm/exiting-csm-validators"),
                    " guide for more details", nl(1),
                    "Requested key: ", TextLink(key, url=key_url), nl(1),
                    "Request date: ", Code(request_date))


@RegisterEventMessage("ValidatorExitDelayProcessed")
def validator_exit_delay_processed(key, key_url, penalty):
    return markdown("🚨 ", Bold("Validator exit delay processed"), nl(),
                    "Validator: ", TextLink(key, url=key_url), nl(1),
                    "Delay penalty: ", Code(penalty), nl(),
                    "Penalty will be applied when the validator exits")


@RegisterEventMessage("TriggeredExitFeeRecorded")
def triggered_exit_fee_recorded(key, key_url, paid_fee, recorded_fee):
    return markdown("🚨 ", Bold("Exit fee recorded"), nl(),
                    "Validator: ", TextLink(key, url=key_url), nl(1),
                    "Fee paid now: ", Code(paid_fee), nl(1),
                    "Fee to be charged on exit: ", Code(recorded_fee), nl(),
                    "Exit fee will be applied when the validator exits")


@RegisterEventMessage("StrikesPenaltyProcessed")
def strikes_penalty_processed(key, key_url, penalty):
    return markdown("🚨 ", Bold("Strikes penalty processed"), nl(),
                    "Validator: ", TextLink(key, url=key_url), nl(1),
                    "Penalty amount: ", Code(penalty), nl(),
                    "Penalty will be charged when the validator withdraws")


@RegisterEventMessage("DistributionLogUpdated")
def distribution_data_updated(node_operator_id: int | None=None, striked_validators: list | None=None):
    cfg = get_config()
    base_message = Text(
        "📈 ", Bold("Rewards distributed!"), nl(),
        "Follow the ", TextLink("CSM UI", url=cfg.module_ui_url or ""),
        " to check new claimable rewards."
    )

    if node_operator_id is not None and striked_validators:

        return Text(
            base_message,
            Text(nl(),
                "⚠️ ", Bold("Strikes detected for your validators"), nl(),
                "Node Operator ID: ", Code(str(node_operator_id)), nl(1),
                "Validators with strikes: ", Code(len(striked_validators)), nl(1),
            )
        ).as_markdown()

    return base_message.as_markdown()


@RegisterEventMessage("TargetValidatorsCountChanged")
def target_validators_count_changed(mode_before, limit_before, mode_after, limit_after):
    match (mode_before, limit_before, mode_after, limit_after):
        case (_, _, 1, 0):
            return markdown("🚨 ", Bold("Target validators count changed"), nl(),
                            "The limit has been set to zero.", nl(1),
                            "All keys will be requested to exit first.")
        case (_, _, 2, 0):
            return markdown("🚨 ", Bold("Target validators count changed"), nl(),
                            "The limit has been set to zero.", nl(1),
                            "All keys will be requested to exit immediately.")
        case (1, _, 1, limit_after) if limit_after < limit_before:
            return markdown("🚨 ", Bold("Target validators count changed"), nl(),
                            f"The limit has been decreased from {limit_before} to {limit_after}.", nl(1),
                            f"{limit_before - limit_after} more key(s) will be requested to exit first.")
        case (2, _, 2, limit_after) if limit_after < limit_before:
            return markdown("🚨 ", Bold("Target validators count changed"), nl(),
                            f"The limit has been decreased from {limit_before} to {limit_after}.", nl(1),
                            f"{limit_before - limit_after} more key(s) will be requested to exit immediately.")
        case (_, _, 1, _):
            return markdown("🚨 ", Bold("Target validators count changed"), nl(),
                            f"The limit has been set to {limit_after}.", nl(1),
                            f"{limit_after} keys will be requested to exit first.")
        case (_, _, 2, _):
            return markdown("🚨 ", Bold("Target validators count changed"), nl(),
                            f"The limit has been set to {limit_after}.", nl(1),
                            f"{limit_after} keys will be requested to exit immediately.")
        case (_, _, 0, _):
            return markdown("🚨 ", Bold("Target validators count changed"), nl(),
                            "The limit has been set to zero. No keys will be requested to exit.")
        case _:
            # is there any case for this?
            return markdown("🚨 ", Bold("Target validators count changed"), nl(),
                            f"Mode changed from {mode_before} to {mode_after}.", nl(1),
                            f"Limit changed from {limit_before} to {limit_after}.")

@RegisterEventMessage("Initialized")
def initialized():
    return markdown(
        "🎉 ", Bold("CSM v2 is live!"), nl(),
        "No software update or migration is required. Explore the ", TextLink("CSM widget", url="https://csm.lido.fi"),
        " to try out new features. More info ", TextLink("here.", url="https://discord.com/channels/761182643269795850/1293241757382738001/1399751236579758140"), nl(),
        Bold("For those who are in the "),
        TextLink("initial ICS list", url="https://ipfs.io/ipfs/bafkreido7ieacbe6nlhdivxfp2gd5kxovofngf6qdmahih4laihm675e2a"),
        Bold(" or applied for ICS, please read "),
        TextLink("this short note", url="https://hackmd.io/@lido/csm-v2-checklist"),
        Bold(" to learn more."), nl(),
        Italic("Thank you all for being with us from v1 to v2. CSM is committed to bringing more home stakers into Ethereum. We’d greatly appreciate your help in amplifying this update!")
    )
