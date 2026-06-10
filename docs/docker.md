# Docker And OrbStack

[English README](../README.md) · [한국어 README](../README.ko.md)

Zeus can run as a local CLI container. The image is intentionally local-first:
it does not expose network ports, does not mount the Docker socket, and stores
Zeus state in a named volume.

## Build

```sh
docker compose build zeus
```

## Start

```sh
docker compose up -d zeus
```

## Smoke Checks

```sh
docker exec zeus-agent zeus status --json
docker exec zeus-agent zeus higher-order-agent-os --scenario status --json
docker exec zeus-agent zeus objective-compile-workflow --objective "Zeus, compile this goal into a governed workflow." --requires-code --task-count 4 --json
docker exec zeus-agent zeus governed-live-connectors --scenario trusted-local-smoke --json
```

## Stop

```sh
docker compose down
```

The `zeus_home` volume keeps local Zeus state across restarts. Remove it only
when you intentionally want a clean local state:

```sh
docker volume rm 14_zeus_public_v050_zeus_home
```
