# Changelog

All notable changes to this project are documented here.

## [Unreleased]

## [0.5.2] - 2026-07-18

### Added

- Configurable DNS provider credential field via `CADDY_DNS_PLUGIN_TOKEN_FIELD`
  (default: `api_token`).
- Strict validation for domains, upstream names/hosts, schemes, ports, trust-pool
  paths, extension names, environment keys, and dnsmasq address modes.
- IPv6-literal rendering for reverse-proxy upstream targets.
- Synchronized version regression tests and shell-helper security tests.
- Compose integration tests mount and assert the current checkout source before
  container assertions, preventing stale local images from producing false greens.
- Ruff, Mypy, package-build, and lockfile checks in the release verification path.
- End-user documentation site and deSEC + AdGuard + HTTP server case study.
- `issues.yml` containing larger deferred architecture and integration work.

### Changed

- DNS provider/token values are exported consistently for generated Caddy
  configuration, with configurable provider-specific credential syntax.
- Compose config gives the Caddy service explicit public DNS resolvers for
  DNS-01 propagation checks.
- Version, bump, release-note, and tag helper commands no longer require a
  Docker installation.
- Docker builds now use the Go toolchain already supplied by the configured
  Caddy builder image instead of pulling a redundant moving `golang:alpine` stage.
- Alpine image creation now upgrades the expat runtime consistently and uses
  `py3-virtualenv`, fixing current-base `ensurepip` and `pyexpat` failures.
- The semantic-version bump helper now updates both `pyproject.toml` and
  `certify_reverse.__version__`.
- `verify` now validates synchronized versions, the frozen lockfile, tests,
  lint, type checking, package builds, shell syntax, and both Compose models.

### Fixed

- Prevented crafted upstream names from escaping the `/data` service-directory
  root or injecting invalid Caddy/dnsmasq configuration.
- Caddy plugin detection now requires the exact module name rather than a
  substring match.
- Network timeouts, malformed release responses, and offline update checks no
  longer abort runtime startup.
- Existing CA exports now repair a missing PEM/CRT companion file.
- Internal CA export no longer accepts an intermediate certificate as a root-CA
  fallback.
- Invalid YAML and unsupported upstream fields now produce concise
  `InvalidSetupError` messages.
- Corrected stale importable package version `0.3.5` to the release version.

### Security

- Added a restrictive `.dockerignore` so local secrets, runtime certificate
  data, caches, Git history, and the runtime data directory are not sent to builders.
- `caddy-docker.sh config` redacts token, secret, password, API-key, and
  private-key values in both `.env` and `upstreams.yml` output.
- The status CLI no longer reveals the final characters of the configured DNS
  token.
- Inline dashboard JSON escapes script-closing characters to prevent stored
  script injection through rendered metadata.

## [0.5.1] - 2026-02-25

### Changed

- Favicon routing adjusted to avoid overriding upstream application favicons:
  - project favicon is served for status/static pages,
  - upstream site blocks no longer intercept `/favicon.ico`, so proxied apps can serve their own favicon.

## [0.5.0] - 2026-02-25

### Added

- Configurable Docker builder base image via `.env`:
  - `CADDY_BUILDER_IMAGE` (used as compose build arg for `docker/Dockerfile`).
- Python test suite under `tests/` with:
  - regression coverage for JS template escaping issues,
  - regression coverage ensuring generated Caddyfile does not emit unsupported `pki` options,
  - regression coverage for ANSI-highlight + file-log stripping behavior,
  - config parsing/validation unit tests,
  - CA export behavior tests.
- Container-level integration test (`tests/test_integration_compose.py`) that runs Compose-based Caddyfile generation and auto-skips when Docker Compose is unavailable.
- `caddy-docker.sh verify` now runs unittest discovery (including integration tests with skip semantics) in addition to syntax/compose validation.

### Changed

- `caddy-docker.sh verify` now runs unittest discovery (including integration tests with skip semantics) in addition to syntax/compose validation.
- Improved compatibility with Caddy command variants by removing unsupported trust/export flags and using internal PKI-file export logic.
- Removed unsupported Caddyfile `pki` options from generated config (fixes `root_ca_ttl` parse failures).
- Fixed dashboard template JS interpolation escaping that could crash runtime HTML generation.
- Interactive logs now highlight key values (domain/upstream counts/provider/paths/version recommendation) while rotating file logs remain plain text.
- `./caddy-docker.sh rebuild-caddy` no longer requires a running `caddy` container; it now falls back to a one-shot `docker compose run --rm --no-deps caddy --rebuild-caddy` when service is down.
- Runtime Caddy rebuild now sets writable `HOME`/`XDG_CACHE_HOME`/`GOCACHE`/`GOMODCACHE`/`TMPDIR` under `/data/caddybuild`, fixing non-root cache permission failures like `mkdir /.cache: permission denied`.
- Caddy rebuild is now atomic: builds to a temporary binary first and only replaces `/data/caddy-rebuild` after successful build output.
- `caddy-docker.sh` now derives `CADDY_BUILDER_IMAGE` from `CADDY_VERSION` when unset (e.g. `v2.10.0 -> caddy:2.10.0-builder`).
- `/config/.env` values now override inherited image environment defaults (fixes cases where base image `CADDY_VERSION` prevented requested runtime version from being applied).
- Runtime rebuild now forces `GOTOOLCHAIN=auto` (instead of inheriting `local`) so Go can select/download newer toolchains when required by newer Caddy versions.
- Removed pinned/configurable Go image selection from project config surface; Go toolchain selection is now handled by enforced `GOTOOLCHAIN=auto` during runtime rebuilds.
- Runtime rebuild now sets `XCADDY_SETCAP=0` to prevent non-root `setcap` failures (`CAP_SETFCAP`), relying on container `NET_BIND_SERVICE` capability for low-port binding.
- Generated Caddyfile now removes redundant `header_up X-Forwarded-Host` entries that triggered startup warnings.
- Generated Caddyfile content is now pre-formatted via `caddy fmt` to avoid runtime formatting warnings.
- Caddy runtime now exports writable `HOME`/`XDG_CONFIG_HOME`/`XDG_DATA_HOME`/`XDG_CACHE_HOME` under `/data`, fixing `/.config` and `/.local` permission/storage errors on non-root containers.
- dnsmasq now starts with a guaranteed writable `/data` mount and creates `/data/logs` before launch, fixing missing log-path startup failures.
- dnsmasq now supports optional extra CLI flags via `.env` (`DNSMASQ_EXTRA_ARGS`).
- Added `./caddy-docker.sh reload-dnsmasq` to send `SIGHUP` for dnsmasq config reloads without full stack restart.
- Added crt.sh integration on startup:
  - queries `https://crt.sh/?q=<domain>&output=json`,
  - logs latest matching certificate and derived validity status,
  - writes `/data/crtsh-state.json`.
- Dashboard now loads `/crtsh-state.json` client-side and renders the full crt.sh result set as a dynamic table on page load.
- Added Caddy status probe endpoint `/probe/crtsh` (proxy to `https://crt.sh`) and dashboard live-refresh action using this endpoint to avoid direct browser-to-crt.sh CORS issues.
- dnsmasq wildcard address target is now configurable via `.env` (`DNSMASQ_ADDRESS_IP`) instead of being hardcoded.
- Added `DNSMASQ_ADDRESS_MODE`:
  - `manual` (uses `DNSMASQ_ADDRESS_IP`),
  - `host-src-ip` (derives host source IP from route table with manual fallback).
- `host-src-ip` mode now prefers a host-derived source IP provided by `caddy-docker.sh` (`HOST_DNSMASQ_ADDRESS_IP`) so wildcard DNS targets resolve to host/LAN-reachable addresses instead of container-internal routes.
- `caddy-docker.sh logs` now shows both `caddy` and `dnsmasq` by default; optional service filter supported.
- Bootstrap now skips pre-run `caddy trust` (which requires an active admin endpoint), reducing startup noise.
- Generated Caddyfile is now formatted in-place (`caddy fmt --overwrite`) after write to avoid adapter formatting warnings.
- Dashboard Services table now has dedicated `Ping` and `Cert` columns with automatic async checks on page load and per-result refresh controls.
- Dashboard crt.sh status now includes dedicated refresh control and `Last Queried` timestamp for the currently displayed status result.

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
