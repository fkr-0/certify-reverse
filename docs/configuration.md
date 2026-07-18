# Configuration (v0.5.4)

## Files

- `.env`: global settings and secrets.
- `upstreams.yml`: upstream topology.

## `.env` keys

Required:
- `DNS_PROVIDER`
- `DNS_TOKEN`
- `DOMAIN`

Optional:
- `ACME_EMAIL` (default `admin@example.com`)
- `CADDY_VERSION` (default `latest`; otherwise a semantic version such as `v2.10.0`)
- `CADDY_DNS_PLUGIN_TOKEN_FIELD` (provider-aware; deSEC defaults to `token`,
  unknown providers fall back to `api_token`)
- `DNSMASQ_ADDRESS_MODE` (`manual`, `host-src-ip`, or `auto`)
- `DNSMASQ_ADDRESS_IP` (valid IPv4 address or resolvable hostname)

## `upstreams.yml` schema

Top-level keys are subdomains.

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

Supported fields per subdomain object:
- `ip` (required IPv4, IPv6, or hostname target)
- `port` (required integer, `1..65535`)
- `scheme` (`http`/`https`, default `http`)
- `skip_verify` (default `false`)
- `trust_pool` (optional absolute path)
- `forward_auth_headers` (default `true`)
- `ext_name` (optional trust extension)
- `ext_params` (optional map)

Top-level keys are validated DNS subdomains and cannot contain path separators,
whitespace, or Caddyfile control characters. Unknown fields and malformed YAML
fail startup with a concise configuration error. Names are normalized to
lowercase without a trailing dot, and normalization collisions are rejected.

An explicitly pinned `CADDY_VERSION` is checked against the installed binary on
startup. A mismatch triggers a rebuild even when the configured DNS plugin is
already present. `latest` does not force a network-dependent rebuild on every
startup; use `check-updates` for advisory release discovery.
