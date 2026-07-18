# certify-reverse

Caddy reverse-proxy bootstrapper with DNS-01 automation, Caddy plugin rebuild support, and generated runtime status assets.

## What This Is

- Operator CLI: `./caddy-docker.sh`
- Runtime image builds/runs Caddy with a DNS provider plugin
- Generates runtime files under `./caddy-data`
- Includes dashboard/status assets for services and cert visibility

## Primary Flow

1. Configure `.env` and `upstreams.yml`.
2. Start stack with `./caddy-docker.sh start`.
3. Validate generated config with `./caddy-docker.sh print-caddyfile`.
4. Review runtime status via `./caddy-docker.sh status` and `./caddy-docker.sh logs --follow`.

## Next

- [Getting Started](getting-started.md)
- [Case Study: deSEC + AdGuard + http.server](case-study-desec-adguard-httpserver.md)
- [Configuration](configuration.md)
- [Dashboard](dashboard.md)
- [Operations](operations.md)
- [Troubleshooting](troubleshooting.md)
