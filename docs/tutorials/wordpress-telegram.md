# Tutorial: WordPress + Telegram webhook

This tutorial publishes two services through one certify-reverse instance:

- `wordpress.<DOMAIN>` -> a WordPress container;
- `telegram.<DOMAIN>` -> a minimal Telegram webhook receiver.

The example also includes MariaDB, persistent volumes, health checks, a webhook
secret, and an optional webhook-registration script.

```text
internet or LAN clients
        |
        v
Caddy / certify-reverse
   |              |
   v              v
wordpress:80   telegram-bot:8080
   |
   v
wordpress-db:3306
```

The database never becomes a public upstream.

## What this example teaches

By the end, you will have practiced:

- adding several services to the same Compose project;
- routing by Docker service name instead of container IP;
- keeping application secrets separate from the DNS token;
- checking internal health before testing HTTPS;
- registering a Telegram webhook without printing the bot token;
- cleaning up containers while preserving or removing volumes deliberately.

## 1. Prepare certify-reverse

Start from a working clone and create the main configuration files:

```bash
cp .env.example .env
cp examples/wordpress-telegram/upstreams.yml upstreams.yml
```

Edit the root `.env`:

```env
DOMAIN=example.net
ACME_EMAIL=admin@example.net
DNS_PROVIDER=desec
DNS_TOKEN=REPLACE_WITH_YOUR_REAL_DNS_TOKEN
CADDY_DNS_PLUGIN_TOKEN_FIELD=token
CADDY_VERSION=latest

DNSMASQ_ADDRESS_MODE=manual
DNSMASQ_ADDRESS_IP=192.168.1.20
```

Replace every example value. The DNS token belongs only in the root `.env`.

## 2. Prepare application secrets

Copy the example application environment file:

```bash
cp examples/wordpress-telegram/.env.example \
   examples/wordpress-telegram/.env
```

Generate three independent random values. One portable option is:

```bash
python3 - <<'PY'
import secrets
for label in ("WORDPRESS_DB_PASSWORD", "WORDPRESS_DB_ROOT_PASSWORD", "TELEGRAM_WEBHOOK_SECRET"):
    print(f"{label}={secrets.token_urlsafe(32)}")
PY
```

Paste those values into `examples/wordpress-telegram/.env`.

Leave `TELEGRAM_BOT_TOKEN` as a placeholder until you want to connect a real bot.

!!! warning "Do not reuse secrets"

    The WordPress database password, MariaDB root password, Telegram bot token, DNS
    token, and webhook secret protect different systems. Do not use the same value
    for more than one field.

## 3. Review the upstream configuration

The provided `upstreams.yml` contains:

```yaml
wordpress:
  ip: wordpress
  port: 80
  scheme: http

telegram:
  ip: telegram-bot
  port: 8080
  scheme: http
```

The `ip` values are Compose service names. They work because the overlay adds the
application services to the same default network as Caddy.

## 4. Validate before starting

Preview the Caddyfile:

```bash
./caddy-docker.sh print-caddyfile
```

Confirm that it contains both public hosts:

```text
wordpress.example.net
telegram.example.net
```

Validate the complete Compose model:

```bash
docker compose \
  --env-file examples/wordpress-telegram/.env \
  -f docker/docker-compose.yml \
  -f examples/wordpress-telegram/compose.override.yml \
  config --quiet
```

<div class="result" markdown>
**Expected:** both commands return successfully and no secret value appears in the
printed Caddyfile.
</div>

## 5. Start the complete stack

```bash
docker compose \
  --env-file examples/wordpress-telegram/.env \
  -f docker/docker-compose.yml \
  -f examples/wordpress-telegram/compose.override.yml \
  up -d --build
```

Inspect state:

```bash
docker compose \
  --env-file examples/wordpress-telegram/.env \
  -f docker/docker-compose.yml \
  -f examples/wordpress-telegram/compose.override.yml \
  ps
```

MariaDB may remain in `health: starting` briefly. WordPress waits for the database
health check.

Follow logs in separate terminals:

```bash
./caddy-docker.sh logs --follow caddy
```

```bash
docker compose \
  --env-file examples/wordpress-telegram/.env \
  -f docker/docker-compose.yml \
  -f examples/wordpress-telegram/compose.override.yml \
  logs --follow wordpress telegram-bot wordpress-db
```

## 6. Check the services inside Docker first

Before involving DNS or HTTPS, confirm that Caddy can reach both upstreams.

WordPress:

```bash
docker compose \
  --env-file examples/wordpress-telegram/.env \
  -f docker/docker-compose.yml \
  -f examples/wordpress-telegram/compose.override.yml \
  exec caddy wget -qO- http://wordpress:80/ | head
```

Telegram webhook health endpoint:

```bash
docker compose \
  --env-file examples/wordpress-telegram/.env \
  -f docker/docker-compose.yml \
  -f examples/wordpress-telegram/compose.override.yml \
  exec caddy wget -qO- http://telegram-bot:8080/health
```

<div class="result" markdown>
**Expected:** WordPress returns HTML and the bot returns
`{"ok":true,"service":"telegram-webhook"}`.
</div>

When these checks fail, the problem is inside the Compose stack—not public DNS.

## 7. Test HTTPS routing

Assume the proxy host is `192.168.1.20` and the domain is `example.net`.

WordPress:

```bash
curl --resolve wordpress.example.net:443:192.168.1.20 \
  -I https://wordpress.example.net/
```

Telegram health endpoint:

```bash
curl --resolve telegram.example.net:443:192.168.1.20 \
  https://telegram.example.net/health
```

Open `https://wordpress.example.net` in a browser after normal DNS points the name
to the proxy host. Complete the WordPress installer and create an administrator
account with a strong password.

## 8. Test webhook secret validation locally

Load the secret from the example environment without printing it:

```bash
set -a
. examples/wordpress-telegram/.env
set +a
```

Send a small synthetic update:

```bash
curl --resolve telegram.example.net:443:192.168.1.20 \
  -H "Content-Type: application/json" \
  -H "X-Telegram-Bot-Api-Secret-Token: ${TELEGRAM_WEBHOOK_SECRET}" \
  --data '{"update_id":1,"message":{"chat":{"id":12345},"text":"test"}}' \
  https://telegram.example.net/webhook
```

<div class="result" markdown>
**Expected:** `{"ok":true}` and a log entry containing only the update ID and chat
ID. The example receiver deliberately does not log message text or secrets.
</div>

Try the same request without the secret header:

```bash
curl --resolve telegram.example.net:443:192.168.1.20 \
  -H "Content-Type: application/json" \
  --data '{"update_id":2}' \
  https://telegram.example.net/webhook
```

<div class="result" markdown>
**Expected:** HTTP 403 with `{"ok":false,"error":"invalid secret"}`.
</div>

## 9. Connect a real Telegram bot

Create a bot using BotFather and place its token in:

```text
examples/wordpress-telegram/.env
```

Ensure normal public DNS resolves `telegram.<DOMAIN>` to the proxy and that the
certificate is valid from the public internet. Then run:

```bash
examples/wordpress-telegram/register-webhook.sh
```

The script reads:

- `DOMAIN` from the root `.env`;
- `TELEGRAM_BOT_TOKEN` from the example `.env`;
- `TELEGRAM_WEBHOOK_SECRET` from the example `.env`.

It sends those values directly to Telegram's webhook API and does not echo the bot
token.

Check the receiver logs:

```bash
docker compose \
  --env-file examples/wordpress-telegram/.env \
  -f docker/docker-compose.yml \
  -f examples/wordpress-telegram/compose.override.yml \
  logs --follow telegram-bot
```

The example acknowledges updates but does not reply to messages. Its purpose is to
demonstrate secure ingress and routing, not a complete bot framework.

## 10. Operate the stack

Useful commands:

```bash
./caddy-docker.sh status
./caddy-docker.sh config
./caddy-docker.sh data
./caddy-docker.sh check-updates
```

Application-specific logs:

```bash
docker compose \
  --env-file examples/wordpress-telegram/.env \
  -f docker/docker-compose.yml \
  -f examples/wordpress-telegram/compose.override.yml \
  logs --tail=100 wordpress telegram-bot wordpress-db
```

Back up at least these named volumes before upgrades:

- `wordpress-data`;
- `wordpress-db-data`.

The exact Compose project prefix may be added to the actual volume names. Use
`docker volume ls` to identify them.

## 11. Stop or remove the example

Stop containers but keep data:

```bash
docker compose \
  --env-file examples/wordpress-telegram/.env \
  -f docker/docker-compose.yml \
  -f examples/wordpress-telegram/compose.override.yml \
  stop
```

Remove containers and networks but keep named volumes:

```bash
docker compose \
  --env-file examples/wordpress-telegram/.env \
  -f docker/docker-compose.yml \
  -f examples/wordpress-telegram/compose.override.yml \
  down
```

Remove the example data as well:

```bash
docker compose \
  --env-file examples/wordpress-telegram/.env \
  -f docker/docker-compose.yml \
  -f examples/wordpress-telegram/compose.override.yml \
  down --volumes
```

!!! danger "`--volumes` deletes WordPress and database data"

    Use it only for a disposable tutorial environment or after a verified backup.

## Production follow-up

Before treating this example as production-ready:

- pin container images by digest;
- place WordPress and database backups on a tested schedule;
- protect the status dashboard with network policy or authentication;
- add monitoring independent of the browser dashboard;
- implement real Telegram update handling with replay, rate, and business-logic
  controls;
- review firewall rules for ports 53, 80, and 443;
- rotate all tutorial secrets.
