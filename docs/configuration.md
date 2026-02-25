# Configuration Reference

`config.yml` is mounted into the container as `/config.yml`.

## Schema

```yaml
dns_provider: desec
dns_token: "REPLACE_ME"
email: admin@example.com
domain: example.com
upstreams:
  - subdomain: app
    ip: 10.0.0.10
    port: 8080
    scheme: http
    skip_verify: false
    trust_pool: null
    forward_auth_headers: true
    ext_name: null
    ext_params: {}
```

## Top-Level Fields

- `dns_provider`: required, Caddy DNS plugin key (for example `desec`, `cloudflare`, `route53`).
- `dns_token`: required, API token used by the provider plugin.
- `email`: optional, defaults to `admin@example.com`.
- `domain`: required root domain.
- `upstreams`: required list of backend entries.

## Upstream Fields

- `subdomain`: required.
- `ip`: required backend IP.
- `port`: required backend port.
- `scheme`: optional `http` or `https` (default `http`).
- `skip_verify`: optional bool, only relevant for `https`.
- `trust_pool`: optional path to CA bundle file.
- `forward_auth_headers`: optional bool, default `true`.
- `ext_name`: optional trust-extension name (`trust_ext.<ext_name>`).
- `ext_params`: optional object passed into trust extension class.

## Behavior Notes

- If `scheme: https` and no `trust_pool` is given, template logic defaults to:
  - `/data/exported-certs/caddy-internal-ca.pem`.
- If `skip_verify: true`, transport uses `tls_insecure_skip_verify`.
- If `ext_name` is set, `app.py` imports `trust_ext.<ext_name>` and runs `TrustExtension` methods.

## Example: Mixed HTTP/HTTPS

```yaml
dns_provider: desec
dns_token: "REPLACE_ME"
email: admin@example.com
domain: example.com
upstreams:
  - subdomain: app
    ip: 10.0.0.10
    port: 8080
    scheme: http

  - subdomain: secure-api
    ip: 10.0.0.20
    port: 8443
    scheme: https
    skip_verify: false
```

## Operational Security

- Keep `dns_token` out of git.
- Use minimal-scoped provider tokens.
- Rotate tokens on exposure.
