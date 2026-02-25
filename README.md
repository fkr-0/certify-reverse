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
- Optional pinned Caddy version via `CADDY_VERSION` (default `latest`).
- Diff logging when generated files change (stdout + rotating file logger).
- Fallback runtime override with `/data/Caddyfile.overwrite`.
- Built-vs-latest Caddy update check.

## Project Structure

- `src/certify_reverse/cli.py`: runtime bootstrapper and primary CLI.
- `src/certify_reverse/templates.py`: Caddy/dnsmasq/dashboard templating.
- `src/certify_reverse/status_cli.py`: terminal status UI.
- `pyproject.toml`: packaging and script entrypoints.
- `docker/Dockerfile`: image build.
- `docker/docker-compose.yml`: runtime stack.
- `docker/docker-compose.caddyfile.yml`: print generated Caddyfile and exit.
- `caddy-docker.sh`: operational + versioning helper script.
- `.env.example`, `upstreams.yml.example`: config templates.

## Configuration

1. Global values:

```bash
cp .env.example .env
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

## Commands

Everything goes through `./caddy-docker.sh`:

Runtime:
- `start`, `stop`, `restart`, `logs`, `status`, `config`, `data`
- `check-updates`, `rebuild-caddy`, `print-caddyfile`
- `app --<flags>` passthrough

Project/version:
- `verify`
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
5. If generated content changed, unified diff is logged.
6. If `/data/Caddyfile.overwrite` exists, that file is used at runtime.
7. App starts Caddy with selected config file.

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

- Optionally set Docker builder base image for `./caddy-docker.sh build`:

```env
CADDY_BUILDER_IMAGE=caddy:2.10.0-builder
```

- Check update recommendation:

```bash
./caddy-docker.sh check-updates
```

## Dashboard Output

Generated `/data/index.html` includes:
- service links,
- ping/check-cert actions backed by server-side probe endpoints on `status.<domain>`,
- non-secret metadata (email, provider, built/latest caddy version),
- ACME state summary from `/data/acme-state.json`.

Update checks now also report whether the built Caddy binary exposes a native `upgrade` command.

## Verification

```bash
./caddy-docker.sh verify
```

## Docs

- [Architecture](/home/user/code/certify-reverse/docs/architecture.md)
- [Configuration](/home/user/code/certify-reverse/docs/configuration.md)
- [Operations](/home/user/code/certify-reverse/docs/operations.md)
- [Review](/home/user/code/certify-reverse/docs/review.md)
- [Changelog](/home/user/code/certify-reverse/CHANGELOG.md)
