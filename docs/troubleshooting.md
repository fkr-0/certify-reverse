# Troubleshooting

## Container exits immediately

- Check env and topology files exist in project root:
  - `.env`
  - `upstreams.yml`
- Check required keys in `.env`: `DOMAIN`, `DNS_PROVIDER`, `DNS_TOKEN`.

## Caddy rebuild fails

- Run `./caddy-docker.sh rebuild-caddy` and inspect logs.
- Confirm DNS provider name matches an existing `caddy-dns` module.
- Ensure `/data` is writable (`./caddy-data` bind mount permissions).

## HTTPS upstream cert validation failures

- Export CA certs:
  - `./caddy-docker.sh app --export-certs`
- Trust `caddy-internal-ca.pem` in upstream services or set `skip_verify: true` temporarily.

## Dashboard/probes not loading

- Confirm `status.<DOMAIN>` resolves to the host IP used by dnsmasq.
- Verify `dnsmasq` is running and reloaded:
  - `./caddy-docker.sh logs --follow dnsmasq`
  - `./caddy-docker.sh reload-dnsmasq`

## Validate generated config quickly

```bash
./caddy-docker.sh print-caddyfile
./caddy-docker.sh verify
```
