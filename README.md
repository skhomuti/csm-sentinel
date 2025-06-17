# CSM Sentinel

CSM Sentinel is a Telegram bot that sends you notifications for your CSM Node Operator events.

This bot was developed and is maintained by [@skhomuti](https://github.com/skhomuti), a member of the Lido Protocol community, 
to simplify the process of [subscribing to the important events for CSM](https://docs.lido.fi/staking-modules/csm/guides/events/). 
You can either [run the bot yourself](https://github.com/skhomuti/csm-sentinel?tab=readme-ov-file#running-your-own-instance) 
or use the [community-supported public instance](https://github.com/skhomuti/csm-sentinel?tab=readme-ov-file#public-instances), depending on your privacy preferences.

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
Preferably, use your own local node e.g. you already have for CSM validators.
But it is also possible to use a public node of any web3 providers.

All other fields are pre-filled with the contracts from the corresponding network.

Run the CSM Sentinel using Docker compose:

```bash
docker compose up -d
```

Or using Docker:

```bash
docker build -t csm-sentinel .
docker volume create csm-sentinel-persistent

docker run -d --env-file=.env --name csm-sentinel -v csm-sentinel-persistent:/app/.storage csm-sentinel
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
