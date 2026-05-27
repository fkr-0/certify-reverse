# Getting Started

## Prerequisites

- Docker with `docker compose`
- A DNS provider token supported by `caddy-dns`
- Linux host recommended for local DNS override flow

## 1) Configure Runtime

```bash
cp .env.example .env
cp upstreams.yml.example upstreams.yml
```

Edit `.env` with at least:

- `DOMAIN`
- `DNS_PROVIDER`
- `DNS_TOKEN`
- `ACME_EMAIL`

## 2) Define Upstreams

`upstreams.yml` maps subdomains to targets:

```yaml
app:
  ip: 10.0.0.10
  port: 8080
  scheme: http
```

## 3) Start

```bash
./caddy-docker.sh start
```

## 4) Validate

```bash
./caddy-docker.sh status
./caddy-docker.sh print-caddyfile
./caddy-docker.sh logs --follow
```

## 5) DNS for Clients

If using local wildcard DNS via dnsmasq, point client DNS to the host running this stack.
