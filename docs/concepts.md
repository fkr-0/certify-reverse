# Core concepts

This page explains the vocabulary used throughout certify-reverse. You do not need
to know Caddy or ACME before starting.

## Reverse proxy

A reverse proxy accepts a request for a public hostname and sends it to an internal
service.

```text
https://blog.example.net  ->  Caddy  ->  wordpress:80
https://bot.example.net   ->  Caddy  ->  telegram-bot:8080
```

The browser sees one HTTPS endpoint. The services can stay on a private Docker
network and do not each need to manage certificates or expose host ports.

## Domain and subdomain

`example.net` is the base domain. `blog.example.net` and `bot.example.net` are
subdomains.

In certify-reverse:

- `DOMAIN=example.net` sets the base domain;
- the top-level keys in `upstreams.yml` become subdomains;
- a key named `blog` produces `blog.example.net`;
- a key named `status` would conflict with the generated dashboard host and should
  be avoided.

## DNS

DNS translates names into addresses. Two DNS jobs are involved here:

1. **Public DNS validation** proves to a certificate authority that you control the
   domain.
2. **Client name resolution** tells a browser which machine should receive traffic
   for `blog.example.net`.

Those jobs are related but not identical.

### Public DNS-01 validation

Caddy uses the DNS provider token to create a temporary TXT record. The certificate
authority sees that record and issues a certificate. This works even when the web
service is not publicly reachable during validation.

```text
Caddy -> DNS provider API -> temporary _acme-challenge TXT record
      -> certificate authority checks TXT record
      -> certificate is issued
```

### Client name resolution

After a certificate exists, clients still need `blog.example.net` to resolve to the
proxy host.

Common choices are:

- normal public A/AAAA records;
- router or internal DNS records;
- the bundled dnsmasq wildcard response for a LAN;
- temporary `curl --resolve` checks during setup.

## DNS provider plugin

Each DNS provider has a different API. Caddy uses provider-specific plugins such as
`dns.providers.desec`.

certify-reverse builds a Caddy binary containing the selected plugin. The provider
name comes from `DNS_PROVIDER`.

Some plugins call their credential `token`; others call it `api_token`. The optional
`CADDY_DNS_PLUGIN_TOKEN_FIELD` setting controls the generated Caddyfile directive.
Known defaults are applied where the project has verified them.

## ACME and certificates

ACME is the protocol Caddy uses to request and renew HTTPS certificates.

A certificate binds a hostname to a cryptographic key. When a browser opens
`https://blog.example.net`, the certificate lets the browser verify that the server
is authorized for that hostname.

certify-reverse manages two distinct trust situations:

- **Browser-facing certificates** obtained through DNS-01;
- **Internal CA certificates** used when Caddy connects to an HTTPS upstream that
  trusts Caddy's internal certificate authority.

## Upstream

An upstream is the service behind Caddy.

```yaml
blog:
  ip: wordpress
  port: 80
  scheme: http
```

This means:

- public host: `blog.<DOMAIN>`;
- Docker or network target: `wordpress`;
- target port: `80`;
- connection from Caddy to the service: plain HTTP.

The `ip` field may contain an IPv4 address, IPv6 address, or resolvable hostname.
When services share the same Compose network, service names are usually clearer and
more stable than container IP addresses.

## Docker Compose network

Services started by the same Compose project share a default network and can resolve
one another by service name.

That is why the tutorials use targets such as `wordpress` and `telegram-bot` rather
than hard-coded addresses.

```text
Compose network
├── caddy
├── wordpress
├── wordpress-db
└── telegram-bot
```

The database does not need to be an upstream. Only the WordPress container needs to
reach it.

## dnsmasq

The bundled dnsmasq service can answer every hostname below your domain with one
address:

```text
*.example.net -> 192.168.1.20
```

That is useful on a private LAN. It is not mandatory when public DNS already points
to the proxy host.

Port 53 is commonly already used by a router, system resolver, Pi-hole, AdGuard Home,
or another DNS server. Decide deliberately which service owns port 53 before
starting dnsmasq.

## Dashboard

The generated dashboard at `status.<DOMAIN>` is an operator view. It shows configured
services, browser-level reachability probes, certificate-transparency information,
and generated ACME state.

It is useful for setup and diagnosis, but it is not a full monitoring platform. In
particular, browser TLS checks cannot inspect the peer certificate chain directly.

## Generated files

The runtime writes state below `caddy-data/`, mounted as `/data` in the container.
Important files include:

| File | Purpose |
| --- | --- |
| `Caddyfile` | Generated reverse-proxy configuration |
| `dnsmasq.conf` | Generated wildcard DNS configuration |
| `index.html` | Generated status dashboard |
| `acme-state.json` | Browser-readable ACME summary |
| `crtsh-state.json` | Cached certificate-transparency result |
| `exported-certs/` | Exported internal root CA files |
| `logs/app.log` | Rotating bootstrap log |

## A complete request path

For `https://blog.example.net`:

1. The client resolves `blog.example.net` to the proxy host.
2. The client connects to host port 443.
3. Caddy selects the `blog.example.net` site block.
4. Caddy presents the certificate obtained through DNS-01.
5. Caddy forwards the request to the configured upstream.
6. The upstream response returns through Caddy to the client.

Once this model is clear, the [15-minute quickstart](getting-started.md) becomes much
easier to reason about.
