# Architecture (v0.3.0)

## Packaging

Python code is packaged under `src/certify_reverse` and installed into container image with `pip install .`.

Console scripts:
- `certify-reverse` -> main runtime CLI
- `certify-reverse-status` -> status viewer

## Runtime flow

1. Container entrypoint runs `boot.sh`.
2. `boot.sh` executes `certify-reverse`.
3. App reads env/upstream config files under `/config`.
4. App optionally rebuilds Caddy binary with required DNS plugin.
5. App renders config/status artifacts under `/data`.
6. App may switch to `/data/Caddyfile.overwrite` if present.
7. App execs Caddy as PID 1.

## Idempotency profile

Idempotent:
- deterministic rendering for fixed inputs,
- no rebuild if plugin/binary already satisfies requirements.

Non-fully-idempotent:
- `latest` version pin is intentionally time-variable,
- update check depends on live GitHub API response.
