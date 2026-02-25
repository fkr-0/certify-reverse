# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project aims to follow Semantic Versioning.

## [Unreleased]

### Added

- `config.yml.example` as the canonical safe config template.
- `Makefile` with operational targets (`start`, `stop`, `restart`, `logs`, `status`, `build`, `down`, `clean`, `verify`).
- Semantic version targets in `Makefile` (`version`, `bump-patch`, `bump-minor`, `bump-major`, `release-note`).
- Expanded README coverage for architecture, features, usage, and idempotency/configuration guidance.
- Initial changelog file.

### Changed

- Runtime plugin build path now uses `xcaddy build latest` with `GOTOOLCHAIN=auto` for provider compatibility.
- `boot.sh` now installs `go`, required for runtime `xcaddy` plugin builds.
- `config.yml` moved to ignored local runtime config model.

## [0.1.0] - 2026-02-25

### Added

- Initial Caddy reverse proxy bootstrap tooling.
- Config-driven Caddyfile/dnsmasq generation.
- Internal CA export and service CA directory support.
- Helper scripts for docker operations and status inspection.
