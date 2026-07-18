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

`version`, `bump-*`, `release-note`, and `tag` are local project operations and
do not require Docker. `verify` is the release gate and checks:

- frozen dependency resolution,
- unit, regression, and Compose integration tests,
- Ruff and Mypy,
- wheel and source-distribution creation,
- synchronized project/package versions,
- shell syntax,
- base and Caddyfile-print Compose configurations.

The `config` command redacts keys containing `TOKEN`, `SECRET`, `PASSWORD`,
`API_KEY`, or `PRIVATE_KEY` before printing `.env` and `upstreams.yml`. Both
underscore and hyphen spellings are recognized, and complete YAML block-scalar
secret bodies are suppressed.

Runtime-generated configuration, status, dashboard, CA, and static-asset files
use same-directory atomic replacement. Service certificate generation stages
both outputs first and installs private keys with mode `0600`.
