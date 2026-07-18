#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)

if [ ! -f "$ROOT_DIR/.env" ]; then
  echo "missing root .env" >&2
  exit 1
fi
if [ ! -f "$SCRIPT_DIR/.env" ]; then
  echo "missing examples/wordpress-telegram/.env" >&2
  exit 1
fi

read_value() {
  key=$1
  file=$2
  sed -n "s/^${key}=//p" "$file" | tail -n 1
}

DOMAIN=$(read_value DOMAIN "$ROOT_DIR/.env")
TOKEN=$(read_value TELEGRAM_BOT_TOKEN "$SCRIPT_DIR/.env")
SECRET=$(read_value TELEGRAM_WEBHOOK_SECRET "$SCRIPT_DIR/.env")

if [ -z "$DOMAIN" ] || [ -z "$TOKEN" ] || [ -z "$SECRET" ]; then
  echo "DOMAIN, TELEGRAM_BOT_TOKEN, and TELEGRAM_WEBHOOK_SECRET must be set" >&2
  exit 1
fi

curl --fail --silent --show-error \
  --request POST \
  --data-urlencode "url=https://telegram.${DOMAIN}/webhook" \
  --data-urlencode "secret_token=${SECRET}" \
  "https://api.telegram.org/bot${TOKEN}/setWebhook"
printf '\n'
