import asyncio
from collections.abc import Callable
import pytest

from csm_bot.config import get_config

from .helpers import replay_transaction_on_anvil, build_subscription


@pytest.fixture(autouse=True)
def force_service_urls(monkeypatch):
    """Force URL-based config to stable values for integration tests."""
    monkeypatch.setenv("ETHERSCAN_URL", "https://etherscan.io")
    monkeypatch.setenv("BEACONCHAIN_URL", "https://beaconcha.in")
    monkeypatch.setenv("CSM_UI_URL", "https://csm.lido.fi")

    get_config.cache_clear()
    try:
        yield
    finally:
        get_config.cache_clear()


pytestmark = [pytest.mark.asyncio, pytest.mark.integration]

PLACEHOLDER_BLOCK = -1
PLACEHOLDER_TX_HASH = "0xTX_HASH_HERE"
PLACEHOLDER_LOG_INDEX = -1
PLACEHOLDER_MESSAGE = "EXPECTED_MESSAGE_HERE"


async def _exercise_event(
    *,
    event_name: str,
    fork_block: int,
    tx_hash: str,
    expected_markdown: str | None,
    anvil_launcher,
    via_subscription: bool = False,
) -> None:
    fork_block = fork_block if not via_subscription else fork_block - 1

    anvil = await anvil_launcher(fork_block)
    harness = await build_subscription(anvil.ws_url)
    subscription_task: asyncio.Task | None = None
    try:
        if via_subscription:
            cfg = get_config()
            subscription_task = asyncio.create_task(harness.subscribe())
            try:
                await asyncio.sleep(0.1)  # give the subscription task time to register handlers
                await replay_transaction_on_anvil(
                    fork_provider_url=cfg.web3_socket_provider,
                    anvil_http_url=anvil.http_url,
                    tx_hash=tx_hash,
                )
                assert await _wait_for(
                    lambda: _has_expected_message(
                        harness,
                        event_name=event_name,
                        expected_markdown=expected_markdown
                    )
                ), (f"Did not find expected message for event {event_name}, \n"
                    f"{expected_markdown=}\n"
                    f"found={[plan.broadcast if plan else None for event, plan in harness.processed_events]}")
            finally:
                harness._shutdown_event.set()
        else:
            await harness.process_blocks_from(fork_block - 1, fork_block)
            assert _has_expected_message(harness, event_name=event_name, expected_markdown=expected_markdown), \
                (f"Did not find expected message for event {event_name}, \n"
                 f"{expected_markdown=}\n"
                 f"found={[plan.broadcast if plan else None for event, plan in harness.processed_events]}")

    finally:
        await harness.disconnect()
        if subscription_task:
            subscription_task.cancel()


async def _wait_for(predicate: Callable[[], bool], *, timeout: float = 5.0, interval: float = 0.1) -> bool:
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() >= deadline:
            return False
        await asyncio.sleep(interval)
    return True


def _has_expected_message(
    harness,
    *,
    event_name: str,
    expected_markdown: str | None
) -> bool:
    messages = []
    for event, plan in harness.processed_events:
        if event is not None and event.event == event_name:
            messages.append(plan.broadcast if plan else None)
    if not messages:
        return False
    if expected_markdown is None:
        return all(message is None for message in messages)
    return expected_markdown in messages


@pytest.fixture(params=[True, False], ids=["via_subscription", "via_process_blocks"])
def via_subscription(request) -> bool:
    return request.param


async def test_process_blocks_deposited_signing_keys_count_changed(anvil_launcher, via_subscription):
    await _exercise_event(
        event_name="DepositedSigningKeysCountChanged",
        fork_block=1279457,
        tx_hash="0xb6be980ac363c47424f972576ae13f46cd41f86fac3157586553a77a063f1926",
        expected_markdown='🤩 *Keys were deposited\\!*\n\nNew deposited keys count: 1\n\nnodeOperatorId: 299\n[Transaction](https://etherscan.io/tx/0xdeadbeef)',
        anvil_launcher=anvil_launcher,
        via_subscription=via_subscription,
    )


async def test_process_blocks_el_rewards_stealing_penalty_cancelled(anvil_launcher, via_subscription):
    await _exercise_event(
        event_name="ELRewardsStealingPenaltyCancelled",
        fork_block=1129167,
        tx_hash="0xfdee52932e34aee4065258ab4f0a5cb5477c4ea24e10ce54a5389e11899fcf68",
        expected_markdown='😮‍💨 *EL rewards stealing penalty cancelled*\n\nRemaining amount: `0\\.05 ether`\n\nnodeOperatorId: 1\n[Transaction](https://etherscan.io/tx/0xdeadbeef)',
        anvil_launcher=anvil_launcher,
        via_subscription=via_subscription,
    )


async def test_process_blocks_el_rewards_stealing_penalty_reported(anvil_launcher, via_subscription):
    await _exercise_event(
        event_name="ELRewardsStealingPenaltyReported",
        fork_block=1129139,
        tx_hash="0x8e3882c7d5f778140e2e2faf0c4f9557e2e9de62e2af970e6479788b6ffe0b9e",
        expected_markdown='🚨 *Penalty for stealing EL rewards reported*\n\n`2 ether` rewards from the [block](https://etherscan.io/block/0xe16e65e99b2a99e8d13fb574c50bea9f703eab51c858d7e692bf7fc8423b6c2c) were transferred to the wrong EL address\nSee the [guide](https://docs.lido.fi/staking-modules/csm/guides/mev-stealing) for more details\n\nnodeOperatorId: 0\n[Transaction](https://etherscan.io/tx/0xdeadbeef)',
        anvil_launcher=anvil_launcher,
        via_subscription=via_subscription,
    )


@pytest.mark.skip(reason="TODO: investigate ELRewardsStealingPenaltySettled replay and update tx hash")
async def test_process_blocks_el_rewards_stealing_penalty_settled(anvil_launcher, via_subscription):
    # TODO: investigate why the historical replay fails with "nonce too low" and
    #       update the transaction hash or replay logic before reenabling.
    await _exercise_event(
        event_name="ELRewardsStealingPenaltySettled",
        fork_block=1267596,
        tx_hash="0xd9389ba64cb14fecbec82b9d06ac3cd20615eb0993e7e5507731794bb3c7b79e",
        expected_markdown=(
            "👀 *Information about validator withdrawal has been submitted*\n\n"
            "Withdrawn key: "
            "[0x977315543bdc050474b4ee90c8cebd7d196d9b622ceb105d87c22a682b23747a8550659451a3f88ad155464b8f6a70f0]"
            "(https://beaconcha.in/validator/0x977315543bdc050474b4ee90c8cebd7d196d9b622ceb105d87c22a682b23747a8550659451a3f88ad155464b8f6a70f0) "
            "with exit balance: `31\\.995429281 ether`\n\n"
            "Check the amount of the bond released at [CSM UI](https://csm.lido.fi)\n\n"
            "nodeOperatorId: 12\n"
            "[Transaction](https://etherscan.io/tx/0xdeadbeef)"
        ),
        anvil_launcher=anvil_launcher,
        via_subscription=via_subscription,
    )


async def test_process_blocks_key_removal_charge_applied(anvil_launcher, via_subscription):
    await _exercise_event(
        event_name="KeyRemovalChargeApplied",
        fork_block=1270229,
        tx_hash="0xa4d75ba64584ddbadded5b4694ca72e2e6304fe7e7bdbe8f6cba304243d4c539",
        expected_markdown='🔑 *Key removal charge applied*\n\nAmount of charge: `0\\.02 ether`\n\nnodeOperatorId: 296\n[Transaction](https://etherscan.io/tx/0xdeadbeef)',
        anvil_launcher=anvil_launcher,
        via_subscription=via_subscription,
    )


async def test_process_blocks_node_operator_manager_address_change_proposed(anvil_launcher, via_subscription):
    await _exercise_event(
        event_name="NodeOperatorManagerAddressChangeProposed",
        fork_block=1284172,
        tx_hash="0x0c0f3914c5634fdf51ad750a13d06820fcec957b70c8692c129f83554d29a114",
        expected_markdown='ℹ️ *Proposed manager address revoked*\n\nnodeOperatorId: 83\n[Transaction](https://etherscan.io/tx/0xdeadbeef)',
        anvil_launcher=anvil_launcher,
        via_subscription=via_subscription,
    )


async def test_process_blocks_node_operator_manager_address_changed(anvil_launcher, via_subscription):
    await _exercise_event(
        event_name="NodeOperatorManagerAddressChanged",
        fork_block=1252972,
        tx_hash="0x884b24a8f2779acb9e74fb0ddc71dcad7d83a5ba850c311c4b3a6511b9cd1791",
        expected_markdown='✅ *Manager address changed*\n\nNew address: `0xa8EF1c5ddb7efe11A0D0E896B1F1F118582395d4`\n\nnodeOperatorId: 239\n[Transaction](https://etherscan.io/tx/0xdeadbeef)',
        anvil_launcher=anvil_launcher,
        via_subscription=via_subscription,
    )


async def test_process_blocks_node_operator_reward_address_change_proposed(anvil_launcher, via_subscription):
    await _exercise_event(
        event_name="NodeOperatorRewardAddressChangeProposed",
        fork_block=1284204,
        tx_hash="0x5dbde52ae7df3da1394654267923892a887515e2bb0ae1d525748583e0ef36d5",
        expected_markdown='ℹ️ *Proposed reward address revoked*\n\nnodeOperatorId: 83\n[Transaction](https://etherscan.io/tx/0xdeadbeef)',
        anvil_launcher=anvil_launcher,
        via_subscription=via_subscription,
    )


async def test_process_blocks_node_operator_reward_address_changed(anvil_launcher, via_subscription):
    await _exercise_event(
        event_name="NodeOperatorRewardAddressChanged",
        fork_block=1252969,
        tx_hash="0x294e7986fe8b8ccf196e8836eac788664405b6f9119927b3f605eb063641e294",
        expected_markdown='✅ *Rewards address changed*\n\nNew address: `0xa8EF1c5ddb7efe11A0D0E896B1F1F118582395d4`\n\nnodeOperatorId: 239\n[Transaction](https://etherscan.io/tx/0xdeadbeef)',
        anvil_launcher=anvil_launcher,
        via_subscription=via_subscription,
    )


async def test_process_blocks_vetted_signing_keys_count_decreased(anvil_launcher, via_subscription):
    await _exercise_event(
        event_name="VettedSigningKeysCountDecreased",
        fork_block=1270156,
        tx_hash="0xbcbb7713a51ec2d3d93a4a693908f01afca482501474d80239602b3dcc42a231",
        expected_markdown='🚨 *Vetted keys count decreased*\n\nConsider removing invalid keys\\. Check [CSM UI](https://csm.lido.fi) for more details\n\nnodeOperatorId: 296\n[Transaction](https://etherscan.io/tx/0xdeadbeef)',
        anvil_launcher=anvil_launcher,
        via_subscription=via_subscription,
    )


async def test_process_blocks_withdrawal_submitted(anvil_launcher, via_subscription):
    await _exercise_event(
        event_name="WithdrawalSubmitted",
        fork_block=1267596,
        tx_hash="0xa32f3975d6f68a4968c770888529fc66b25dfebbafa9581dad3ccb8c84d546e2",
        expected_markdown=(
            "👀 *Information about validator withdrawal has been submitted*\n\n"
            "Withdrawn key: "
            "[0x977315543bdc050474b4ee90c8cebd7d196d9b622ceb105d87c22a682b23747a8550659451a3f88ad155464b8f6a70f0]"
            "(https://beaconcha.in/validator/0x977315543bdc050474b4ee90c8cebd7d196d9b622ceb105d87c22a682b23747a8550659451a3f88ad155464b8f6a70f0) "
            "with exit balance: `31\\.995429281 ether`\n\n"
            "Check the amount of the bond released at [CSM UI](https://csm.lido.fi)\n\n"
            "nodeOperatorId: 12\n"
            "[Transaction](https://etherscan.io/tx/0xdeadbeef)"
        ),
        anvil_launcher=anvil_launcher,
        via_subscription=via_subscription,
    )


async def test_process_blocks_validator_exit_delay_processed(anvil_launcher, via_subscription):
    await _exercise_event(
        event_name="ValidatorExitDelayProcessed",
        fork_block=1124552,
        tx_hash="0x806f016399df457e27454a6cc3feef67c7f24264b2d66e1e56e9bf7f4fc7670c",
        expected_markdown='🚨 *Validator exit delay processed*\n\nValidator: [0x8069c348ce982b1c66b68403f2061a33400f18188db89aa7f7335a4c5b0b674ef5f1a01e428006442c09cb24ad44b39e](https://beaconcha.in/validator/0x8069c348ce982b1c66b68403f2061a33400f18188db89aa7f7335a4c5b0b674ef5f1a01e428006442c09cb24ad44b39e)\nDelay penalty: `0\\.05 ether`\n\nPenalty will be applied when the validator exits\n\nnodeOperatorId: 242\n[Transaction](https://etherscan.io/tx/0xdeadbeef)',
        anvil_launcher=anvil_launcher,
        via_subscription=via_subscription,
    )


async def test_process_blocks_total_signing_keys_count_changed(anvil_launcher, via_subscription):
    await _exercise_event(
        event_name="TotalSigningKeysCountChanged",
        fork_block=1285083,
        tx_hash="0x83fe416f67366fcb2487abb593a854ba076ee337ba34a498d4d8b477e37f504a",
        expected_markdown='👀 *New keys uploaded*\n\nKeys count: `0 \\-\\> 1`\n\nnodeOperatorId: 314\n[Transaction](https://etherscan.io/tx/0xdeadbeef)',
        anvil_launcher=anvil_launcher,
        via_subscription=via_subscription,
    )


async def test_process_blocks_validator_exit_request(anvil_launcher, via_subscription):
    await _exercise_event(
        event_name="ValidatorExitRequest",
        fork_block=1085299,
        tx_hash="0x1cfa7454c54a3d874c2d55082ed6bf82f0a730e279f7d598221820e2b0cf9bfc",
        expected_markdown=(
            "🚨 *Validator exit requested*\n\n"
            "Make sure to exit the key before Sat 30 Aug 2025, 02:20PM UTC\n"
            "Check the [Exiting CSM validators](https://dvt-homestaker.stakesaurus.com/bonded-validators-setup/lido-csm/exiting-csm-validators) guide for more details\n"
            "Requested key: [0x8069c348ce982b1c66b68403f2061a33400f18188db89aa7f7335a4c5b0b674ef5f1a01e428006442c09cb24ad44b39e](https://beaconcha.in/validator/0x8069c348ce982b1c66b68403f2061a33400f18188db89aa7f7335a4c5b0b674ef5f1a01e428006442c09cb24ad44b39e)\n"
            "Request date: `Tue 26 Aug 2025, 02:20PM UTC`\n\n"
            "nodeOperatorId: 242\n"
            "[Transaction](https://etherscan.io/tx/0xdeadbeef)"
        ),
        anvil_launcher=anvil_launcher,
        via_subscription=via_subscription,
    )


async def test_process_blocks_distribution_log_updated(anvil_launcher, via_subscription):
    await _exercise_event(
        event_name="DistributionLogUpdated",
        fork_block=1245619,
        tx_hash="0x961bf83cd38b6b9e452e70dbaa74eda5035759dc91c8ab2de773778e22418d24",
        expected_markdown=(
            "📈 *Rewards distributed\u005c!*\n\n"
            "Follow the [CSM UI](https://csm.lido.fi) to check new claimable rewards\\.\n\n"
            "[Transaction](https://etherscan.io/tx/0xdeadbeef)"
        ),
        anvil_launcher=anvil_launcher,
        via_subscription=via_subscription,
    )


async def test_process_blocks_triggered_exit_fee_recorded(anvil_launcher, via_subscription):
    await _exercise_event(
        event_name="TriggeredExitFeeRecorded",
        fork_block=1292072,
        tx_hash="0xaf7969ea79766f13956215cd2abca8395d006d1d54493773adf28975cb6f6b1d",
        expected_markdown=(
            "🚨 *Exit fee recorded*\n\n"
            "Validator: [0xaaaf86690452a63abe9ef3398055c7105fd78ea980eddfd5513612e1ef7342b49190fef0de38188bc850a7c474bce8e0]"
            "(https://beaconcha.in/validator/0xaaaf86690452a63abe9ef3398055c7105fd78ea980eddfd5513612e1ef7342b49190fef0de38188bc850a7c474bce8e0)\n"
            "Fee paid now: `1 wei`\n"
            "Fee to be charged on exit: `1 wei`\n\n"
            "Exit fee will be applied when the validator exits\n\n"
            "nodeOperatorId: 120\n"
            "[Transaction](https://etherscan.io/tx/0xdeadbeef)"
        ),
        anvil_launcher=anvil_launcher,
        via_subscription=via_subscription,
    )


async def test_process_blocks_strikes_penalty_processed(anvil_launcher, via_subscription):
    await _exercise_event(
        event_name="StrikesPenaltyProcessed",
        fork_block=1292072,
        tx_hash="0xaf7969ea79766f13956215cd2abca8395d006d1d54493773adf28975cb6f6b1d",
        expected_markdown=(
            "🚨 *Strikes penalty processed*\n\n"
            "Validator: [0xaaaf86690452a63abe9ef3398055c7105fd78ea980eddfd5513612e1ef7342b49190fef0de38188bc850a7c474bce8e0]"
            "(https://beaconcha.in/validator/0xaaaf86690452a63abe9ef3398055c7105fd78ea980eddfd5513612e1ef7342b49190fef0de38188bc850a7c474bce8e0)\n"
            "Penalty amount: `0\\.258 ether`\n\n"
            "Penalty will be charged when the validator withdraws\n\n"
            "nodeOperatorId: 120\n"
            "[Transaction](https://etherscan.io/tx/0xdeadbeef)"
        ),
        anvil_launcher=anvil_launcher,
        via_subscription=via_subscription,
    )


async def test_bond_curve_set(anvil_launcher, via_subscription):
    await _exercise_event(
        event_name="BondCurveSet",
        fork_block=1103471,
        tx_hash="0x4b6a752d52ff1e480ba51d0038f16b8a5e9c27bc0f3fd99aa09dff5401e97282",
        expected_markdown=(
            'ℹ️ *Node Operator type changed*\n\nNew type id: `2`\n'
            'Operational requirements may now differ\\. '
            'Check the [CSM UI](https://csm.lido.fi) for updated guidance\n\n'
            'nodeOperatorId: 234\n[Transaction](https://etherscan.io/tx/0xdeadbeef)'
        ),
        anvil_launcher=anvil_launcher,
        via_subscription=via_subscription,
    )


async def test_process_blocks_target_validators_count_changed(anvil_launcher, via_subscription):
    await _exercise_event(
        event_name="TargetValidatorsCountChanged",
        fork_block=1084974,
        tx_hash="0xf920fb581bc3e69d5db7066aa905fbe8b3e62ca688cfb1c7b9dc2585f0652221",
        expected_markdown='🚨 *Target validators count changed*\n\nThe limit has been set to zero\\.\nAll keys will be requested to exit immediately\\.\n\nnodeOperatorId: 242\n[Transaction](https://etherscan.io/tx/0xdeadbeef)',
        anvil_launcher=anvil_launcher,
        via_subscription=via_subscription,
    )
