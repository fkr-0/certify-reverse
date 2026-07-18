# Architecture

certify-reverse is a small Python bootstrapper around Caddy, xcaddy, Docker Compose,
and dnsmasq. Its design favors explicit generated files and inspectable shell
operations over a long-running management daemon.

## Component view

```text
repository configuration
├── .env
└── upstreams.yml
        |
        v
certify_reverse.cli
├── validates configuration
├── checks/builds Caddy DNS plugin
├── renders Caddyfile + dnsmasq.conf
├── exports internal CA material
├── writes dashboard + JSON snapshots
└── execs Caddy as PID 1
        |
        +--------------------------+
        |                          |
        v                          v
Caddy reverse proxy            dnsmasq service
ports 80/443                   port 53 TCP/UDP
        |
        v
configured upstream services
```

## Source layout

| Path | Responsibility |
| --- | --- |
| `src/certify_reverse/cli.py` | Configuration model, runtime bootstrap, Caddy build, certificate exports, status data |
| `src/certify_reverse/templates.py` | Caddyfile, dnsmasq, and TLS guide rendering |
| `src/certify_reverse/status_page.py` | Self-contained browser dashboard |
| `src/certify_reverse/status_cli.py` | Terminal status view |
| `caddy-docker.sh` | Operator, release, and documentation commands |
| `docker/` | Container image and Compose models |
| `tools/docs/` | Pinned documentation publishing pipeline |
| `examples/` | Runnable tutorial overlays and applications |
| `tests/` | Unit, regression, shell, Compose, and publishing checks |

## Runtime flow

1. Docker runs `/usr/local/bin/boot`.
2. `boot.sh` creates writable runtime directories and invokes `certify-reverse`.
3. The application loads `/config/.env` and `/config/upstreams.yml`.
4. Dataclass validation rejects malformed or unsafe values.
5. The application checks whether `/data/caddy-rebuild` exists, contains the
   required exact DNS provider module, and matches an explicit version pin.
6. When needed, xcaddy builds a temporary binary under `/data/caddybuild`.
7. A successful temporary build atomically replaces the active binary.
8. The application renders and atomically replaces runtime files.
9. Optional trust extensions and certificate export/generation steps run.
10. Caddy starts with the generated file or `Caddyfile.overwrite`.
11. `os.execvp` replaces the Python process, making Caddy PID 1.

## Configuration boundaries

The runtime has three configuration layers:

1. image defaults;
2. container process environment;
3. mounted `/config/.env`.

The mounted file is authoritative and overrides inherited image values. This avoids
a stale image `CADDY_VERSION` silently defeating the deployment configuration.

`upstreams.yml` has a deliberately narrow schema. Unknown fields fail instead of
being ignored.

## Caddy build strategy

The active binary is persisted below `/data` rather than rebuilt into the image on
every configuration change.

```text
requested provider/version
        |
        v
check existing binary
   | exact plugin present?
   | explicit version matches?
   +-- yes -> reuse
   +-- no  -> xcaddy build temporary file
                    |
                    +-- success -> atomic replace
                    +-- failure -> keep previous binary
```

Build caches, module caches, temporary files, and HOME/XDG directories are placed
below writable runtime data so a non-root container does not attempt to use
`/.cache`, `/.config`, or `/.local`.

## Generated Caddy model

The renderer creates:

- one site block per upstream;
- a status host with server-side probe routes;
- an internal-CA public certificate download host;
- a wildcard convenience host;
- a DNS-01 TLS block using runtime environment placeholders.

The DNS token is not embedded directly in the generated Caddyfile. Caddy receives it
through `CADDY_DNS_PLUGIN_TOKEN`.

IPv6 upstream literals are bracketed in both normal and probe routes.

## Data and atomicity

Generated text, JSON, HTML, CA files, and static assets use same-directory temporary
files followed by `os.replace`. This prevents readers from seeing a partially written
file after interruption.

Service certificates use a paired staging process:

1. Caddy writes temporary certificate and key files;
2. both must exist and be non-empty;
3. certificate mode becomes `0644`;
4. private-key mode becomes `0600`;
5. staged files replace active files.

The remaining full lifecycle—expiry-aware reuse, coordinated pair rotation,
consumer reload, and revocation behavior—is tracked in `issues.yml`.

## Dashboard architecture

The status page is generated as one self-contained HTML document with embedded CSS
and JavaScript. Runtime metadata and service definitions are serialized as inline
JSON with script-closing characters escaped.

Browser data sources:

| Endpoint | Content |
| --- | --- |
| `/acme-state.json` | Generated ACME summary |
| `/crtsh-state.json` | Local crt.sh snapshot |
| `/probe/<service>/` | Server-side upstream reachability proxy |
| `/probe/crtsh` | Server-side crt.sh proxy for live refresh |

The browser constructs rows with DOM APIs and `textContent`; runtime values are not
inserted with `innerHTML`.

## Certificate model

### Browser-facing certificates

Caddy obtains these through ACME DNS-01. DNS provider credentials are needed for
challenge records and renewal.

### Internal upstream trust

When Caddy connects to an HTTPS upstream, it can:

- trust the exported internal CA;
- trust an explicit PEM file;
- temporarily skip verification.

The internal-CA host serves only public root CA files. Private keys are never routed
through it.

## dnsmasq model

The generated configuration provides one wildcard address rule:

```text
address=/.<DOMAIN>/<DNSMASQ_ADDRESS_IP>
```

It is intentionally simple. DHCP integration, split DNS, DNSSEC policy, IPv6
wildcard responses, and coexistence with another resolver remain deployment-level
or deferred concerns.

## Extension model

An HTTPS upstream may name a `trust_ext.<ext_name>` Python module. The runtime loads a
`TrustExtension` class, asks for status, and may issue or refresh trust material.

This interface is currently convention-based rather than a versioned plugin API.
The larger API and isolation work is tracked in `issues.yml`.

## Packaging

Python uses a `src/` package layout and setuptools. Console entrypoints are:

```text
certify-reverse        -> certify_reverse.cli:entrypoint
certify-reverse-status -> certify_reverse.status_cli:main
```

Wheel and source distribution builds are part of the release gate.

## Documentation architecture

Canonical Markdown is rendered into several formats:

```text
docs/*.md
├── MkDocs Material static site
├── Pandoc standalone handbook HTML
├── WeasyPrint A4 PDF
└── Pandoc roff man pages
```

Python documentation dependencies are hash-pinned. External renderer versions are
recorded and enforced. A manifest records source order, tool versions, sizes, and
SHA-256 hashes.

## Idempotency profile

Idempotent for fixed inputs:

- configuration validation;
- Caddyfile and dnsmasq rendering;
- static/dashboard generation;
- existing compatible binary reuse;
- documentation archive metadata when `SOURCE_DATE_EPOCH` is fixed.

Intentionally or currently variable:

- `CADDY_VERSION=latest`;
- GitHub release lookup;
- crt.sh results;
- certificate authority timing;
- provider DNS propagation;
- generated certificate lifetimes;
- package-index contents when intentionally refreshing the docs lock.

## Security boundaries

Sensitive:

- DNS provider token;
- Caddy private keys and certificate storage;
- generated service private keys;
- application secrets in tutorial/application environments;
- runtime backups.

Public or lower sensitivity by design:

- root CA certificates;
- generated Caddyfile placeholders without token values;
- static documentation artifacts;
- version and commit metadata.

The dashboard may still reveal operational topology and is unauthenticated by
default. Protect it according to the deployment threat model.

## Deferred architectural work

`issues.yml` tracks larger work not appropriate for a patch release, including:

- live DNS-provider integration coverage;
- dashboard authentication and metadata policy;
- a versioned trust-extension API;
- reproducible Caddy and container supply chain;
- dual-stack wildcard DNS;
- CI and protected release publishing;
- expiry-aware internal service certificate lifecycle;
- project license selection.
