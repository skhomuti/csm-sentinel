# CSM Sentinel

CSM Sentinel is a telegram bot that sends you notifications for your CSM Node Operator events.

## Instances
At the moment, only Holesky instance is available. Check it out [here](https://t.me/CSMSentinelHolesky_bot).
Please note that no guarantee is given for the availability of the bot.

## Running your own instance 

First, you need to create a bot on Telegram. You can do this by talking to the [BotFather](https://t.me/botfather).

Then, you need to create a `.env` by copying the `env.example.holesky` file and filling in the required fields:
- TOKEN: The token you received from the BotFather
- WEB3_SOCKET_PROVIDER: The websocket provider for your node

All the other fields are pre-filled with the Holesky instance values.

Next, run the CSM Watcher using Docker:

```bash
docker build -t csm-sentinel .
docker volume create csm-sentinel-persistece

docker run -d --env-file=.env --name csm-sentinel -v csm-sentinel-persistent:/app/.storage csm-sentinel
```
