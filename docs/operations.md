# Operations

## Runtime Control

```bash
./caddy-docker.sh start
./caddy-docker.sh stop
./caddy-docker.sh restart
./caddy-docker.sh status
```

## Logs and State

```bash
./caddy-docker.sh logs
./caddy-docker.sh logs --follow
./caddy-docker.sh logs --follow caddy
./caddy-docker.sh data
./caddy-docker.sh config
```

## Caddy Maintenance

```bash
./caddy-docker.sh check-updates
./caddy-docker.sh rebuild-caddy
./caddy-docker.sh print-caddyfile
```

## dnsmasq

```bash
./caddy-docker.sh reload-dnsmasq
```

## Release/Version Helpers

```bash
./caddy-docker.sh verify
./caddy-docker.sh version
./caddy-docker.sh bump-patch
./caddy-docker.sh bump-minor
./caddy-docker.sh bump-major
./caddy-docker.sh release-note
./caddy-docker.sh tag
```
