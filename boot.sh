#!/usr/bin/env sh

set -e

echo "▶️  Installing runtime deps (root, once)…"
apk add --no-cache \
  dnsmasq \
  openssh-client rsync \
  curl jq git \
  python3 py3-pip py3-yaml \
  logrotate tzdata \
  su-exec libcap openssl

# ----- create dedicated user/group --------------------------------
echo '▶️  Adding lower priv user "app"…'
adduser -D -h /home/app -s /sbin/nologin app || echo 'user "app" lready existing, OK'
chown -R app:app /data # /config /app /root
app caddy
# ------------------------------------------------------------------
# dropping privileges
# su-exec app /bin/sh -c 'app caddy'
