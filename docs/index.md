# certify-reverse

**certify-reverse turns a small Docker host into a DNS-validated HTTPS reverse proxy.**
You describe services in YAML, provide a DNS API token, and the runtime builds the
matching Caddy DNS plugin, obtains certificates, writes local DNS configuration,
and exposes an operator dashboard.

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } **I want a working service**

    ---

    Follow the [15-minute quickstart](getting-started.md). It includes a complete
    demo backend, copy-and-paste configuration, checks, and cleanup.

-   :material-school:{ .lg .middle } **I am new to DNS and reverse proxies**

    ---

    Read [Core concepts](concepts.md) first. It explains every moving part without
    assuming Caddy, ACME, or Docker networking knowledge.

-   :material-docker:{ .lg .middle } **I want a realistic deployment**

    ---

    Build the [WordPress + Telegram webhook example](tutorials/wordpress-telegram.md)
    with one database, two upstreams, HTTPS, health checks, and safe secret placeholders.

-   :material-book-open-page-variant:{ .lg .middle } **I need offline documentation**

    ---

    Run `./caddy-docker.sh docs`. It produces a searchable static site, an A4 PDF
    handbook, HTML handbook, compressed man pages, checksums, and an archive.

</div>

## What it does

For each configured upstream, certify-reverse can generate a public HTTPS host such
as `notes.example.net` and forward requests to a private target such as
`notes:8080`.

```text
browser
   |
   | HTTPS: notes.example.net
   v
Caddy + DNS-01 certificate
   |
   | HTTP inside Docker network
   v
notes:8080
```

The project also generates:

- a Caddyfile and dnsmasq configuration under `caddy-data/`;
- a status dashboard at `status.<domain>`;
- certificate and crt.sh status snapshots;
- exported internal CA files for HTTPS upstream trust;
- local commands for start, stop, verification, release work, and documentation.

## Choose the right path

| You are trying to… | Start with… |
| --- | --- |
| See the smallest complete setup | [15-minute quickstart](getting-started.md) |
| Understand the terminology | [Core concepts](concepts.md) |
| Configure several services | [Configuration](configuration.md) |
| Deploy a real application stack | [WordPress + Telegram](tutorials/wordpress-telegram.md) |
| Operate an existing installation | [Operations](operations.md) |
| Diagnose a failure | [Troubleshooting](troubleshooting.md) |
| Look up one command | [Command reference](cli-reference.md) |
| Publish the docs | [Documentation publishing](publishing.md) |

## What you need

- Docker with the `docker compose` subcommand;
- a domain you control;
- an API token for a Caddy-supported DNS provider;
- ports 80 and 443 available on the proxy host;
- port 53 available only when you enable the bundled dnsmasq service for LAN DNS.

!!! warning "Use a restricted DNS token"

    The DNS token can modify records in your zone. Create the narrowest token your
    provider supports, keep `.env` out of version control, and rotate the token if it
    is ever copied into logs, screenshots, or chat.

## Documentation formats

The same Markdown sources feed every published format:

```text
docs/*.md
   ├── MkDocs Material -> dist/docs/site/
   ├── Pandoc          -> dist/docs/certify-reverse-handbook.html
   ├── WeasyPrint      -> dist/docs/certify-reverse-handbook.pdf
   └── Pandoc man      -> dist/docs/man/*.1 + *.1.gz
```

See [Documentation publishing](publishing.md) for the exact commands and pinned
toolchain policy.
