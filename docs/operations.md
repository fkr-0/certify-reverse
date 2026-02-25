# Operations Guide

## Start and Stop

```bash
./caddy-docker.sh start
./caddy-docker.sh stop
./caddy-docker.sh restart
```

## Logs

```bash
./caddy-docker.sh logs
./caddy-docker.sh logs --follow
```

Application log file path:
- host: `./caddy-data/logs/app.log`
- container: `/data/logs/app.log`

## Runtime Inspection

```bash
./caddy-docker.sh status
./caddy-docker.sh config
./caddy-docker.sh data
```

## App Utility Commands

```bash
./caddy-docker.sh app --show-certs
./caddy-docker.sh app --export-certs
./caddy-docker.sh app --create-service-dirs
./caddy-docker.sh app --force-build
```

## Container Exec

```bash
./caddy-docker.sh shell
./caddy-docker.sh exec caddy version
```

## Rebuild and Cleanup

```bash
./caddy-docker.sh build
./caddy-docker.sh down
./caddy-docker.sh clean
```

## Troubleshooting Checklist

1. `docker compose ps` shows both `caddy` and `dnsmasq` running.
2. `./caddy-docker.sh logs --follow` has no Python traceback.
3. `/data/Caddyfile` and `/data/dnsmasq.conf` exist.
4. `/data/exported-certs/caddy-internal-ca.pem` exists for HTTPS upstream trust.
5. DNS token and provider in `config.yml` are valid.

## Safe Rollout Pattern

1. Update `config.yml`.
2. Run `docker compose config` locally.
3. Restart with `./caddy-docker.sh restart`.
4. Validate through logs and `./caddy-docker.sh app --show-certs`.
