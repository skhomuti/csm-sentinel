# CSM Sentinel

CSM Sentinel is a telegram bot that sends you notifications for your CSM Node Operator events.

This bot was developed and is maintained by [@skhomuti](https://github.com/skhomuti), a member of the Lido Protocol community, 
to simplify the process of [subscribing to the important events for CSM](https://docs.lido.fi/staking-modules/csm/guides/events/). 
You can either [run the bot yourself](https://github.com/skhomuti/csm-sentinel?tab=readme-ov-file#running-your-own-instance) 
or use the [community-supported public instance](https://github.com/skhomuti/csm-sentinel?tab=readme-ov-file#public-instances), depending on your privacy preferences.

## Public Instances
These bots are owned by [@skhomuti](https://t.me/skhomuti): [Ethereum](https://t.me/CSMSentinel_bot) and [Holesky](https://t.me/CSMSentinelHolesky_bot) 

Please note that no guarantee is given for the availability of the bot.
Also consider privacy concerns when using a public instance.

## Running your own instance 

First, you need to create a bot on Telegram. You can do this by talking to the [BotFather](https://t.me/botfather).

Then, you need to create a `.env` by copying one of the `env.example.ethereum` or `env.example.holesky` files and filling in the required fields:
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
