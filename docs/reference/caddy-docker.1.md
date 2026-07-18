---
title: CADDY-DOCKER
section: 1
header: User Commands
footer: certify-reverse @VERSION@
date: @DATE@
---

# NAME

caddy-docker - operate, verify, release, and document certify-reverse

# SYNOPSIS

**./caddy-docker.sh** COMMAND [ARGUMENTS]

# DESCRIPTION

**caddy-docker.sh** is the repository-level operator interface for
certify-reverse. It wraps Docker Compose runtime operations and also exposes local
versioning, verification, and documentation commands that do not require a running
container.

Run the script from the repository root.

# RUNTIME COMMANDS

**start**
: Build when required and start Caddy and dnsmasq in the background.

**stop**
: Stop project services without removing containers.

**restart**
: Restart project services.

**down**
: Remove project containers and network while retaining named volumes unless the
  Compose model says otherwise.

**logs** [**--follow**] [SERVICE]
: Show the last 100 log lines. Without a service, show Caddy and dnsmasq. With
  `--follow`, continue streaming.

**status**
: Show Compose state and basic data-filesystem and memory information.

**config**
: Print redacted `.env` and `upstreams.yml` content plus generated-file
  information. Token, secret, password, API-key, and private-key values are
  suppressed, including YAML block scalars.

**data**
: Print generated Caddyfile, dnsmasq configuration, dashboard preview, and recent
  application logs.

**shell**
: Open `/bin/sh` inside the running Caddy container.

**exec** COMMAND [ARGUMENTS]
: Execute a command inside the running Caddy container.

**app** [ARGUMENTS]
: Run `certify-reverse` with the supplied arguments inside the running container.

**show-certs**
: Print managed certificate subjects.

**check-updates**
: Compare built and latest discoverable Caddy versions.

**rebuild-caddy**
: Build and validate Caddy in the running service or a one-shot container. When
  the service is running, restart it only after the validated binary is installed.

**print-caddyfile**
: Render the generated Caddyfile and write configuration-only output to stdout.

**reload-dnsmasq**
: Send SIGHUP to the dnsmasq service.

**build**
: Build the Caddy image without cache.

**clean**
: Interactively remove this Compose project's containers, network, and volumes.
  This command is destructive but does not prune global Docker state.

# PROJECT COMMANDS

**verify**
: Run the release gate: version synchronization, frozen dependency resolution,
  tests, Ruff, Mypy, package builds, shell syntax, Compose validation, Caddyfile
  validation, and documentation rendering.

**version**
: Print the version from `pyproject.toml`.

**bump-patch**, **bump-minor**, **bump-major**
: Update package version sources using `scripts/bump_version.py`.

**release-note**
: Print a release heading for the current project version.

**tag**
: Create Git tag `v<version>`.

# DOCUMENTATION COMMANDS

**docs**
: Build the static site, standalone HTML handbook, A4 PDF handbook, man pages,
  manifest, and archive below `dist/docs/`.

**docs-check**
: Build and validate all documentation formats.

**docs-site**
: Build only the strict searchable static site used by GitHub Pages.

**docs-serve**
: Start the MkDocs development server.

**docs-clean**
: Remove generated documentation outputs and temporary handbook assembly files.

**docs-update-lock**
: Recompile the pinned MkDocs dependency lock. Use only as an intentional
  maintenance operation and review the resulting diff.

# FILES

`.env`
: Local runtime configuration and DNS credential. Not tracked by Git.

`upstreams.yml`
: Local upstream topology. Not tracked by Git.

`docker/docker-compose.yml`
: Base Compose model.

`caddy-data/`
: Host runtime data mounted at `/data`.

`tools/docs/requirements.lock.txt`
: Hashed Python documentation dependency lock.

`tools/docs/toolchain.toml`
: Expected external renderer versions.

`dist/docs/`
: Generated documentation artifacts.

# EXAMPLES

Start and follow logs:

```
./caddy-docker.sh start
./caddy-docker.sh logs --follow
```

Safely save generated Caddy configuration:

```
./caddy-docker.sh print-caddyfile > /tmp/Caddyfile
```

Build offline documentation:

```
./caddy-docker.sh docs
man -l dist/docs/man/caddy-docker.1
```

Run the complete release gate:

```
./caddy-docker.sh verify
```

# EXIT STATUS

Commands return zero on success and non-zero on failed validation, Docker errors,
missing prerequisites, or unknown commands.

# SEE ALSO

**certify-reverse**(1), **docker-compose**(1), **caddy**(8)

Project documentation: `https://fkr-0.github.io/certify-reverse/`
