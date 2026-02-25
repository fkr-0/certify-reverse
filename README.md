# certify-reverse

`certify-reverse` is a Dockerized Caddy reverse-proxy bootstrapper for DNS-01 ACME deployments.
It generates runtime config from a single service definition file, builds a custom Caddy binary when needed, and prepares internal trust material for HTTPS upstreams.

## Features

- Automatic DNS-01 TLS provisioning using configurable `caddy-dns` plugin.
- On-demand Caddy plugin build flow:
  - checks `/data/caddy-rebuild` for requested provider module,
  - runs `xcaddy build latest --with github.com/caddy-dns/<provider>` if missing.
- Deterministic Caddyfile and dnsmasq config rendering from service config.
- Internal CA export for upstream TLS validation:
  - `/data/exported-certs/caddy-internal-ca.pem`
  - `/data/exported-certs/caddy-internal-ca.crt`
- Per-service CA directory generation under `/data/<subdomain>/`.
- Helper CLI for common operations (`caddy-docker.sh`).
- Makefile workflow for operations and semantic version bumping.

## Repository Layout

- `app.py`: main bootstrapper and runtime entrypoint.
- `templates.py`: renderers for Caddy and dnsmasq config.
- `status.py`: rich status/inspection output.
- `boot.sh`: container startup script (installs deps, runs app).
- `caddy-docker.sh`: operator wrapper around docker compose.
- `docker-compose.yml`: `caddy` + `dnsmasq` stack.
- `config.yml.example`: safe, committed configuration template.
- `config.yml`: local, ignored runtime configuration.
- `Makefile`: operational and release helpers.
- `docs/`: architecture, config, operations, review docs.

## Requirements

- Docker Engine + Docker Compose plugin.
- Reachable domain and DNS API token for your provider.
- Open ports:
  - `80/tcp`
  - `443/tcp`
  - `53/udp`, `53/tcp`

## Quick Start

1. Create local config:

```bash
cp config.yml.example config.yml
```

2. Edit `config.yml` with real values.

3. Start services:

```bash
make start
```

4. Follow logs:

```bash
make logs
```

5. Verify generated artifacts:

```bash
./caddy-docker.sh data
```

## Configuration

Primary runtime config file: `config.yml`.

Top-level fields:
- `dns_provider`
- `dns_token`
- `email`
- `domain`
- `upstreams`

Per-upstream fields:
- `subdomain`, `ip`, `port`
- `scheme` (`http`/`https`)
- `skip_verify`
- `trust_pool`
- `forward_auth_headers`
- `ext_name`, `ext_params`

See [Configuration Reference](/home/user/code/certify-reverse/docs/configuration.md).

## Runtime Flow

1. Compose launches `caddy` with `/usr/bin/boot`.
2. `boot.sh` installs runtime dependencies (`go`, `python3`, etc.) and executes `/usr/bin/app`.
3. `app.py` loads `/config.yml`.
4. If Caddy binary is missing or lacks provider module, it builds one with `xcaddy`.
5. It writes `/data/Caddyfile` and `/data/dnsmasq.conf`.
6. It exports and distributes CA material for internal TLS.
7. It execs Caddy as PID 1.

## Operations

### Makefile targets

- `make start`
- `make stop`
- `make restart`
- `make logs`
- `make status`
- `make down`
- `make clean`
- `make build`
- `make verify`

### Semantic versioning targets

- `make version`
- `make bump-patch`
- `make bump-minor`
- `make bump-major`
- `make release-note`

These targets update `version` in `pyproject.toml`.

## Idempotency and Design Guidance

Current state: mostly idempotent for generation paths, with one non-idempotent side effect.

Idempotent behavior:
- Re-rendering `Caddyfile` and `dnsmasq.conf` from same config yields stable results.
- Plugin check/build runs only when binary is missing or module absent.
- CA copy operations overwrite files safely.

Non-idempotent behavior:
- `boot.sh` installs packages on every container startup.

Recommendation:
- Keep idempotency as a core property.
- For production-grade startup speed and determinism, move package installs into image build (Dockerfile) and keep runtime bootstrap side-effect-light.

### `config.yml` vs `.env` for service config

Recommended: keep structured service topology in `config.yml`, optionally sourcing secrets from env.

Why:
- Upstream list is hierarchical and better represented as YAML.
- `.env` is good for flat key/value secrets, weaker for nested service arrays.
- Current code already consumes structured YAML directly.

Pragmatic hybrid:
- Keep upstream/service graph in `config.yml`.
- Inject sensitive values (like token/email) from env at runtime (future enhancement).

### Should Caddyfile generation be manual/non-auto?

Recommended: keep auto-generation by default.

Why:
- Prevents config drift.
- Keeps runtime aligned with source-of-truth config.
- Improves repeatability and rollback behavior.

Optional enhancement:
- add explicit `--render-only` mode for CI/previews while retaining auto mode for runtime.

## Security

- `config.yml` is ignored; never commit live tokens.
- Rotate any token that was ever committed or shared.
- Prefer least-privilege DNS API tokens.
- Avoid `skip_verify: true` unless strictly required.

## Verification

```bash
make verify
```

Equivalent manual checks:

```bash
python3 -m py_compile app.py status.py templates.py
bash -n caddy-docker.sh
sh -n boot.sh
docker compose config
```

## Additional Docs

- [Architecture](/home/user/code/certify-reverse/docs/architecture.md)
- [Configuration Reference](/home/user/code/certify-reverse/docs/configuration.md)
- [Operations Guide](/home/user/code/certify-reverse/docs/operations.md)
- [Implementation Review](/home/user/code/certify-reverse/docs/review.md)
- [Changelog](/home/user/code/certify-reverse/CHANGELOG.md)
