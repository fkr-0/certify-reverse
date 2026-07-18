# Command reference

There are two command surfaces:

- `./caddy-docker.sh` manages the Compose deployment and project workflows;
- `certify-reverse` is the Python runtime command inside the Caddy container.

For first-time setup, use the [15-minute quickstart](getting-started.md) rather than
reading this page from top to bottom.

## `caddy-docker.sh`

Run commands from the repository root:

```bash
./caddy-docker.sh <command> [arguments]
```

### Runtime control

| Command | What it does | Example |
| --- | --- | --- |
| `start` | Build if necessary and start Caddy and dnsmasq in the background | `./caddy-docker.sh start` |
| `stop` | Stop containers without removing them | `./caddy-docker.sh stop` |
| `restart` | Restart existing containers | `./caddy-docker.sh restart` |
| `down` | Remove project containers and network | `./caddy-docker.sh down` |
| `clean` | Interactively remove this project's containers, network, and volumes | `./caddy-docker.sh clean` |

!!! danger "Use `clean` deliberately"

    It deletes this project's volumes. Prefer `down` when you only want to recreate
    containers. It does not prune global Docker state.

### Logs and inspection

| Command | What it does | Example |
| --- | --- | --- |
| `logs` | Show the last 100 Caddy and dnsmasq log lines | `./caddy-docker.sh logs` |
| `logs --follow` | Follow both services | `./caddy-docker.sh logs --follow` |
| `logs --follow SERVICE` | Follow one service | `./caddy-docker.sh logs --follow caddy` |
| `status` | Show Compose status and container filesystem/memory information | `./caddy-docker.sh status` |
| `config` | Print redacted `.env` and `upstreams.yml`, then generated-file information | `./caddy-docker.sh config` |
| `data` | Show generated configuration, dashboard preview, and recent logs | `./caddy-docker.sh data` |
| `shell` | Open `/bin/sh` inside the running Caddy container | `./caddy-docker.sh shell` |
| `exec` | Run an arbitrary command inside the running Caddy container | `./caddy-docker.sh exec id` |

The `config` command redacts token, secret, password, API-key, and private-key
fields, including multiline YAML block values.

### Caddy and certificate operations

| Command | What it does | Example |
| --- | --- | --- |
| `print-caddyfile` | Render the generated Caddyfile and exit | `./caddy-docker.sh print-caddyfile` |
| `check-updates` | Compare the built Caddy version with the latest discoverable release | `./caddy-docker.sh check-updates` |
| `rebuild-caddy` | Build and validate Caddy, then restart the running Caddy service after success | `./caddy-docker.sh rebuild-caddy` |
| `show-certs` | Print managed certificate subjects from generated configuration | `./caddy-docker.sh show-certs` |
| `reload-dnsmasq` | Send SIGHUP to dnsmasq | `./caddy-docker.sh reload-dnsmasq` |
| `app ARGS…` | Pass arguments directly to `certify-reverse` in the running container | `./caddy-docker.sh app --export-certs` |

`print-caddyfile` keeps stdout configuration-only. Diagnostic logs go to stderr, so
this is safe:

```bash
./caddy-docker.sh print-caddyfile > /tmp/Caddyfile
```

### Image and release operations

| Command | What it does | Docker required? |
| --- | --- | --- |
| `build` | Rebuild the container image without cache | Yes |
| `verify` | Run the complete release gate, including documentation outputs | Yes for Compose checks |
| `version` | Print the project version | No |
| `bump-patch` | Increment patch version in package metadata | No |
| `bump-minor` | Increment minor version | No |
| `bump-major` | Increment major version | No |
| `release-note` | Print a release heading for the current version | No |
| `tag` | Create `v<version>` Git tag | No |

### Documentation operations

| Command | What it does | Output |
| --- | --- | --- |
| `docs` | Build all documentation formats | `dist/docs/` |
| `docs-check` | Build and validate all formats | `dist/docs/` |
| `docs-site` | Build only the searchable static site | `dist/docs/site/` |
| `docs-serve` | Start the local MkDocs development server | Local web server |
| `docs-clean` | Remove generated documentation outputs | Removes `dist/docs/` |
| `docs-update-lock` | Refresh the pinned MkDocs dependency lock | `tools/docs/requirements.lock.txt` |

See [Documentation publishing](publishing.md) for toolchain requirements and output
layout.

## `certify-reverse`

The container entrypoint normally runs this command without manual intervention.

```bash
certify-reverse [OPTIONS]
```

### Options

| Option | Effect |
| --- | --- |
| `--rebuild-caddy` | Force a Caddy build before startup |
| `--rebuild-caddy-only` | Rebuild and validate Caddy, then exit without starting the server |
| `--force-build` | Deprecated alias for `--rebuild-caddy` |
| `--update-caddy` | Force a Caddy build before startup |
| `--show-certs` | Print managed certificate subjects and exit |
| `--export-certs` | Export Caddy's internal root CA files and exit |
| `--create-service-dirs` | Create per-upstream CA distribution directories and exit |
| `--check-updates` | Print built/latest Caddy comparison and exit |
| `--print-caddyfile` | Print generated Caddyfile to stdout and exit |
| `--help` | Show argument help |

### Common direct invocations

Inside the running container:

```bash
./caddy-docker.sh app --check-updates
./caddy-docker.sh app --export-certs
./caddy-docker.sh app --create-service-dirs
```

One-shot invocation when the service is not running:

```bash
docker compose -f docker/docker-compose.yml run --rm --no-deps \
  caddy --print-caddyfile
```

## `certify-reverse-status`

This command prints a terminal-oriented view of configuration, certificate exports,
service directories, data-directory contents, and generated files.

```bash
./caddy-docker.sh exec certify-reverse-status --data-dir /data
```

Use `--help` inside the container for the currently installed options.

## Exit behavior

- configuration errors produce a concise error and non-zero exit;
- one-shot inspection commands return zero on success;
- a failed Caddy build or invalid generated configuration returns non-zero;
- the normal runtime replaces itself with Caddy, so Caddy becomes PID 1.

## Installed man pages

After building docs:

```bash
man -l dist/docs/man/certify-reverse.1
man -l dist/docs/man/caddy-docker.1
```

For local installation:

```bash
install -Dm644 dist/docs/man/certify-reverse.1.gz \
  "$HOME/.local/share/man/man1/certify-reverse.1.gz"
install -Dm644 dist/docs/man/caddy-docker.1.gz \
  "$HOME/.local/share/man/man1/caddy-docker.1.gz"
mandb "$HOME/.local/share/man" 2>/dev/null || true
```
