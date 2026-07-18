# Operations

This page is organized around common operator tasks. For a complete command list,
see the [Command reference](cli-reference.md).

## Daily checks

A small daily check can be:

```bash
./caddy-docker.sh status
./caddy-docker.sh logs
./caddy-docker.sh check-updates
```

Also open `https://status.<DOMAIN>` and run all service checks.

Look for:

- containers that are restarting or stopped;
- repeated DNS challenge failures;
- upstream connection errors;
- disk space pressure under `caddy-data/`;
- a Caddy update recommendation;
- certificate snapshot errors.

## Start, stop, and restart

Start:

```bash
./caddy-docker.sh start
```

Stop without removing containers:

```bash
./caddy-docker.sh stop
```

Restart existing containers:

```bash
./caddy-docker.sh restart
```

Remove containers and the project network:

```bash
./caddy-docker.sh down
```

`down` is usually safer than `clean` because it does not intentionally remove
volumes or prune unrelated Docker state.

## Follow logs

Both services:

```bash
./caddy-docker.sh logs --follow
```

Only Caddy:

```bash
./caddy-docker.sh logs --follow caddy
```

Only dnsmasq:

```bash
./caddy-docker.sh logs --follow dnsmasq
```

Press ++ctrl+c++ to stop following. The service continues running.

The application also writes rotating logs to:

```text
caddy-data/logs/app.log
```

## Add a service safely

1. Add one entry to `upstreams.yml`.
2. Preview the Caddyfile:

```bash
./caddy-docker.sh print-caddyfile >/tmp/Caddyfile
```

3. Confirm Caddy can resolve and reach the target.
4. Restart the stack:

```bash
./caddy-docker.sh restart
```

5. Follow Caddy logs and test with `curl --resolve` before changing shared DNS.
6. Run the service checks in the dashboard.

Example:

```yaml
wiki:
  ip: wiki
  port: 3000
  scheme: http
```

If `wiki` is a Docker service, ensure it shares the same Compose network as Caddy.

## Change an upstream address or port

Edit `upstreams.yml`, preview the generated configuration, then restart:

```bash
./caddy-docker.sh print-caddyfile >/tmp/Caddyfile
./caddy-docker.sh restart
./caddy-docker.sh logs --follow caddy
```

A changed upstream does not normally require rebuilding Caddy. Rebuilds are for
Caddy versions or DNS provider plugins.

## Change the DNS provider

1. Create a restricted token at the new provider.
2. Update `DNS_PROVIDER`, `DNS_TOKEN`, and when necessary
   `CADDY_DNS_PLUGIN_TOKEN_FIELD`.
3. Force a plugin rebuild:

```bash
./caddy-docker.sh rebuild-caddy
```

4. Validate the generated Caddyfile.
5. Watch DNS-01 challenge logs closely.
6. Revoke the old provider token after the migration is verified.

Changing providers is a security-sensitive operation because both old and new tokens
may remain valid during the transition.

## Pin or upgrade Caddy

Check current state:

```bash
./caddy-docker.sh check-updates
```

Set an explicit version in `.env`:

```env
CADDY_VERSION=v2.10.2
```

Then restart or rebuild:

```bash
./caddy-docker.sh rebuild-caddy
```

certify-reverse builds to a temporary binary and replaces the active file only after
a successful build.

After an upgrade:

```bash
./caddy-docker.sh print-caddyfile >/tmp/Caddyfile
./caddy-docker.sh status
./caddy-docker.sh logs
```

Test every important route, not only the dashboard.

## Reload dnsmasq

After changing wildcard DNS target settings:

```bash
./caddy-docker.sh reload-dnsmasq
```

Confirm from a client that uses this dnsmasq instance:

```bash
nslookup app.example.net 192.168.1.20
```

Replace the hostname and DNS server address.

If the result is wrong, inspect:

```bash
./caddy-docker.sh data
./caddy-docker.sh logs --follow dnsmasq
```

## Export and distribute the internal CA

Caddy must initialize its internal PKI before export files exist.

Export:

```bash
./caddy-docker.sh app --export-certs
```

Generated public trust files appear below:

```text
caddy-data/exported-certs/
```

Inspect the certificate:

```bash
openssl x509 \
  -in caddy-data/exported-certs/caddy-internal-ca.pem \
  -noout -subject -issuer -dates -fingerprint -sha256
```

Distribute only the public CA certificate. Never distribute a private CA key.

The generated endpoint also serves the public files:

```text
https://internal-ca.<DOMAIN>/cert/caddy-internal-ca.pem
https://internal-ca.<DOMAIN>/cert/caddy-internal-ca.crt
```

Protect access according to your network policy even though root CA certificates are
public trust material.

## Back up runtime state

Important state is under `caddy-data/`. Back it up while preserving permissions.

Example local archive:

```bash
tar --xattrs --acls -czf \
  "certify-reverse-data-$(date +%F).tar.gz" \
  caddy-data/
```

Store backups away from the host and protect them as sensitive because runtime data
may contain private keys and service certificates.

Also back up application volumes independently. certify-reverse does not back up
WordPress, databases, or other upstream data.

## Restore runtime state

1. Stop the stack:

```bash
./caddy-docker.sh stop
```

2. Move the current directory aside rather than deleting it:

```bash
mv caddy-data "caddy-data.before-restore.$(date +%s)"
```

3. Extract the backup in the repository root.
4. Check ownership and permissions.
5. Start and inspect logs:

```bash
./caddy-docker.sh start
./caddy-docker.sh logs --follow caddy
```

6. Test routes and certificate behavior before deleting the pre-restore copy.

## Inspect generated state

Redacted configuration plus generated-file summary:

```bash
./caddy-docker.sh config
```

Generated files and logs:

```bash
./caddy-docker.sh data
```

Inside the container:

```bash
./caddy-docker.sh shell
ls -la /data
```

Use the shell for diagnosis, not permanent manual changes. Generated files can be
replaced on restart.

## Emergency Caddyfile override

If `caddy-data/Caddyfile.overwrite` exists, certify-reverse starts Caddy with it
instead of the generated Caddyfile.

Use this only for a controlled emergency:

1. copy the generated file;
2. make the smallest change;
3. validate it with Caddy;
4. document why the override exists;
5. remove it after moving the change into supported configuration.

An old override creates configuration drift because later `upstreams.yml` changes do
not affect the active runtime file.

## Rotate a DNS token

1. Create the new restricted token.
2. Replace `DNS_TOKEN` in `.env`.
3. Restart the stack.
4. Force a certificate-related operation or observe a normal renewal path.
5. Confirm DNS API operations succeed.
6. Revoke the old token.
7. Check shell history, backups, and operator notes for accidental copies.

The dashboard does not reveal the configured token.

## Release verification

Run the complete gate:

```bash
./caddy-docker.sh verify
```

It checks:

- synchronized package versions;
- frozen Python dependency resolution;
- unit, regression, and Compose integration tests;
- Ruff and Mypy;
- wheel and source-distribution creation;
- shell syntax;
- base and Caddyfile-print Compose configurations;
- generated Caddyfile validation;
- static site, HTML handbook, PDF handbook, man pages, manifest, and docs archive.

## Build and preview documentation

```bash
./caddy-docker.sh docs
./caddy-docker.sh docs-serve
```

See [Documentation publishing](publishing.md) for renderer pins and output details.

## Maintenance checklist

### Weekly

- inspect logs for repeated warnings;
- run dashboard service checks;
- confirm backups completed;
- inspect disk usage;
- check Caddy updates.

### Monthly

- restore one backup into a test location;
- review DNS provider tokens and operator access;
- inspect certificate expiration data;
- update pinned documentation dependencies when needed;
- run the full release gate on the current main branch.

### Before any major change

- save redacted configuration output;
- back up `caddy-data/` and upstream data;
- record the current commit and Caddy version;
- validate the rollback path;
- change one layer at a time.
