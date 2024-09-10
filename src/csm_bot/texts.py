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

START_BUTTON_FOLLOW = "Follow to NO updates"
START_BUTTON_UNFOLLOW = "Unfollow from NO updates"
FOLLOW_NODE_OPERATOR_BACK = "Back"
FOLLOW_NODE_OPERATOR_TEXT = "Please enter the node operator id you want to follow:"
FOLLOW_NODE_OPERATOR_FOLLOWING = "You are following the node operator ids: {}" + nl()
UNFOLLOW_NODE_OPERATOR_BACK = "Back"
UNFOLLOW_NODE_OPERATOR_TEXT = "Please enter the node operator id you want to unfollow:"
UNFOLLOW_NODE_OPERATOR_NOT_FOLLOWING = "You are not following any node operators."
UNFOLLOW_NODE_OPERATOR_FOLLOWING = "You are following the node operator ids: {}" + nl()
NODE_OPERATOR_FOLLOWED = "Node operator id {} followed!"
NODE_OPERATOR_UNFOLLOWED = "Node operator id {} unfollowed!"
EVENT_EMITS = "Event {} emitted with data: \n{}"

EVENT_MESSAGE_FOOTER = lambda noId, link: Text(nl(), f"nodeOperatorId: {noId}\n", TextLink("Transaction", url=link))
EVENT_MESSAGE_FOOTER_TX_ONLY = lambda x: Text(nl(), TextLink("Transaction", url=x))


@RegisterEventMessage("DepositedSigningKeysCountChanged")
def deposited_signing_keys_count_changed(x):
    return markdown("🤩 ", Bold("Keys were deposited!"), nl(), f"New deposited keys count: {x}")


@RegisterEventMessage("ELRewardsStealingPenaltyCancelled")
def el_rewards_stealing_penalty_cancelled(remaining):
    return markdown("😮‍💨 ", Bold("Cancelled penalty for stealing EL rewards"), nl(),
                    "Remaining amount: ", Code(remaining))


@RegisterEventMessage("ELRewardsStealingPenaltyReported")
def el_rewards_stealing_penalty_reported(rewards, block_link):
    return markdown("🚨 ", Bold("Penalty for stealing EL rewards reported"), nl(),
                    Code(rewards), " rewards from the ", TextLink("block", url=block_link),
                    " were transferred to the wrong EL rewards address", nl(1),
                    "See the ", TextLink("guide", url="https://docs.lido.fi/staking-modules/csm/guides/mev-stealing"),
                    " for more details")


@RegisterEventMessage("ELRewardsStealingPenaltySettled")
def el_rewards_stealing_penalty_settled(burnt):
    return markdown("🚨 ", Bold("Penalty for stealing EL rewards settled"), nl(),
                    Code(burnt), " burnt from bond")


@RegisterEventMessage("InitialSlashingSubmitted")
def initial_slashing_submitted(key, key_url):
    return markdown("😱 ", Bold("Initial slashing submitted"), nl(),
                    "Slashed key: ", TextLink(key, url=key_url), nl(1),
                    "See the ", TextLink("guide", url="https://docs.lido.fi/staking-modules/csm/guides/slashing"),
                    " for more details")


@RegisterEventMessage("KeyRemovalChargeApplied")
def key_removal_charge_applied(amount):
    return markdown("🔑 ", Bold("Key removal charge applied"), nl(),
                    "Amount of charge: ", Code(amount))


@RegisterEventMessage("NodeOperatorManagerAddressChangeProposed")
def node_operator_manager_address_change_proposed(address):
    return markdown("ℹ️ ", Bold("Proposed change of the node operator manager address"), nl(),
                    "Proposed address: ", Code(address))


@RegisterEventMessage("NodeOperatorManagerAddressChanged")
def node_operator_manager_address_changed(address):
    return markdown("✅ ", Bold("Node operator manager address changed"), nl(),
                    "New address: ", Code(address))


@RegisterEventMessage("NodeOperatorRewardAddressChangeProposed")
def node_operator_reward_address_change_proposed(address):
    return markdown("ℹ️ ", Bold("Proposed change of the node operator reward address"), nl(),
                    "Proposed address: ", Code(address))


@RegisterEventMessage("NodeOperatorRewardAddressChanged")
def node_operator_reward_address_changed(address):
    return markdown("✅ ", Bold("Node operator reward address changed"), nl(),
                    "New address: ", Code(address))


@RegisterEventMessage("StuckSigningKeysCountChanged")
def stuck_signing_keys_count_changed(count):
    return markdown("🚨 ", Bold("Stuck keys reported"), nl(),
                    Code(count), " key(s) were not exited in time. Check ",
                    TextLink("CSM UI", url=os.getenv("CSM_UI_URL")), " for more details")


@RegisterEventMessage("VettedSigningKeysCountDecreased")
def vetted_signing_keys_count_decreased():
    return markdown("🚨 ", Bold("Vetted keys count decreased"), nl(),
                    "Consider removing invalid key and upload new one. Check ",
                    TextLink("CSM UI", url=os.getenv("CSM_UI_URL")), " for more details")


@RegisterEventMessage("WithdrawalSubmitted")
def withdrawal_submitted(key, key_url, amount):
    return markdown("👀 ", Bold("Withdrawal submitted"), nl(),
                    "Withdrawn the following key: ", TextLink(key, url=key_url),
                    " with exit balance: ", Code(amount))


@RegisterEventMessage("TotalSigningKeysCountChanged")
def total_signing_keys_count_changed(count):
    return markdown("👀 ", Bold("Total keys count changed"), nl(),
                    "New keys count: ", Code(count))


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
                    " for checking amounts and claiming rewards.")
