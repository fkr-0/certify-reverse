# Implementation Review

Date: 2026-02-24

## Findings

### Critical

1. `app.py` failed to import at runtime due to invalid `from __future__` placement.
- Location: `app.py` top-of-file.
- Impact: process exits before startup.
- Status: fixed.

2. `build_caddy` called with wrong type and defined after invocation path.
- Location: `app.py` around `main()` and bottom of file.
- Impact: startup failure (`AttributeError`/`NameError`) when rebuild path is exercised.
- Status: fixed (signature changed to `dns_provider: str`, moved into active function section).

3. `docker-compose.yml` entrypoint kept container sleeping forever.
- Location: `docker-compose.yml` service `caddy`.
- Impact: app bootstrap and Caddy never start automatically.
- Status: fixed (`entrypoint: ["/usr/bin/boot"]`).

### High

4. `caddy-docker.sh` had function-boundary bug (`show_data` nested inside `show_status`).
- Location: `caddy-docker.sh` around lines ~173-199.
- Impact: incorrect status/data behavior and hard-to-maintain script flow.
- Status: fixed.

5. Runtime dependency mismatch in `pyproject.toml`.
- Location: `pyproject.toml` dependencies.
- Impact: code imports `yaml` but dependency listed `pyaml` instead of `PyYAML`.
- Status: fixed (`pyyaml>=6.0.2`).

6. `boot.sh` invoked `app.py` instead of mounted executable path.
- Location: `boot.sh` line invoking app.
- Impact: command-not-found risk in container startup depending on PATH.
- Status: fixed (`/usr/bin/app`).

7. `Dockerfile` referenced non-existent project files (`startup.py`, `templates/`).
- Location: previous `Dockerfile`.
- Impact: build failure when using Dockerfile path.
- Status: fixed by replacing Dockerfile with current repo-aligned build.

### Medium

8. Status output pointed to wrong log path.
- Location: `status.py` generated files table.
- Impact: false-negative log visibility (`/data/app.log` vs `/data/logs/app.log`).
- Status: fixed.

9. Sensitive DNS token appears in tracked `config.yml`.
- Location: `config.yml`.
- Impact: credential exposure risk if repo is shared/backed up.
- Status: not automatically rotated by code changes; operational remediation required.

## Verification Performed

- `python3 -m py_compile app.py status.py templates.py` passed.
- `bash -n caddy-docker.sh` passed.
- `sh -n boot.sh` passed.
- `docker compose config` passed.

## Recommended Follow-Up

1. Rotate exposed DNS API token immediately.
2. Add `config.yml` to `.gitignore` and keep `config.yml.example` only.
3. Add automated CI checks for:
- Python compile/lint,
- shell syntax,
- `docker compose config`.
