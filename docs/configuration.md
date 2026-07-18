# Configuration

certify-reverse reads two local files from the repository root and mounts them into
the runtime container:

```text
.env          -> /config/.env
upstreams.yml -> /config/upstreams.yml
```

Both files are intentionally ignored by Git because they describe one deployment
and may contain secrets.

## Start from the examples

```bash
cp .env.example .env
cp upstreams.yml.example upstreams.yml
```

Validate before starting services:

```bash
./caddy-docker.sh print-caddyfile >/tmp/Caddyfile
```

A configuration error stops startup with an actionable message rather than a Python
traceback.

## `.env` reference

### Required settings

| Setting | Example | Purpose |
| --- | --- | --- |
| `DOMAIN` | `example.net` | Base domain used for generated public hosts |
| `DNS_PROVIDER` | `desec` | Caddy DNS plugin name |
| `DNS_TOKEN` | `REPLACE_ME` | Provider API credential used for DNS-01 |

Minimal deSEC example:

```env
DOMAIN=example.net
DNS_PROVIDER=desec
DNS_TOKEN=REPLACE_WITH_REAL_TOKEN
CADDY_DNS_PLUGIN_TOKEN_FIELD=token
```

### Optional settings

| Setting | Default | Meaning |
| --- | --- | --- |
| `ACME_EMAIL` | `admin@example.com` | Contact address sent to the certificate authority |
| `CADDY_VERSION` | `latest` | `latest` or a semantic version such as `v2.10.2` |
| `CADDY_DNS_PLUGIN_TOKEN_FIELD` | provider-aware | Credential directive used inside the DNS plugin block |
| `DNSMASQ_ADDRESS_MODE` | `manual` | How the wildcard DNS target is selected |
| `DNSMASQ_ADDRESS_IP` | `10.0.0.1` | Manual wildcard target address or resolvable hostname |
| `DNSMASQ_EXTRA_ARGS` | empty | Additional dnsmasq command-line flags |
| `CADDY_BUILDER_IMAGE` | derived | Builder image used by the Dockerfile |

### `CADDY_VERSION`

Accepted values:

```env
CADDY_VERSION=latest
CADDY_VERSION=v2.10.2
CADDY_VERSION=2.10.2
CADDY_VERSION=v2.11.0-beta.1
```

Bare semantic versions are normalized with a leading `v`. Option-like or arbitrary
references are rejected.

When an explicit version does not match the installed Caddy binary, certify-reverse
rebuilds Caddy even when the DNS plugin is already present.

`latest` does not force a network-dependent rebuild on every startup. Use:

```bash
./caddy-docker.sh check-updates
```

for an advisory comparison.

### DNS plugin credential field

Provider plugins do not all use the same directive. deSEC expects:

```caddyfile
token {$CADDY_DNS_PLUGIN_TOKEN}
```

Other providers may expect:

```caddyfile
api_token {$CADDY_DNS_PLUGIN_TOKEN}
```

Set the exact identifier documented by the plugin:

```env
CADDY_DNS_PLUGIN_TOKEN_FIELD=api_token
```

The value must be a Caddy identifier. Spaces, punctuation, and injected directives
are rejected.

### dnsmasq address modes

#### Manual

Use the configured address directly:

```env
DNSMASQ_ADDRESS_MODE=manual
DNSMASQ_ADDRESS_IP=192.168.1.20
```

This is the clearest option for a server with a stable LAN address.

#### Host source IP

Prefer a host-derived address supplied by the wrapper, then fall back to the manual
value:

```env
DNSMASQ_ADDRESS_MODE=host-src-ip
DNSMASQ_ADDRESS_IP=192.168.1.20
```

#### Auto

`auto` uses the same detection path and manual fallback:

```env
DNSMASQ_ADDRESS_MODE=auto
DNSMASQ_ADDRESS_IP=192.168.1.20
```

A hostname is accepted for `DNSMASQ_ADDRESS_IP` when it resolves to IPv4 during
startup.

## `upstreams.yml` reference

The file is a top-level mapping. Each key becomes a subdomain.

```yaml
notes:
  ip: notes-app
  port: 8080
  scheme: http
```

With `DOMAIN=example.net`, this creates `notes.example.net`.

### Supported fields

| Field | Required | Default | Meaning |
| --- | --- | --- | --- |
| `ip` | yes | — | IPv4, IPv6, or resolvable hostname/service name |
| `port` | yes | — | Integer from 1 through 65535 |
| `scheme` | no | `http` | `http` or `https` |
| `skip_verify` | no | `false` | Disable TLS verification for this upstream |
| `trust_pool` | no | generated CA | Absolute path to a PEM trust pool |
| `forward_auth_headers` | no | `true` | Add the generated real-client header behavior |
| `ext_name` | no | — | Python trust-extension module name |
| `ext_params` | no | `{}` | Mapping passed to the trust extension |

Unknown fields fail validation. This catches misspellings instead of silently
ignoring them.

## Common upstream examples

### HTTP service on the same Compose network

```yaml
app:
  ip: app
  port: 8080
  scheme: http
```

This is the preferred tutorial pattern. Docker DNS resolves the service name.

### HTTP service on another LAN host

```yaml
printer:
  ip: 192.168.1.45
  port: 631
  scheme: http
```

Ensure the Caddy container can route to that address and that the host firewall
allows the connection.

### Hostname target

```yaml
storage:
  ip: storage.internal.example
  port: 9000
  scheme: http
```

The hostname must resolve inside the Caddy container.

### IPv6 target

```yaml
metrics:
  ip: 2001:db8::20
  port: 9090
  scheme: http
```

certify-reverse adds the brackets required in the rendered proxy URL.

### HTTPS upstream using the exported internal CA

```yaml
secure-app:
  ip: secure-app
  port: 8443
  scheme: https
```

Without `skip_verify` or an explicit `trust_pool`, the generated transport points to:

```text
/data/exported-certs/caddy-internal-ca.pem
```

Export the CA after Caddy has initialized its internal PKI:

```bash
./caddy-docker.sh app --export-certs
```

### HTTPS upstream with an explicit trust pool

```yaml
vendor-api:
  ip: vendor-api.internal
  port: 443
  scheme: https
  trust_pool: /data/trust/vendor-root-ca.pem
```

The path must be absolute and readable inside the container.

### Temporary insecure HTTPS upstream

```yaml
legacy:
  ip: legacy-device
  port: 443
  scheme: https
  skip_verify: true
```

!!! warning "Treat `skip_verify` as a migration aid"

    It encrypts traffic but does not authenticate the upstream. Replace it with a
    valid trust pool as soon as possible.

### Disable forwarding behavior

```yaml
privacy-sensitive-service:
  ip: service
  port: 8080
  forward_auth_headers: false
```

Use this only when the upstream should not receive the generated client-address
header.

## Naming rules

Subdomain keys are normalized to lowercase without a trailing dot.

These collide and are rejected:

```yaml
App:
  ip: one
  port: 8080

app.:
  ip: two
  port: 8081
```

Names cannot contain path separators, whitespace, Caddyfile control characters, or
invalid DNS labels. The validation also prevents a service name from escaping its
runtime data directory.

Avoid reserved generated hosts:

- `status.<DOMAIN>`;
- `internal-ca.<DOMAIN>`.

## Complete multi-service example

```yaml
blog:
  ip: wordpress
  port: 80

bot:
  ip: telegram-bot
  port: 8080

files:
  ip: 192.168.1.50
  port: 8443
  scheme: https
  trust_pool: /data/trust/files-ca.pem

legacy-camera:
  ip: 192.168.1.60
  port: 443
  scheme: https
  skip_verify: true
  forward_auth_headers: false
```

Check the result:

```bash
./caddy-docker.sh print-caddyfile >/tmp/Caddyfile
sed -n '1,220p' /tmp/Caddyfile
```

## Environment precedence

Values loaded from the mounted `/config/.env` override inherited container image
environment defaults. This ensures the deployment file—not a stale image setting—
controls the requested Caddy version and provider configuration.

## Secret handling

Use the redacted configuration view when sharing diagnostics:

```bash
./caddy-docker.sh config
```

Do not share raw `.env`, Docker inspection output containing environment values, or
the generated process environment.

For production:

- restrict `.env` permissions;
- use a provider token limited to the required zone and operations;
- rotate credentials on operator changes;
- avoid shell history containing tokens;
- keep backups encrypted.

## Validation checklist

Before starting:

```bash
./caddy-docker.sh print-caddyfile >/tmp/Caddyfile
docker compose -f docker/docker-compose.yml config --quiet
```

After starting:

```bash
./caddy-docker.sh status
./caddy-docker.sh logs --follow caddy
./caddy-docker.sh config
```

When a setting is rejected, copy the exact error text and compare it with the field
rules above before changing unrelated networking or certificate settings.
