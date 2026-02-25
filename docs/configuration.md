# Configuration (v0.3.0)

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
- `CADDY_VERSION` (default `latest`)

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
- `ip` (required)
- `port` (required)
- `scheme` (`http`/`https`, default `http`)
- `skip_verify` (default `false`)
- `trust_pool` (optional path)
- `forward_auth_headers` (default `true`)
- `ext_name` (optional trust extension)
- `ext_params` (optional map)
