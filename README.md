# CSM Sentinel (archived)

> [!IMPORTANT]
> This repository is archived and no longer maintained.
> Active development has moved to [lidofinance/sm-sentinel](https://github.com/lidofinance/sm-sentinel), which is the upstream repository for issues, pull requests, documentation, releases, and container images.

CSM Sentinel is a Telegram bot that sends notifications for Lido staking module Node Operator events.
It supports both the Community Staking Module (CSM) and Curated Module deployments.

This bot was originally developed by [@skhomuti](https://github.com/skhomuti), a member of the Lido Protocol community,
to simplify the process of [subscribing to the important events for CSM](https://docs.lido.fi/staking-modules/csm/guides/events/).
For current setup instructions, support, and ongoing maintenance, use [lidofinance/sm-sentinel](https://github.com/lidofinance/sm-sentinel).

The documentation below is retained for historical reference for this archived repository.

## Module support

The bot discovers the module type from `MODULE_ADDRESS` on startup and wires the matching notification adapter automatically:

- **Community Staking Module (CSM):** supports CSM v2 and v3 contracts, including automatic v3 switching after the module is initialized.
- **Curated Module:** supports Curated Module events, MetaRegistry-based Node Operator labels, operator group notifications, and Curated-specific follow/unfollow buttons.

For CSM, subscriptions are managed by Node Operator ID. For Curated, the bot also shows Node Operator labels from the MetaRegistry when they are available.

## Public Instances
These bots are owned by [@skhomuti](https://t.me/skhomuti): [Ethereum](https://t.me/CSMSentinel_bot) and [Hoodi](https://t.me/CSMSentinelHoodi_bot). 
The [Holesky](https://t.me/CSMSentinelHolesky_bot) instance is no longer supported. 

Please note that no guarantee is given for the availability of the bot.
Also consider privacy concerns when using a public instance.

## Running your own instance 

First, you need to create a bot on Telegram. You can do this by talking to the [BotFather](https://t.me/botfather).

Then, you need to create a `.env` by copying one of the `.env.sample.ethereum` or `.env.sample.hoodi` files and filling in the required fields:
- `TOKEN`: The token you received from the BotFather
- `WEB3_SOCKET_PROVIDER`: The websocket provider for your node. 
Preferably, use your own local node, for example the execution node you already run for validators.
But it is also possible to use a public node of any web3 providers.
- `MODULE_ADDRESS`: The staking module address to monitor. Use the CSM address for a CSM instance or the Curated Module address for a Curated instance.
- `MODULE_UI_URL`: Optional URL used in notification links. Use the matching CSM or Curated Module UI.

All other fields are pre-filled with the CSM contracts from the corresponding network. For a Curated instance, update at least `MODULE_ADDRESS` and `MODULE_UI_URL`; dependent contract addresses, module type, staking module ID, and MetaRegistry address are discovered on startup.

`CSM_ADDRESS` and `CSM_UI_URL` are still accepted for backward compatibility, but new configs should use `MODULE_ADDRESS` and `MODULE_UI_URL`.

Run the Sentinel using Docker compose:

```bash
docker compose up -d
```

Or using Docker:

```bash
docker build -t csm-sentinel .
docker volume create csm-sentinel-persistent

docker run -d --env-file=.env --name csm-sentinel -v csm-sentinel-persistent:/app/.storage csm-sentinel
```

## Container images

Container image publishing is disabled in this archived repository.
Use the upstream [lidofinance/sm-sentinel](https://github.com/lidofinance/sm-sentinel) repository for current image publishing and release information.

Historical images, if still available, were published under `ghcr.io/skhomuti/csm-sentinel`.

## Local development

Install dependencies and run the bot with `uv`:

```bash
uv sync
uv run python -m sentinel.main
```

## Running alongside eth-docker
If you are running the bot on the same machine as the [eth-docker](https://github.com/eth-educators/eth-docker), 
you can use the execution client with no need to expose it outside the container.

You need to use a special docker-compose file that connects the Sentinel instance to the eth-docker network.

```bash
docker compose -f docker-compose-ethd.yml up -d
```

`WEB3_SOCKET_PROVIDER` env variable is set to `ws://execution:8546` via docker-compose file, 
so you don't need to specify it in the `.env` file.

## Extra configuration

Pass the `BLOCK_FROM` environment variable to specify the block the bot should start monitoring events from.
Note that this may result in duplicate events if you set it to a block that the bot has already processed before.
`BLOCK_FROM=0` allows you to skip processing past blocks and always start from the head.
In general, you don't need to set this variable.

`BLOCK_BATCH_SIZE` controls how many blocks are fetched per RPC request when processing historical events.
The default value is `10000`.

`PROCESS_BLOCKS_REQUESTS_PER_SECOND` caps how many historical RPC requests `process_blocks_from`
issues per second when backfilling. Leave unset to disable throttling.

## Admin access (ADMIN_IDS)

Some maintenance commands are restricted to admins. To enable them, set your Telegram user ID in the `ADMIN_IDS` environment variable.

How to find your Telegram user ID:
- Open a chat with `@userinfobot`, send `/start`, and copy the numeric `Id` value.

Configure the ID in your `.env`:

```
# Single admin
ADMIN_IDS=123456789

# Multiple admins (comma or space separated)
ADMIN_IDS=123456789,987654321
# or
ADMIN_IDS=123456789 987654321
```

### Admin broadcasts

Admins can broadcast messages via the in-bot Admin panel:

- Open `Admin` → `Broadcast`.
- Choose `All subscribers` to send a message to every chat subscribed to any node operator, then enter your message.
- Or choose `By node operator` and enter comma-separated node operator IDs (e.g., `1,2,3`), then enter your message.

## Integration test suite

End-to-end verification for on-chain events lives under `tests/integration`. Each
scenario replays a real transaction through a lightweight harness that exposes the
same `process_blocks_from` and `subscribe` entrypoints as the real subscription, allowing
the module event message engine to render the expected Markdown for every event.

To enable the suite:

1. Install a local fork provider:
   - [`anvil`](https://book.getfoundry.sh/anvil/)
2. Ensure `.env` contains a `WEB3_SOCKET_PROVIDER` that can serve archive data;
   the tests reuse this value as the fork source (WebSocket URLs are
   translated to their HTTP equivalents automatically)

Each test spawns a dedicated local fork pinned to the case's block to keep state
deterministic. Run the suite with:

```
uv run pytest -m integration
```
