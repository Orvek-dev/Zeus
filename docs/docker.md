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
docker exec zeus-agent zeus --version
docker exec zeus-agent zeus init
docker exec zeus-agent zeus status
docker exec zeus-agent zeus dev kernel-status   # legacy harness surface, parked under `zeus dev`
```

## Stop

```sh
docker compose down
```

The `zeus_home` volume keeps local Zeus state across restarts. Remove it only
when you intentionally want a clean local state:

```sh
docker compose down --volumes
```
