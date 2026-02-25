# Architecture

## Components

- `caddy` container:
  - Runs `boot.sh` then `app.py`.
  - Builds and runs Caddy with DNS provider plugin.
  - Owns generated configs and cert artifacts in `/data`.
- `dnsmasq` container:
  - Serves wildcard DNS resolution for the configured domain.
  - Uses generated `/data/dnsmasq.conf`.

## Control Plane

`app.py` does all orchestration:
- parses `config.yml` into dataclasses,
- validates/ensures Caddy binary with required DNS module,
- renders Caddy and dnsmasq config files,
- exports Caddy internal CA certificates,
- copies CA certs into per-service directories,
- optionally generates service certs for HTTPS upstreams,
- replaces itself with Caddy process (`os.execvp`).

## Generated Artifacts

Primary artifacts in `/data`:
- `caddy-rebuild`: generated Caddy binary.
- `Caddyfile`: active runtime config.
- `dnsmasq.conf`: wildcard resolver config.
- `logs/app.log`: bootstrap logs (rotating file handler).
- `exported-certs/`: internal CA exports for upstream trust.
- `<service>/`: per-service CA cert copies + README.

## TLS Model

External TLS:
- Caddy handles public cert automation using DNS-01 ACME.

Internal TLS:
- For `https` upstreams, Caddy uses trust pool configuration:
  - explicit `trust_pool` path when configured,
  - otherwise exported internal CA at `/data/exported-certs/caddy-internal-ca.pem`.
- `skip_verify` disables cert validation and should be avoided.

## Process Boundaries

- Runtime inside container depends on Alpine packages installed by `boot.sh`.
- `app.py` expects config path `/config.yml`.
- `status.py` imports config/constants from `app.py` and reads `/data`.

## Failure Surfaces

- DNS provider plugin build failure (`xcaddy`).
- Invalid/missing `config.yml`.
- Missing DNS token or provider mismatch.
- Internal CA unavailable early in startup (handled with warnings/fallback).
- Upstream HTTPS verification failures when trust bundles are wrong.
