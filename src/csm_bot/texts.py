import os

from aiogram.utils.formatting import Text, Bold, TextLink, Code
from web3.constants import ADDRESS_ZERO

markdown = lambda *args, **kwargs: Text(*args, **kwargs).as_markdown()
nl = lambda x=2: "\n" * x


class RegisterEventMessage:
    def __init__(self, event_name):
        self.event_name = event_name

    def __call__(self, func):
        EVENT_MESSAGES[self.event_name] = func
        return func


EVENT_MESSAGES = {}
EVENT_DESCRIPTIONS = {
    "DepositedSigningKeysCountChanged": "- 🤩 Node Operator's keys received deposits",
    "ELRewardsStealingPenaltyReported": "- 🚨 Penalty for stealing EL rewards reported",
    "ELRewardsStealingPenaltySettled": "- 🚨 EL rewards stealing penalty confirmed and applied",
    "ELRewardsStealingPenaltyCancelled": "- 😮‍💨 Cancelled penalty for stealing EL rewards",
    "InitialSlashingSubmitted": "- 🚨 Initial slashing submitted for one of the validators",
    "KeyRemovalChargeApplied": "- 🔑 Applied charge for key removal",
    "NodeOperatorManagerAddressChangeProposed": "- ℹ️ New manager address proposed",
    "NodeOperatorManagerAddressChanged": "- ✅ Manager address changed",
    "NodeOperatorRewardAddressChangeProposed": "- ℹ️ New rewards address proposed",
    "NodeOperatorRewardAddressChanged": "- ✅ Rewards address changed",
    "StuckSigningKeysCountChanged": "- 🚨 Reported stuck keys that were not exited in time",
    "VettedSigningKeysCountDecreased": "- 🚨 Uploaded invalid keys",
    "WithdrawalSubmitted": "- 👀 Key withdrawal information submitted",
    "TotalSigningKeysCountChanged": "- 👀 New keys uploaded or removed",
    "ValidatorExitRequest": "- 🚨 One of the validators requested to exit",
    "PublicRelease": "- 🎉 Public release of CSM!",
    "DistributionLogUpdated": "- 📈 New rewards distributed",
    "TargetValidatorsCountChanged": "- 🚨 Target validators count changed",
}

EVENT_LIST_TEXT = markdown(
    "Here is the list of events you will receive notifications for:", nl(1),
    "A 🚨 means urgent action is required from you", nl(),
    Bold("Key Management Events:"), nl(1), "Changes related to keys and their status.", nl(1),
    EVENT_DESCRIPTIONS["VettedSigningKeysCountDecreased"], nl(1),
    EVENT_DESCRIPTIONS["StuckSigningKeysCountChanged"], nl(1),
    EVENT_DESCRIPTIONS["DepositedSigningKeysCountChanged"], nl(1),
    EVENT_DESCRIPTIONS["TotalSigningKeysCountChanged"], nl(1),
    EVENT_DESCRIPTIONS["KeyRemovalChargeApplied"], nl(1),
    EVENT_DESCRIPTIONS["TargetValidatorsCountChanged"], nl(),
    Bold("Address and Reward Changes:"), nl(1), "Changes or proposals regarding management and reward addresses.",
    nl(1),
    EVENT_DESCRIPTIONS["NodeOperatorManagerAddressChangeProposed"], nl(1),
    EVENT_DESCRIPTIONS["NodeOperatorManagerAddressChanged"], nl(1),
    EVENT_DESCRIPTIONS["NodeOperatorRewardAddressChangeProposed"], nl(1),
    EVENT_DESCRIPTIONS["NodeOperatorRewardAddressChanged"], nl(),
    Bold("Slashing and Stealing Events:"), nl(1), "Alerts for validator status and MEV stealing penalties.", nl(1),
    EVENT_DESCRIPTIONS["InitialSlashingSubmitted"], nl(1),
    EVENT_DESCRIPTIONS["ELRewardsStealingPenaltyReported"], nl(1),
    EVENT_DESCRIPTIONS["ELRewardsStealingPenaltySettled"], nl(1),
    EVENT_DESCRIPTIONS["ELRewardsStealingPenaltyCancelled"], nl(),
    Bold("Withdrawal and Exit Requests:"), nl(1), "Notifications for exit requests and confirmation of exits.", nl(1),
    EVENT_DESCRIPTIONS["ValidatorExitRequest"], nl(1),
    EVENT_DESCRIPTIONS["WithdrawalSubmitted"], nl(),
    Bold("Common CSM Events for all the Node Operators:"), nl(1),
    EVENT_DESCRIPTIONS["DistributionLogUpdated"], nl(1),
    EVENT_DESCRIPTIONS["PublicRelease"], nl(),
)

WELCOME_TEXT = ("Welcome to the CSM Sentinel! " + nl() +
                "Here you can follow Node Operators and receive notifications about their events." + nl() +
                "To get started, please use the buttons below." + nl())
START_BUTTON_FOLLOW = "Follow"
START_BUTTON_UNFOLLOW = "Unfollow"
START_BUTTON_EVENTS = "Events"
BUTTON_BACK = "Back"
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

EVENT_MESSAGE_FOOTER = lambda noId, link: Text(nl(), f"nodeOperatorId: {noId}\n", TextLink("Transaction", url=link))
EVENT_MESSAGE_FOOTER_TX_ONLY = lambda x: Text(nl(), TextLink("Transaction", url=x))


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


@RegisterEventMessage("InitialSlashingSubmitted")
def initial_slashing_submitted(key, key_url):
    return markdown("🚨 ", Bold("Initial slashing submitted for one of the validators"), nl(),
                    "Slashed key: ", TextLink(key, url=key_url), nl(1),
                    "See the ", TextLink("guide", url="https://docs.lido.fi/staking-modules/csm/guides/slashing"),
                    " for more details")


@RegisterEventMessage("KeyRemovalChargeApplied")
def key_removal_charge_applied(amount):
    return markdown("🔑 ", Bold("Key removal charge applied"), nl(),
                    "Amount of charge: ", Code(amount))


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
                        "Proposed address: ", Code(address),
                        "To complete the change, the Node Operator must confirm it from the new address.")


@RegisterEventMessage("NodeOperatorRewardAddressChanged")
def node_operator_reward_address_changed(address):
    return markdown("✅ ", Bold("Rewards address changed"), nl(),
                    "New address: ", Code(address))


@RegisterEventMessage("StuckSigningKeysCountChanged")
def stuck_signing_keys_count_changed(count):
    return markdown("🚨 ", Bold("Stuck keys reported"), nl(),
                    Code(count), " key(s) were not exited in time. Check ",
                    TextLink("CSM UI", url=os.getenv("CSM_UI_URL")), " for more details")


@RegisterEventMessage("VettedSigningKeysCountDecreased")
def vetted_signing_keys_count_decreased():
    return markdown("🚨 ", Bold("Vetted keys count decreased"), nl(),
                    "Consider removing invalid keys. Check ",
                    TextLink("CSM UI", url=os.getenv("CSM_UI_URL")), " for more details")


@RegisterEventMessage("WithdrawalSubmitted")
def withdrawal_submitted(key, key_url, amount):
    return markdown("👀 ", Bold("Information about validator withdrawal has been submitted"), nl(),
                    "Withdrawn key: ", TextLink(key, url=key_url),
                    " with exit balance: ", Code(amount), nl(),
                    "Check the amount of the bond released at ", TextLink("CSM UI", url=os.getenv("CSM_UI_URL")))


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


@RegisterEventMessage("PublicRelease")
def public_release():
    return markdown("🎉 ", Bold("Public release of CSM is here!"), nl(),
                    "Now everyone can join the CSM and upload any number of keys.")


@RegisterEventMessage("DistributionLogUpdated")
def distribution_data_updated():
    return markdown("📈 ", Bold("Rewards distributed!"), nl(),
                    "Follow the ", TextLink("CSM UI", url=os.getenv("CSM_UI_URL")),
                    " to check new claimable rewards.")


@RegisterEventMessage("TargetValidatorsCountChanged")
def target_validators_count_changed(mode_before, limit_before, mode_after, limit_after):
    match (mode_before, limit_before, mode_after, limit_after):
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