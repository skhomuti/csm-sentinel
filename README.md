# CSM Sentinel

Run using Docker:

```bash
docker build -t csm-sentinel .
docker volume create csm-sentinel-persistece

docker run -d --env-file=.env --name csm-sentinel -v csm-sentinel-persistent:/app/.storage csm-sentinel
```
