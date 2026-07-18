# WordPress + Telegram example

This directory supports the full tutorial at
[`docs/tutorials/wordpress-telegram.md`](../../docs/tutorials/wordpress-telegram.md).

Files:

- `compose.override.yml`: adds MariaDB, WordPress, and the Telegram webhook receiver
  to the base certify-reverse Compose project;
- `.env.example`: non-secret application environment template;
- `upstreams.yml`: matching certify-reverse upstream configuration;
- `telegram-bot/`: dependency-free webhook receiver example;
- `register-webhook.sh`: optional Telegram webhook registration helper.

Quick preparation:

```bash
cp examples/wordpress-telegram/.env.example examples/wordpress-telegram/.env
cp examples/wordpress-telegram/upstreams.yml upstreams.yml
```

Start only after editing both the root `.env` and the example `.env`:

```bash
docker compose \
  --env-file examples/wordpress-telegram/.env \
  -f docker/docker-compose.yml \
  -f examples/wordpress-telegram/compose.override.yml \
  up -d --build
```

The example `.env` is ignored by Git. Never put real DNS or Telegram tokens in the
committed `.env.example` file.
