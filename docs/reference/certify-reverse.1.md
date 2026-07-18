---
title: CERTIFY-REVERSE
section: 1
header: User Commands
footer: certify-reverse @VERSION@
date: @DATE@
---

# NAME

certify-reverse - build and run a Caddy reverse proxy with a DNS provider plugin

# SYNOPSIS

**certify-reverse** [**--rebuild-caddy**] [**--show-certs**]
[**--print-caddyfile**]

**certify-reverse** **--rebuild-caddy-only**

**certify-reverse** **--export-certs**

**certify-reverse** **--create-service-dirs**

**certify-reverse** **--check-updates**

# DESCRIPTION

**certify-reverse** reads global settings from `/config/.env` and upstream
settings from `/config/upstreams.yml`. It validates the configuration, builds or
reuses a Caddy binary containing the selected DNS provider plugin, renders runtime
files below `/data`, and normally replaces itself with Caddy.

The normal container entrypoint invokes this command automatically. Operators
usually use **caddy-docker**(1) rather than running it directly.

# OPTIONS

**--rebuild-caddy**
: Force a Caddy rebuild before startup.

**--rebuild-caddy-only**
: Rebuild and validate the configured Caddy version and DNS provider module, then
  exit without starting Caddy.

**--force-build**
: Deprecated alias for **--rebuild-caddy**.

**--update-caddy**
: Force a Caddy rebuild before startup.

**--show-certs**
: Print certificate subjects discovered in generated Caddy configuration, then
  exit.

**--export-certs**
: Export Caddy's internal root CA as PEM and CRT files, write an upstream TLS guide,
  then exit.

**--create-service-dirs**
: Create per-upstream directories containing public internal-CA files, then exit.

**--check-updates**
: Compare the installed Caddy version with the latest discoverable release and
  report whether an update appears advisable.

**--print-caddyfile**
: Render the generated Caddyfile to stdout and exit. Logs are written to stderr so
  stdout can be redirected safely.

**-h**, **--help**
: Show command help.

# CONFIGURATION

`/config/.env`
: Global configuration. Required keys are `DNS_PROVIDER`, `DNS_TOKEN`, and
  `DOMAIN`. Common optional keys include `ACME_EMAIL`, `CADDY_VERSION`,
  `CADDY_DNS_PLUGIN_TOKEN_FIELD`, `DNSMASQ_ADDRESS_MODE`, and
  `DNSMASQ_ADDRESS_IP`.

`/config/upstreams.yml`
: YAML mapping from subdomain names to upstream objects. Each object requires `ip`
  and `port`; `scheme` defaults to `http`.

Example:

```
blog:
  ip: wordpress
  port: 80
  scheme: http
```

# FILES

`/data/Caddyfile`
: Generated Caddy configuration.

`/data/Caddyfile.overwrite`
: Optional operator override used instead of the generated Caddyfile at runtime.

`/data/dnsmasq.conf`
: Generated wildcard dnsmasq configuration.

`/data/index.html`
: Generated status dashboard.

`/data/acme-state.json`
: Generated ACME state summary.

`/data/crtsh-state.json`
: Cached certificate-transparency query result.

`/data/exported-certs/`
: Exported internal root CA files.

`/data/logs/app.log`
: Rotating bootstrap log.

# ENVIRONMENT

`CADDY_DNS_PLUGIN`
: Set internally to the selected provider name before Caddy starts.

`CADDY_DNS_PLUGIN_TOKEN`
: Set internally to the configured DNS credential before Caddy starts.

`CADDY_DNS_PLUGIN_TOKEN_FIELD`
: Provider-specific Caddyfile credential directive.

`CERTIFY_REVERSE_COMMIT`, `APP_COMMIT`
: Optional source commit identifiers exposed in dashboard metadata.

# EXIT STATUS

The command returns zero after successful one-shot operations. Configuration,
build, export, or validation failures return non-zero. During normal startup the
process is replaced with Caddy, so subsequent status is Caddy's status.

# EXAMPLES

Print generated configuration:

```
certify-reverse --print-caddyfile > /tmp/Caddyfile
```

Check Caddy update status:

```
certify-reverse --check-updates
```

Export internal CA files through the project helper:

```
./caddy-docker.sh app --export-certs
```

# SECURITY NOTES

The DNS token can modify records at the configured provider. Restrict token scope,
keep `/config/.env` private, and avoid copying it into logs or issue reports.

The generated status dashboard is not authenticated by default. Protect it with
network policy or an added authentication layer where operational metadata is
sensitive.

# SEE ALSO

**caddy-docker**(1), **caddy**(8), **docker-compose**(1)

Project documentation: `https://fkr-0.github.io/certify-reverse/`
