# Troubleshooting

Start with the smallest failing layer. Do not change DNS, certificates, Docker
networking, and upstream configuration at the same time.

## Fast triage

Run these commands and keep their output:

```bash
./caddy-docker.sh status
./caddy-docker.sh config
./caddy-docker.sh logs
./caddy-docker.sh print-caddyfile >/tmp/Caddyfile
```

Then identify the first broken step:

```text
configuration -> container start -> Caddy build -> DNS-01 -> HTTPS listener
      -> upstream network -> upstream application -> client DNS
```

## Symptom table

| Symptom | Most likely layer | First check |
| --- | --- | --- |
| Container exits immediately | Configuration | `./caddy-docker.sh logs caddy` |
| Caddy rebuild loops or fails | Build/toolchain/network | `./caddy-docker.sh rebuild-caddy` |
| Certificate challenge fails | DNS provider/token | Caddy logs for DNS plugin errors |
| Browser cannot resolve hostname | Client DNS | `nslookup HOST DNS_SERVER` |
| Browser connects but gets 502 | Upstream reachability | request upstream from Caddy container |
| HTTPS upstream fails verification | Trust pool/internal CA | inspect `scheme`, `trust_pool`, CA file |
| Dashboard loads but checks fail | Probe route/upstream | test `/probe/<service>/` and upstream directly |
| Port 53 bind error | DNS service conflict | identify process already using port 53 |
| `print-caddyfile` fails | Invalid `.env` or YAML | read exact validation error |
| Docs build fails | Pinned publishing toolchain | `./caddy-docker.sh docs-check` |

## Container exits immediately

Check that both local files exist:

```bash
ls -l .env upstreams.yml
```

Check required settings without printing the token:

```bash
./caddy-docker.sh config
```

Common mistakes:

- missing `DOMAIN`, `DNS_PROVIDER`, or `DNS_TOKEN`;
- YAML tabs instead of spaces;
- quoted or non-integer port;
- invalid subdomain key;
- duplicate names after lowercase/trailing-dot normalization;
- unsupported upstream field;
- invalid `CADDY_VERSION`;
- wrong provider credential directive.

Render in a one-shot container for a concise error:

```bash
./caddy-docker.sh print-caddyfile
```

## Caddy rebuild fails

Run the explicit operation:

```bash
./caddy-docker.sh rebuild-caddy
```

Inspect for:

- provider module not found;
- DNS failure or blocked outbound network;
- Go module download failure;
- writable-space or permission failure below `caddy-data/caddybuild`;
- unsupported Caddy version;
- insufficient disk space.

Check disk and ownership:

```bash
df -h . caddy-data
find caddy-data -maxdepth 2 -printf '%M %u:%g %p\n' | head -n 40
```

The build is atomic. A failed temporary build should not replace the existing Caddy
binary.

## DNS plugin rejects the token field

A log such as:

```text
unrecognized subdirective 'api_token'
```

means the provider expects another Caddyfile directive.

For deSEC:

```env
CADDY_DNS_PLUGIN_TOKEN_FIELD=token
```

For another provider, check its plugin documentation and set the exact identifier.
Then preview again:

```bash
./caddy-docker.sh print-caddyfile >/tmp/Caddyfile
```

## DNS-01 challenge fails

Separate token problems from client DNS problems. DNS-01 uses the provider API and a
TXT record; it does not depend on your LAN dnsmasq answer.

Check:

1. `DNS_PROVIDER` matches the built module;
2. the token is valid and allowed to edit the correct zone;
3. `DOMAIN` belongs to that zone;
4. outbound HTTPS and DNS are available from the container;
5. provider API rate limits or outages;
6. the generated credential field.

Follow Caddy logs:

```bash
./caddy-docker.sh logs --follow caddy
```

Do not paste the raw token into diagnostic commands.

## Hostname does not resolve for a client

Query the intended DNS server explicitly:

```bash
nslookup app.example.net 192.168.1.20
```

If that succeeds but normal lookup fails, the client is not using the intended DNS
server.

Check generated dnsmasq configuration:

```bash
./caddy-docker.sh data
```

Reload after changes:

```bash
./caddy-docker.sh reload-dnsmasq
```

Remember:

- `/etc/hosts` has no wildcard support;
- browsers may cache DNS;
- VPNs can replace DNS settings;
- systemd-resolved, NetworkManager, router DHCP, Pi-hole, or AdGuard may each affect
  the final resolver path.

Use `curl --resolve` to bypass client DNS while keeping correct HTTPS hostname
validation:

```bash
curl --resolve app.example.net:443:192.168.1.20 \
  https://app.example.net/
```

## Port 53 is already in use

Identify the owner:

```bash
sudo ss -lntup '( sport = :53 )'
```

Possible owners include:

- systemd-resolved;
- dnsmasq already running on the host;
- Pi-hole;
- AdGuard Home;
- a local Kubernetes stack;
- another container.

Do not stop a DNS service blindly on a remote machine. Decide which resolver should
own port 53 and integrate certify-reverse with that resolver or disable the bundled
dnsmasq service in your deployment model.

## HTTPS works but returns 502

A 502 usually means Caddy accepted the browser connection but could not get a valid
response from the upstream.

Test from inside the Caddy container.

HTTP example:

```bash
./caddy-docker.sh exec wget -S -O- http://app:8080/
```

HTTPS example:

```bash
./caddy-docker.sh exec wget -S -O- https://secure-app:8443/
```

Check:

- service name or IP;
- port;
- scheme;
- Compose network membership;
- upstream process listening address;
- upstream firewall;
- TLS trust settings.

A service listening only on `127.0.0.1` inside its own container is not reachable by
Caddy through the Compose network. Bind it to `0.0.0.0` or the container interface.

## HTTPS upstream certificate validation fails

Inspect the upstream entry:

```yaml
secure-app:
  ip: secure-app
  port: 8443
  scheme: https
```

Export Caddy's internal CA after PKI initialization:

```bash
./caddy-docker.sh app --export-certs
```

Confirm the trust file exists:

```bash
ls -l caddy-data/exported-certs/caddy-internal-ca.pem
```

For a custom CA, set an absolute path:

```yaml
trust_pool: /data/trust/vendor-ca.pem
```

Use `skip_verify: true` only as a temporary diagnostic. If it fixes the route, the
remaining issue is trust or hostname validation, not basic networking.

## Dashboard loads but service checks fail

The dashboard uses server-side routes such as:

```text
https://status.example.net/probe/app/
```

Test directly:

```bash
curl --resolve status.example.net:443:192.168.1.20 \
  -I https://status.example.net/probe/app/
```

Then test the upstream inside Caddy. The dashboard reports browser-level reachability,
not a cryptographic certificate inspection.

When live crt.sh refresh fails, the local snapshot may still load. crt.sh is external
and can be unavailable or rate limited.

## Internal CA export is empty

The internal PKI files may not exist before Caddy has started once.

1. start Caddy;
2. wait for initialization;
3. run export again:

```bash
./caddy-docker.sh app --export-certs
```

The exporter accepts root CA files, not intermediate certificates. Existing PEM or
CRT exports repair a missing companion format automatically.

## Generated Caddyfile is ignored

Check for:

```text
caddy-data/Caddyfile.overwrite
```

When present, runtime uses that file instead of `caddy-data/Caddyfile`.

```bash
ls -l caddy-data/Caddyfile*
```

Move the override aside and restart when it is no longer intentional:

```bash
mv caddy-data/Caddyfile.overwrite \
  "caddy-data/Caddyfile.overwrite.disabled.$(date +%s)"
./caddy-docker.sh restart
```

## Permissions below `caddy-data/`

The Caddy container runs with the host UID/GID supplied by the wrapper. Problems can
appear after running Docker commands as root or copying data from another host.

Inspect:

```bash
find caddy-data -maxdepth 3 -printf '%M %u:%g %p\n' | head -n 80
```

Avoid recursively making private keys world-readable. Service key directories and
keys intentionally use restrictive permissions.

## Documentation build fails

Run the dedicated check:

```bash
./caddy-docker.sh docs-check
```

Common causes:

- missing `pandoc`, `weasyprint`, `groff`, or `uv`;
- renderer version differs from `tools/docs/toolchain.toml`;
- broken link rejected by MkDocs strict mode;
- missing source listed in `tools/docs/handbook.toml`;
- changed dependency input without refreshed lock;
- malformed man-page metadata;
- PDF renderer error.

For an intentional renderer trial only:

```bash
DOCS_ALLOW_TOOLCHAIN_DRIFT=1 ./caddy-docker.sh docs-check
```

Do not use that override for a release.

## Collect a safe diagnostic bundle

Capture non-secret information:

```bash
{
  git rev-parse --short HEAD
  ./caddy-docker.sh version
  ./caddy-docker.sh status
  ./caddy-docker.sh config
  ./caddy-docker.sh logs
} > certify-reverse-diagnostics.txt 2>&1
```

Review the file manually before sharing it. Redaction protects known sensitive key
names but cannot recognize every secret embedded in free-form logs or values.

Never include:

- raw `.env`;
- private keys;
- unredacted Docker environment output;
- database dumps;
- Telegram bot tokens;
- provider API responses containing credentials.
