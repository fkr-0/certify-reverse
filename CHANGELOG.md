# Changelog

All notable changes to this project are documented here.

## [0.3.5] - 2026-02-25

### Added

- Host UID/GID mapping for `caddy` service to reduce bind-mount ownership issues on `./caddy-data`.
- `NET_BIND_SERVICE` capability for non-root low-port binding (`80/443`) in compose runtime.

### Changed

- Invalid setup handling now emits concise actionable errors instead of raw Python stack traces for common config mistakes.
- Restart behavior adjusted for `caddy` service to avoid endless loops on static setup errors (`on-failure:3`).
- Dashboard probe model improved via server-side `status.<domain>/probe/<service>` routes for stronger reachability checks.
- Docker package install switched to a virtualenv path to satisfy Alpine/PEP 668 constraints.
- Update check output now includes whether native `caddy upgrade` support is present in the built binary.

## [0.3.0] - 2026-02-25

### Added

- Python package scaffolding with `src/` layout:
  - `src/certify_reverse/cli.py`
  - `src/certify_reverse/templates.py`
  - `src/certify_reverse/status_cli.py`
- Package console scripts:
  - `certify-reverse`
  - `certify-reverse-status`
- `caddy-docker.sh` project/version commands replacing Makefile functionality:
  - `verify`, `version`, `bump-patch`, `bump-minor`, `bump-major`, `release-note`, `tag`
- Architecture review doc refresh for current layout.
- Dashboard checks now use server-side probe endpoints via `status.<domain>` for stronger HTTP/TLS reachability signals.
- Docker build now uses a virtualenv for `pip install .` (PEP 668 compliant on Alpine).
- Update check output now includes whether native `caddy upgrade` command is available.

### Changed

- Docker build now installs package with `pip install .` instead of copying Python scripts into `/usr/bin`.
- Runtime entrypoint now executes installed script (`certify-reverse`) via `boot.sh`.
- Docker compose updated to use built image + config mounts only (`.env`, `upstreams.yml`, `/data`).
- Invalid setup errors are now reported in a concise user-facing format, and startup exits cleanly (no endless restart loop for static config errors).
- Project version bumped to `0.3.0`.

### Removed

- `Makefile` (duplicate orchestration surface with `caddy-docker.sh`).

## [0.2.0] - 2026-02-25

### Added

- Optional pinned Caddy version via `.env` (`CADDY_VERSION`, default `latest`).
- New config model:
  - global settings from `.env`,
  - upstream topology from `upstreams.yml` with top-level subdomain keys.
- Verbose diff logging for regenerated files when content changes, logged to stdout and rotating file logger.
- Caddyfile override fallback support:
  - if `/data/Caddyfile.overwrite` exists, runtime uses it and logs explicitly.
- Built-vs-latest Caddy update check command (`--check-updates`).
- Explicit rebuild/update flags (`--rebuild-caddy`, `--update-caddy`; `--force-build` kept as alias).
- Compose override file `docker/docker-compose.caddyfile.yml` to print generated Caddyfile and exit.
- Generated status dashboard (`/data/index.html`) and ACME state JSON (`/data/acme-state.json`) with inline JS/CSS.
- `Makefile` targets for start/stop/restart, update checks, rebuild, Caddyfile print, semver bumping, and tagging.
- Templates:
  - `.env.example`
  - `upstreams.yml.example`

### Changed

- Docker artifacts moved to `docker/`.
- Helper script now operates against compose files in `docker/`.

## [0.1.0] - 2026-02-25

### Added

- Initial Caddy reverse proxy bootstrap tooling.
- Config-driven Caddyfile/dnsmasq generation.
- Internal CA export and service CA directory support.
- Helper scripts for docker operations and status inspection.
