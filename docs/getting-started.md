# 15-minute quickstart

This walkthrough starts one disposable HTTP service beside certify-reverse and
publishes it as `hello.<your-domain>`.

You will create two configuration files, start the Compose stack with a small demo
overlay, validate the generated Caddyfile, and make one HTTPS request.

## Before you begin

You need:

- Docker with `docker compose`;
- a domain you control;
- a DNS API token for a supported `caddy-dns` provider;
- ports 80 and 443 free on the machine;
- a shell in the repository root.

Check Docker first:

```bash
docker version
docker compose version
```

<div class="result" markdown>
**Expected:** both commands print version information and return successfully.
</div>

!!! warning "This quickstart needs a real DNS token"

    DNS-01 validation changes a temporary TXT record in your domain. Example tokens
    in this guide are deliberately invalid. Never commit your real `.env` file.

## 1. Create local configuration

Copy the templates:

```bash
cp .env.example .env
cp upstreams.yml.example upstreams.yml
```

Open `.env` and replace the example values. For deSEC, a minimal file looks like:

```env
DOMAIN=example.net
ACME_EMAIL=admin@example.net
DNS_PROVIDER=desec
DNS_TOKEN=REPLACE_WITH_YOUR_REAL_TOKEN
CADDY_DNS_PLUGIN_TOKEN_FIELD=token
CADDY_VERSION=latest

# The quickstart does not require dnsmasq for its first curl test.
# Keep a valid placeholder address so configuration validation succeeds.
DNSMASQ_ADDRESS_MODE=manual
DNSMASQ_ADDRESS_IP=192.168.1.20
```

Replace:

- `example.net` with your domain;
- the email address with an address you monitor;
- `REPLACE_WITH_YOUR_REAL_TOKEN` with your DNS provider token;
- `192.168.1.20` with the proxy host's LAN address if you later use dnsmasq.

!!! tip "Using a provider other than deSEC"

    Change `DNS_PROVIDER` and check that provider plugin's Caddyfile syntax. Many
    plugins use `api_token`, while deSEC uses `token`.

## 2. Describe the demo upstream

Replace the contents of `upstreams.yml` with:

```yaml
hello:
  ip: demo
  port: 8080
  scheme: http
```

The name `demo` is a Docker Compose service from the quickstart overlay. Caddy can
resolve it because both containers share the same Compose network.

Validate the YAML visually:

- `hello` has no leading spaces;
- `ip`, `port`, and `scheme` are indented by two spaces;
- the port is an integer, not quoted text.

## 3. Preview the generated configuration

Before starting the long-running services, ask the one-shot container to render the
Caddyfile:

```bash
./caddy-docker.sh print-caddyfile
```

Look for blocks similar to:

```caddyfile
hello.example.net {
    tls {
        dns {$CADDY_DNS_PLUGIN} {
            token {$CADDY_DNS_PLUGIN_TOKEN}
        }
    }
    reverse_proxy http://demo:8080
}
```

The exact formatting may differ because Caddy formats the generated file.

<div class="result" markdown>
**Expected:** the command exits successfully, prints configuration to stdout, and
never prints the DNS token.
</div>

## 4. Start certify-reverse and the demo service

Use the base Compose model plus the quickstart overlay:

```bash
docker compose \
  -f docker/docker-compose.yml \
  -f examples/quickstart/compose.override.yml \
  up -d
```

Watch the logs:

```bash
./caddy-docker.sh logs --follow
```

The first startup may take longer because certify-reverse builds Caddy with the DNS
provider plugin. Watch for these broad stages:

1. configuration loaded;
2. Caddy plugin checked or built;
3. Caddyfile and dashboard written;
4. DNS-01 challenge attempted;
5. Caddy started.

Press ++ctrl+c++ to stop following logs; the containers keep running.

## 5. Check container state

```bash
./caddy-docker.sh status
```

You can also inspect the demo directly inside the Compose network:

```bash
docker compose \
  -f docker/docker-compose.yml \
  -f examples/quickstart/compose.override.yml \
  exec caddy wget -qO- http://demo:8080
```

<div class="result" markdown>
**Expected:** the response contains `Hello from certify-reverse`.
</div>

If this internal request fails, fix Docker networking before investigating DNS or
certificates.

## 6. Test HTTPS without changing client DNS

Find the proxy host address clients should use. On Linux, this commonly works:

```bash
ip -4 route get 1.1.1.1 | awk '{for (i=1; i<=NF; i++) if ($i == "src") {print $(i+1); exit}}'
```

Assume it prints `192.168.1.20`. Test the public hostname while overriding DNS only
for this curl invocation:

```bash
curl --resolve hello.example.net:443:192.168.1.20 \
  https://hello.example.net/
```

Replace both the hostname and IP address.

<div class="result" markdown>
**Expected:** curl prints the demo HTML without `-k`. That confirms name selection,
HTTPS certificate validation, Caddy routing, and upstream connectivity.
</div>

If the certificate is still being issued, inspect logs and retry after the DNS-01
challenge completes.

## 7. Open the dashboard

Test the dashboard the same way:

```bash
curl --resolve status.example.net:443:192.168.1.20 \
  -I https://status.example.net/
```

For a browser, configure normal DNS first or add temporary explicit host entries.
See [Core concepts: client name resolution](concepts.md#client-name-resolution).

The dashboard lets you:

- run reachability checks;
- inspect the latest crt.sh snapshot;
- view ACME state;
- see built and requested Caddy versions.

## 8. Optional: enable LAN wildcard DNS

The included dnsmasq service can answer all names below your domain with the proxy
host address.

1. Set `DNSMASQ_ADDRESS_IP` to the proxy host's LAN address.
2. Point a test client or your router's DHCP DNS setting to that host.
3. Reload dnsmasq:

```bash
./caddy-docker.sh reload-dnsmasq
```

Check resolution from the client:

```bash
nslookup hello.example.net 192.168.1.20
```

!!! caution "Port 53 ownership"

    Do not run the bundled dnsmasq beside another host DNS service on the same port.
    Pi-hole, AdGuard Home, systemd-resolved, and router software may already own it.

## 9. Clean up the demo

Stop the stack created with the overlay:

```bash
docker compose \
  -f docker/docker-compose.yml \
  -f examples/quickstart/compose.override.yml \
  down
```

The generated runtime data remains in `caddy-data/`. Keep it for the next start or
remove it only when you intentionally want to discard generated certificates and
state.

## What you have learned

You have now exercised the complete path:

```text
curl/browser -> HTTPS on Caddy -> demo:8080 -> response
                    |
                    +-> DNS provider API for certificate validation
```

Continue with:

- [Core concepts](concepts.md) for a deeper model;
- [Configuration](configuration.md) for multiple or HTTPS upstreams;
- [WordPress + Telegram](tutorials/wordpress-telegram.md) for a realistic stack;
- [Troubleshooting](troubleshooting.md) when a step does not match the expected result.
