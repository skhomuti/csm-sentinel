import os
from datetime import datetime, timedelta

from aiogram.utils.formatting import Text, Bold, TextLink, Code

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

EVENT_MESSAGES = {
    "DepositedSigningKeysCountChanged": lambda x:
    markdown("🤩 ", Bold("Keys were deposited!"), nl(), f"New deposited keys count: {x}"),
    "ELRewardsStealingPenaltyCancelled": lambda remaining:
    markdown("😮‍💨 ", Bold("Cancelled penalty for stealing EL rewards"), nl(),
             "Remaining amount: ", Code(remaining)),
    "ELRewardsStealingPenaltyReported": lambda rewards, block_link:
    markdown("🚨 ", Bold("Penalty for stealing EL rewards reported"), nl(),
             Code(rewards), " rewards from the ", TextLink("block", url=block_link),
             " were transferred to the wrong EL rewards address", nl(1),
             "See the ", TextLink("guide", url="https://docs.lido.fi/staking-modules/csm/guides/mev-stealing"),
             " for more details"),
    "ELRewardsStealingPenaltySettled": lambda burnt:
    markdown("🚨 ", Bold("Penalty for stealing EL rewards settled"), nl(),
             Code(burnt), " burnt from bond"),
    "InitialSlashingSubmitted": lambda key, key_url:
    markdown("😱 ", Bold("Initial slashing submitted"), nl(),
             "Slashed key: ", TextLink(key, url=key_url), nl(1),
             "See the ", TextLink("guide", url="https://docs.lido.fi/staking-modules/csm/guides/slashing"),
             " for more details"),
    "KeyRemovalChargeApplied": lambda amount:
    markdown("🔑 ", Bold("Key removal charge applied"), nl(),
             "Amount of charge: ", Code(amount)),
    "NodeOperatorManagerAddressChangeProposed": lambda address:
    markdown("ℹ️ ", Bold("Proposed change of the node operator manager address"), nl(),
             "Proposed address: ", Code(address)),
    "NodeOperatorManagerAddressChanged": lambda address:
    markdown("✅ ", Bold("Node operator manager address changed"), nl(),
             "New address: ", Code(address)),
    "NodeOperatorRewardAddressChangeProposed": lambda address:
    markdown("ℹ️ ", Bold("Proposed change of the node operator reward address"), nl(),
             "Proposed address: ", Code(address)),
    "NodeOperatorRewardAddressChanged": lambda address:
    markdown("✅ ", Bold("Node operator reward address changed"), nl(),
             "New address: ", Code(address)),
    "StuckSigningKeysCountChanged": lambda count:
    markdown("🚨 ", Bold("Stuck keys reported"), nl(),
             Code(count), " key(s) were not exited in time. Check ", TextLink("CSM UI", url=os.getenv("CSM_UI_URL")), " for more details"),
    "VettedSigningKeysCountDecreased": lambda:
    markdown("🚨 ", Bold("Vetted keys count decreased"), nl(),
             "Consider removing invalid key and upload new one. Check ", TextLink("CSM UI", url=os.getenv("CSM_UI_URL")), " for more details"),
    "WithdrawalSubmitted": lambda key, key_url, amount:
    markdown("👀 ", Bold("Withdrawal submitted"), nl(),
             "Withdrawn the following key: ", TextLink(key, url=key_url),
             " with exit balance: ", Code(amount)),
    "TotalSigningKeysCountChanged": lambda count:
    markdown("👀 ", Bold("Total keys count changed"), nl(),
             "New keys count: ", Code(count)),
    "ValidatorExitRequest": lambda key, key_url, request_date, exit_until:
    markdown("🚨 ", Bold("Validator exit requested"), nl(),
             "Make sure to exit the key before ", exit_until, nl(1),
             "Requested key: ", TextLink(key, url=key_url), nl(1),
             "Request date: ", Code(request_date)),
    "PublicRelease": lambda:
    markdown("🎉 ", Bold("Public release of CSM is here!"), nl(),
             "Now everyone can join the CSM and upload any number of keys."),
    "DistributionDataUpdated": lambda:
    markdown("📈 ", Bold("Rewards distributed!"), nl(),
             "Follow the ", TextLink("CSM UI", url=os.getenv("CSM_UI_URL")),
             " for checking amounts and claiming rewards."),
}

EVENT_MESSAGE_FOOTER = lambda noId, link: Text(nl(), f"nodeOperatorId: {noId}\n", TextLink("Transaction", url=link))
EVENT_MESSAGE_FOOTER_TX_ONLY = lambda x: Text(nl(), TextLink("Transaction", url=x))
