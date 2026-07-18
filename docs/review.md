# Architecture review

This review summarizes material risks that remain after the 0.5.x hardening work.
Large deferred items are tracked in `issues.yml` with acceptance criteria.

## High-priority findings

### Runtime Caddy build remains operationally expensive

certify-reverse can build Caddy with xcaddy during startup. The build is atomic and
uses persistent writable caches, but still depends on:

- outbound network access;
- Go module availability;
- provider plugin compatibility;
- sufficient CPU, memory, disk, and startup time.

A reproducible prebuilt-image path with immutable Caddy and plugin inputs remains the
preferred production hardening direction.

### Dashboard authentication is deployment policy, not built in

The dashboard no longer exposes the DNS token and uses safe DOM rendering, but may
reveal:

- configured hostnames;
- upstream targets;
- version and commit information;
- reachability and certificate state.

Protect `status.<DOMAIN>` with network controls or an authentication layer when this
metadata is sensitive.

### DNS provider coverage is mostly structural

Tests verify configuration generation, plugin-name matching, provider credential
field handling, and Caddy adapter validation. They do not exercise live DNS-01 flows
against every supported provider.

A provider matrix with delegated test zones and cleanup assertions remains a larger
integration project.

## Medium-priority findings

### Browser checks are reachability signals

The dashboard probes through Caddy and reports response state and timing. Browsers do
not expose the full peer certificate chain, negotiated cipher, or expiry details to
page JavaScript.

Use dedicated monitoring or command-line TLS inspection for authoritative
cryptographic checks.

### dnsmasq owns a privileged, commonly occupied port

The bundled dnsmasq service binds TCP and UDP port 53. It can conflict with local
resolvers, Pi-hole, AdGuard Home, router software, or another container.

The project should not guess which resolver an operator intends to replace. Treat
port-53 ownership as an explicit deployment decision.

### Service certificate lifecycle is incomplete

Generation now uses staging, non-empty validation, restrictive permissions, and
atomic installation. Remaining work includes:

- healthy-certificate reuse;
- expiry-aware rotation;
- coordinated certificate/key replacement;
- dependent-service reload;
- interruption rollback;
- revocation behavior.

### Extension API is convention-based

Trust extensions are imported dynamically and expected to provide a
`TrustExtension` class. There is no versioned contract, schema, timeout boundary, or
isolation model yet.

## Low-priority and operational findings

### `Caddyfile.overwrite` can create silent drift

The emergency override is valuable, but while present it bypasses generated
configuration. Operators need an explicit lifecycle for creating, validating,
documenting, and removing it.

### External status data is time-variable

GitHub release discovery and crt.sh data can fail, change, or be rate limited. The
runtime degrades these checks to `unknown` rather than aborting startup, which is the
right availability tradeoff, but dashboards and reports must not treat them as
authoritative.

### Documentation PDF still needs visual release review

The publishing pipeline validates source links, JavaScript, output signatures, man
headers, and deterministic metadata. Automated checks cannot fully judge page
breaks, dense tables, or font rendering. A visual PDF review remains part of release
work.

## Completed hardening relevant to this review

- exact Caddy plugin detection;
- explicit pinned-version matching and atomic rebuild;
- strict domain, upstream, environment, and path validation;
- normalized upstream collision detection;
- redacted multiline secret output;
- atomic generated files;
- restricted service private keys;
- resilient external status lookups;
- safe dashboard DOM construction and accessible interaction states;
- Caddy adapter validation of generated configuration;
- pinned, multi-format documentation publishing.

## Recommended next work

1. Implement protected CI and release publishing from version tags.
2. Build a live DNS-provider test matrix using delegated non-production zones.
3. Add an explicit dashboard authentication and metadata policy.
4. Design expiry-aware service certificate rotation and consumer reload.
5. Pin the Caddy/container supply chain to immutable inputs.
6. Select and publish a project license.
