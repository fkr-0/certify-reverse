# Operations (v0.3.0)

## Start/stop

```bash
./caddy-docker.sh start
./caddy-docker.sh stop
./caddy-docker.sh restart
```

## Observe

```bash
./caddy-docker.sh logs --follow
./caddy-docker.sh status
./caddy-docker.sh data
./caddy-docker.sh config
```

## Caddy lifecycle

```bash
./caddy-docker.sh check-updates
./caddy-docker.sh rebuild-caddy
./caddy-docker.sh print-caddyfile
```

## Project/version helpers

```bash
./caddy-docker.sh verify
./caddy-docker.sh version
./caddy-docker.sh bump-patch
./caddy-docker.sh tag
```

## Compose files

- `docker/docker-compose.yml`
- `docker/docker-compose.caddyfile.yml`
