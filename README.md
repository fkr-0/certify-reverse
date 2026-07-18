# certify-reverse

Caddy reverse-proxy bootstrapper with DNS-01 automation, runtime plugin management, and generated service status assets.

## Highlights

- Single operator CLI: `./caddy-docker.sh` (Makefile removed to avoid duplication).
- Python package layout under `src/certify_reverse` with console scripts:
  - `certify-reverse`
  - `certify-reverse-status`
- Container installs the package during build (`pip install .`) and runs script entrypoint.
- Config split:
  - `.env` for global settings (`DNS_PROVIDER`, `DNS_TOKEN`, `DOMAIN`, etc.)
  - `upstreams.yml` for service topology (top-level keys are subdomains)
- Provider-specific credential keys through `CADDY_DNS_PLUGIN_TOKEN_FIELD`.
- Strict configuration validation before files or service directories are written.
- Optional pinned Caddy version via `CADDY_VERSION` (default `latest`).
- Automatic rebuild when an existing Caddy binary does not match an explicitly
  pinned `CADDY_VERSION`.
- Diff logging when generated files change (stderr + rotating file logger).
- Fallback runtime override with `/data/Caddyfile.overwrite`.
- Built-vs-latest Caddy update check.

## Project Structure

- `src/certify_reverse/cli.py`: runtime bootstrapper and primary CLI.
- `src/certify_reverse/templates.py`: Caddy/dnsmasq configuration templating.
- `src/certify_reverse/status_page.py`: self-contained operational dashboard UI.
- `src/certify_reverse/status_cli.py`: terminal status UI.
- `pyproject.toml`: packaging and script entrypoints.
- `docker/Dockerfile`: image build.
- `docker/docker-compose.yml`: runtime stack.
- `docker/docker-compose.caddyfile.yml`: print generated Caddyfile and exit.
- `caddy-docker.sh`: operational + versioning helper script.
- `.env.example`, `upstreams.yml.example`: config templates.
- `CHANGELOG.md`: release history.
- `issues.yml`: known larger work intentionally deferred from the current release.

## Configuration

1. Global values:

```bash
cp .env.example .env
```

The selected Caddy DNS plugin may use a different credential field. Known
provider defaults are applied when the setting is omitted; deSEC uses `token`,
while unknown providers retain the `api_token` fallback. Override it explicitly
when the plugin documentation requires another directive:

```env
DNS_PROVIDER=desec
DNS_TOKEN=REPLACE_WITH_DNS_API_TOKEN
CADDY_DNS_PLUGIN_TOKEN_FIELD=token
DOMAIN=example.com
```

2. Upstream topology:

```bash
cp upstreams.yml.example upstreams.yml
```

`upstreams.yml` shape:

```yaml
app:
  ip: 10.0.0.10
  port: 8080
  scheme: http

secure-app:
  ip: 10.0.0.20
  port: 8443
  scheme: https
  skip_verify: false
```

Subdomain keys must be valid DNS names. Ports must be integers from `1` through
`65535`, schemes are limited to `http` and `https`, and trust-pool paths must be
absolute. IPv4, IPv6, and hostname upstream targets are supported.

## Commands

Everything goes through `./caddy-docker.sh`:

Runtime:
- `start`, `stop`, `restart`, `logs`, `status`, `config`, `data`
- `check-updates`, `rebuild-caddy`, `print-caddyfile`
- `reload-dnsmasq`
- `app --<flags>` passthrough

`rebuild-caddy` behavior:
- If `caddy` service is running, it uses `docker compose exec caddy certify-reverse --rebuild-caddy`.
- If `caddy` service is not running, it falls back to `docker compose run --rm --no-deps caddy --rebuild-caddy` (one-shot rebuild container).
- Rebuild uses writable per-workdir Go caches (`/data/caddybuild/.cache`) so non-root UID/GID container runs do not fail on `/.cache/go-build` permissions.
- `logs` behavior:
  - `./caddy-docker.sh logs` shows both `caddy` and `dnsmasq`.
  - `./caddy-docker.sh logs --follow` follows both.
  - `./caddy-docker.sh logs --follow caddy` (or `dnsmasq`) filters to one service.

Project/version:
- `verify` (tests, lint, type checks, package build, shell syntax, Compose validation)
- `version`
- `bump-patch`, `bump-minor`, `bump-major`
- `release-note`
- `tag`

Examples:

```bash
./caddy-docker.sh start
./caddy-docker.sh check-updates
./caddy-docker.sh rebuild-caddy
./caddy-docker.sh print-caddyfile
./caddy-docker.sh reload-dnsmasq
./caddy-docker.sh version
./caddy-docker.sh bump-patch
```

## Runtime Behavior

1. Container starts `/usr/local/bin/boot`.
2. `boot.sh` runs `certify-reverse`.
3. App reads `/config/.env` and `/config/upstreams.yml`.
4. App generates:
   - `/data/Caddyfile`
   - `/data/dnsmasq.conf`
   - `/data/index.html`
   - `/data/acme-state.json`
   - `/data/crtsh-state.json`
5. If generated content changed, unified diff is logged.
6. If `/data/Caddyfile.overwrite` exists, that file is used at runtime.
7. App starts Caddy with selected config file.

dnsmasq behavior:
- Uses generated `/data/dnsmasq.conf`.
- Logs to `/data/logs/dnsmasq.log` (directory is created on startup).
- Wildcard DNS target IP is configured via `.env` `DNSMASQ_ADDRESS_IP` (default `10.0.0.1`).
- Wildcard DNS target selection mode via `.env` `DNSMASQ_ADDRESS_MODE`:
  - `manual` (default): use `DNSMASQ_ADDRESS_IP`.
  - `host-src-ip`: auto-derive host source IP using `ip -4 route get 1.1.1.1` from `caddy-docker.sh` and pass it to runtime; fallback to `DNSMASQ_ADDRESS_IP`.
- Optional extra CLI flags via `.env`:

```env
DNSMASQ_EXTRA_ARGS="-q"
```

- Config reload on demand:

```bash
./caddy-docker.sh reload-dnsmasq
```

If setup is invalid (missing env vars or upstream file), startup now fails with a concise actionable error and exits cleanly instead of dumping a long traceback.

## Permissions

- The `caddy` container runs as your host UID/GID by default via compose variable injection (`HOST_UID/HOST_GID`), wired by `caddy-docker.sh`.
- This avoids common bind-mount ownership problems on `./caddy-data`.
- Container is granted `NET_BIND_SERVICE` so non-root execution can still bind ports `80/443`.

## Caddy Version and Updates

- Request version with `.env`:

```env
CADDY_VERSION=latest
# or
CADDY_VERSION=v2.10.2
```

Pinned values must be semantic versions, optionally prefixed with `v` and with
an optional prerelease/build suffix. When a pinned version differs from the
installed binary, startup rebuilds Caddy even if the DNS plugin already exists.
`latest` keeps the installed compatible binary and uses the update-check command
for advisory release discovery.

- Optionally set Docker builder base image for `./caddy-docker.sh build`:

```env
CADDY_BUILDER_IMAGE=caddy:2.10.0-builder
```

- If `CADDY_BUILDER_IMAGE` is not set, `./caddy-docker.sh` derives it from `CADDY_VERSION`:
  - `CADDY_VERSION=v2.10.0` -> `caddy:2.10.0-builder`
  - `CADDY_VERSION=latest` -> fallback `caddy:2.10.0-builder`

- Check update recommendation:

```bash
./caddy-docker.sh check-updates
```

## Dashboard Output

Generated `/data/index.html` includes:
- an operational overview with service, reachability, TLS, and Caddy-version metrics,
- searchable service links and explicit ping/TLS actions backed by server-side
  probe endpoints on `status.<domain>`,
- a readable ACME state summary plus optional raw JSON,
- searchable crt.sh certificate history sourced from `/data/crtsh-state.json`,
- live crt.sh refresh through the Caddy proxy endpoint,
- system/light/dark themes, responsive layouts, keyboard-visible focus, and
  reduced-motion support.

The dashboard uses semantic landmarks and native tables, includes a skip link,
announces asynchronous status changes, and keeps controls at least 44 px high.
See [`docs/dashboard.md`](docs/dashboard.md) for workflows and limitations.

Startup also queries `crt.sh` for the configured domain and logs:
- match count,
- latest certificate id/not_after,
- derived validity state.

The dashboard can also query live crt.sh via Caddy proxy endpoint:
- `status.<domain>/probe/crtsh?q=<domain>&output=json`
- This avoids browser CORS issues against `crt.sh` directly.

Update checks now also report whether the built Caddy binary exposes a native `upgrade` command.

Generated runtime text/JSON/static files are replaced atomically. Internal
service certificates are staged before installation, with private keys written
as owner-only (`0600`) and public certificates as `0644`.

The exported internal root CA can be retrieved from the generated
`internal-ca.<domain>` host at `/cert/caddy-internal-ca.pem` or
`/cert/caddy-internal-ca.crt`. This endpoint serves only public trust material;
service private keys are never routed by Caddy.

## Verification

```bash
./caddy-docker.sh verify
```

The full verification path requires Docker Compose and `uv`. It uses the frozen
`uv.lock`, runs the Python and shell regression suite, Ruff, Mypy, creates wheel
and source distributions in a temporary directory, and validates both Compose
configurations.

## End-User Docs

- Quick start: [`docs/getting-started.md`](docs/getting-started.md)
- Configuration: [`docs/configuration.md`](docs/configuration.md)
- Operations: [`docs/operations.md`](docs/operations.md)
- Troubleshooting: [`docs/troubleshooting.md`](docs/troubleshooting.md)
- Architecture: [`docs/architecture.md`](docs/architecture.md)
- Changelog: [`CHANGELOG.md`](CHANGELOG.md)

Docs site build (local):

```bash
uvx --from mkdocs-material mkdocs serve
```

Docs site deploy (GitHub Pages):

- Push to `main`.
- GitHub Actions workflow `docs-pages.yml` builds and publishes docs automatically.
