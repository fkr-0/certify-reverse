# Case Study: deSEC + AdGuard + Python HTTP Service

This walkthrough shows a realistic local setup using:

- DNS provider: `desec`
- One backend from `python3 -m http.server`
- One backend from AdGuard Home (Docker)
- `certify-reverse` for wildcard DNS + HTTPS reverse proxy

All tokens/hostnames here are examples.

## 1) Prepare config files

```bash
cp .env.example .env
cp upstreams.yml.example upstreams.yml
```

Edit `.env`:

```env
DOMAIN=fkr.dev
ACME_EMAIL=ops@example.invalid
DNS_PROVIDER=desec
DNS_TOKEN=desec_fake_token_1234567890

# Optional pin
CADDY_VERSION=v2.10.2

# Wildcard DNS target for local clients
DNSMASQ_ADDRESS_MODE=manual
DNSMASQ_ADDRESS_IP=10.0.0.1
```

## 2) Start demo backend 1 (python http.server)

```bash
mkdir -p /tmp/demo-site
cat >/tmp/demo-site/index.html <<'HTML'
<h1>python demo service</h1>
<p>served by python3 -m http.server</p>
HTML
python3 -m http.server 8080 --bind 0.0.0.0 --directory /tmp/demo-site
```

Keep it running in a separate terminal.

## 3) Start demo backend 2 (AdGuard Home)

```bash
docker run -d \
  --name adguardhome \
  --restart unless-stopped \
  -v adguard-work:/opt/adguardhome/work \
  -v adguard-conf:/opt/adguardhome/conf \
  -p 3000:3000 \
  -p 8081:80 \
  adguard/adguardhome:latest
```

Notes:
- Port `8081` exposes AdGuard web UI on the host.
- First-run wizard is usually on `http://localhost:3000`.

## 4) Configure upstreams

Edit `upstreams.yml`:

```yaml
demo:
  ip: 10.0.0.1
  port: 8080
  scheme: http

adguard:
  ip: 10.0.0.1
  port: 8081
  scheme: http
```

If your host IP is different, replace `10.0.0.1`.

## 5) Start certify-reverse stack

```bash
./caddy-docker.sh start
```

Check runtime:

```bash
./caddy-docker.sh status
./caddy-docker.sh logs --follow
./caddy-docker.sh print-caddyfile
```

## 6) Test routed HTTPS endpoints

From a client that resolves `*.fkr.dev` to your reverse-proxy host:

- `https://demo.fkr.dev`
- `https://adguard.fkr.dev`
- `https://status.fkr.dev`

Quick probe:

```bash
curl -kI https://demo.fkr.dev
curl -kI https://adguard.fkr.dev
```

(`-k` is only for initial local trust/bootstrap testing.)

## 7) Trust internal CA for local clients (optional)

Export cert bundle:

```bash
./caddy-docker.sh app --export-certs
```

Then distribute `caddy-internal-ca.pem`/`.crt` to local clients or upstream containers as needed.

## 8) Operational tips

- Rebuild Caddy with provider plugin:
```bash
./caddy-docker.sh rebuild-caddy
```
- Re-check available upgrades:
```bash
./caddy-docker.sh check-updates
```
- Reload dnsmasq after DNS-related changes:
```bash
./caddy-docker.sh reload-dnsmasq
```

## 9) Cleanup demo services

```bash
docker rm -f adguardhome
docker volume rm adguard-work adguard-conf
pkill -f "python3 -m http.server 8080" || true
```
