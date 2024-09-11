import os

from aiogram.utils.formatting import Text, Bold, TextLink, Code

EVENT_MESSAGES = {}


class RegisterEventMessage:
    def __init__(self, event_name):
        self.event_name = event_name

    def __call__(self, func):
        EVENT_MESSAGES[self.event_name] = func
        return func


markdown = lambda *args, **kwargs: Text(*args, **kwargs).as_markdown()
header = lambda x: f"*{x}*\n\n"
nl = lambda x=2: "\n" * x

WELCOME_TEXT = ("Welcome to the CSM Sentinel! "
                "Here you can follow Node Operators and receive notifications about their events.")
START_BUTTON_FOLLOW = "Follow"
START_BUTTON_UNFOLLOW = "Unfollow"
FOLLOW_NODE_OPERATOR_BACK = "Back"
FOLLOW_NODE_OPERATOR_TEXT = "Please enter the Node Operator id you want to follow:"
FOLLOW_NODE_OPERATOR_FOLLOWING = "Node Operators you are following: {}" + nl()
UNFOLLOW_NODE_OPERATOR_BACK = "Back"
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
    return markdown("😱 ", Bold("Initial slashing submitted for one of the validators"), nl(),
                    "Slashed key: ", TextLink(key, url=key_url), nl(1),
                    "See the ", TextLink("guide", url="https://docs.lido.fi/staking-modules/csm/guides/slashing"),
                    " for more details")


@RegisterEventMessage("KeyRemovalChargeApplied")
def key_removal_charge_applied(amount):
    return markdown("🔑 ", Bold("Key removal charge applied"), nl(),
                    "Amount of charge: ", Code(amount))


@RegisterEventMessage("NodeOperatorManagerAddressChangeProposed")
def node_operator_manager_address_change_proposed(address):
    return markdown("ℹ️ ", Bold("New manager address proposed"), nl(),
                    "Proposed address: ", Code(address))


@RegisterEventMessage("NodeOperatorManagerAddressChanged")
def node_operator_manager_address_changed(address):
    return markdown("✅ ", Bold("Manager address changed"), nl(),
                    "New address: ", Code(address))


@RegisterEventMessage("NodeOperatorRewardAddressChangeProposed")
def node_operator_reward_address_change_proposed(address):
    return markdown("ℹ️ ", Bold("New rewards address proposed"), nl(),
                    "Proposed address: ", Code(address))


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
                    "Requested key: ", TextLink(key, url=key_url), nl(1),
                    "Request date: ", Code(request_date))


@RegisterEventMessage("PublicRelease")
def public_release():
    return markdown("🎉 ", Bold("Public release of CSM is here!"), nl(),
                    "Now everyone can join the CSM and upload any number of keys.")


@RegisterEventMessage("DistributionDataUpdated")
def distribution_data_updated():
    return markdown("📈 ", Bold("Rewards distributed!"), nl(),
                    "Follow the ", TextLink("CSM UI", url=os.getenv("CSM_UI_URL")),
                    " to check new claimable rewards.")
