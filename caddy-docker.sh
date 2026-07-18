#!/usr/bin/env bash
set -euo pipefail

COMPOSE_SERVICE="caddy"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="docker/docker-compose.yml"
COMPOSE_CADDYFILE_OVERRIDE="docker/docker-compose.caddyfile.yml"
VERSION_FILE="pyproject.toml"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }

is_sensitive_key() {
  local upper_key="${1^^}"
  case "$upper_key" in
    *TOKEN*|*SECRET*|*PASSWORD*|*API_KEY*|*API-KEY*|*PRIVATE_KEY*|*PRIVATE-KEY*) return 0 ;;
    *) return 1 ;;
  esac
}

redact_env_file() {
  local path="$1"
  while IFS= read -r line || [[ -n "$line" ]]; do
    if [[ "$line" != *=* || "$line" =~ ^[[:space:]]*# ]]; then
      printf '%s\n' "$line"
      continue
    fi
    local key="${line%%=*}"
    if is_sensitive_key "$key"; then
      printf '%s=***REDACTED***\n' "$key"
    else
      printf '%s\n' "$line"
    fi
  done < "$path"
}

redact_yaml_file() {
  local path="$1"
  local redacted_block_indent=-1
  while IFS= read -r line || [[ -n "$line" ]]; do
    if (( redacted_block_indent >= 0 )); then
      if [[ -z "${line//[[:space:]]/}" ]]; then
        printf '\n'
        continue
      fi
      local current_indent=0
      if [[ "$line" =~ ^([[:space:]]*) ]]; then
        current_indent="${#BASH_REMATCH[1]}"
      fi
      if (( current_indent > redacted_block_indent )); then
        continue
      fi
      redacted_block_indent=-1
    fi
    if [[ "$line" =~ ^([[:space:]]*)([A-Za-z_][A-Za-z0-9_-]*)[[:space:]]*:[[:space:]]*(.*)$ ]] \
      && is_sensitive_key "${BASH_REMATCH[2]}"; then
      local sensitive_indent="${#BASH_REMATCH[1]}"
      local sensitive_key="${BASH_REMATCH[2]}"
      local sensitive_value="${BASH_REMATCH[3]}"
      printf '%s%s: ***REDACTED***\n' "${line:0:sensitive_indent}" "$sensitive_key"
      if [[ "$sensitive_value" =~ ^[\>\|] ]]; then
        redacted_block_indent="$sensitive_indent"
      fi
    else
      printf '%s\n' "$line"
    fi
  done < "$path"
}

check_docker_compose() {
  if command -v docker-compose >/dev/null 2>&1; then
    DOCKER_COMPOSE="docker-compose"
  elif command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
  else
    log_error "Neither 'docker-compose' nor 'docker compose' found."
    exit 1
  fi
}

compose() {
  cd "$SCRIPT_DIR"
  local derived_builder_image
  derived_builder_image="$(derive_builder_image_from_version)"
  HOST_UID="$(id -u)" HOST_GID="$(id -g)" HOST_DNSMASQ_ADDRESS_IP="$(derive_host_src_ip || true)" CERTIFY_REVERSE_COMMIT="$(git_commit_short || true)" CADDY_BUILDER_IMAGE="${CADDY_BUILDER_IMAGE:-$derived_builder_image}" $DOCKER_COMPOSE -f "$COMPOSE_FILE" "$@"
}

compose_caddyfile() {
  cd "$SCRIPT_DIR"
  local derived_builder_image
  derived_builder_image="$(derive_builder_image_from_version)"
  HOST_UID="$(id -u)" HOST_GID="$(id -g)" HOST_DNSMASQ_ADDRESS_IP="$(derive_host_src_ip || true)" CERTIFY_REVERSE_COMMIT="$(git_commit_short || true)" CADDY_BUILDER_IMAGE="${CADDY_BUILDER_IMAGE:-$derived_builder_image}" $DOCKER_COMPOSE -f "$COMPOSE_FILE" -f "$COMPOSE_CADDYFILE_OVERRIDE" "$@"
}

derive_host_src_ip() {
  command -v ip >/dev/null 2>&1 || return 1
  ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i=1;i<=NF;i++) if ($i=="src") {print $(i+1); exit}}'
}

git_commit_short() {
  git -C "$SCRIPT_DIR" rev-parse --short HEAD 2>/dev/null
}

derive_builder_image_from_version() {
  local requested="${CADDY_VERSION:-}"

  if [[ -z "$requested" && -f "$SCRIPT_DIR/.env" ]]; then
    requested="$(sed -n 's/^CADDY_VERSION=//p' "$SCRIPT_DIR/.env" | tail -n1)"
  fi

  requested="${requested%\"}"
  requested="${requested#\"}"
  requested="${requested%\'}"
  requested="${requested#\'}"

  if [[ -z "$requested" || "$requested" == "latest" ]]; then
    echo "caddy:2.10.0-builder"
    return
  fi

  requested="${requested#v}"
  echo "caddy:${requested}-builder"
}

caddy_is_running() {
  compose ps --services --filter status=running 2>/dev/null | grep -qx "$COMPOSE_SERVICE"
}

project_version() {
  sed -n 's/^version = "\([0-9]\+\.[0-9]\+\.[0-9]\+\)"/\1/p' "$SCRIPT_DIR/$VERSION_FILE"
}

show_usage() {
  cat << EOFU
Usage: $0 <command> [options]

Runtime commands:
  start
  stop
  restart
  logs [--follow] [service]
  shell
  exec <command>
  app [args...]
  show-certs
  check-updates
  rebuild-caddy
  print-caddyfile
  config
  data
  status
  build
  down
  clean
  reload-dnsmasq

Project commands:
  verify
  docs
  docs-check
  docs-site
  docs-serve
  docs-clean
  docs-update-lock
  version
  bump-patch
  bump-minor
  bump-major
  release-note
  tag
EOFU
}

start_services() { log_info "Starting services..."; compose up -d; log_success "Services started"; }
stop_services() { log_info "Stopping services..."; compose stop; log_success "Services stopped"; }
restart_services() { log_info "Restarting services..."; compose restart; log_success "Services restarted"; }

show_logs() {
  local follow=""
  local service=""
  if [[ "${1:-}" == "--follow" ]]; then
    follow="-f"
    shift || true
  fi
  service="${1:-}"

  if [[ -n "$service" ]]; then
    compose logs $follow --tail=100 "$service"
    return
  fi
  compose logs $follow --tail=100 caddy dnsmasq
}

open_shell() { compose exec "$COMPOSE_SERVICE" /bin/sh; }

exec_command() {
  if [[ $# -eq 0 ]]; then
    log_error "No command specified"
    exit 1
  fi
  compose exec "$COMPOSE_SERVICE" "$@"
}

run_app() { compose exec "$COMPOSE_SERVICE" certify-reverse "$@"; }
show_certificates() { compose exec "$COMPOSE_SERVICE" certify-reverse --show-certs; }
check_updates() { compose exec "$COMPOSE_SERVICE" certify-reverse --check-updates; }
rebuild_caddy() {
  if caddy_is_running; then
    log_info "Rebuilding Caddy in running service container..."
    compose exec "$COMPOSE_SERVICE" certify-reverse --rebuild-caddy
    return
  fi
  log_warn "Service '$COMPOSE_SERVICE' is not running; using one-shot rebuild container."
  compose run --rm --no-deps "$COMPOSE_SERVICE" --rebuild-caddy
}
print_caddyfile() { compose_caddyfile run --rm caddy; }

show_config() {
  log_info "Runtime configuration"
  echo "=== .env ==="
  if [[ -f .env ]]; then
    redact_env_file .env
  else
    log_warn ".env not found"
  fi
  echo
  echo "=== upstreams.yml ==="
  if [[ -f upstreams.yml ]]; then
    redact_yaml_file upstreams.yml
  else
    log_warn "upstreams.yml not found"
  fi
  echo
  echo "=== Generated Files in /data ==="
  compose exec "$COMPOSE_SERVICE" sh -c "ls -la /data/ && echo && echo '=== Caddyfile Preview ===' && head -40 /data/Caddyfile 2>/dev/null || echo 'Caddyfile not found'" || true
}

show_status() {
  compose ps
  echo
  compose exec "$COMPOSE_SERVICE" sh -c "df -h /data && echo && free -h" || true
}

show_data() {
  compose exec "$COMPOSE_SERVICE" sh -c "
    echo 'Data Directory Structure:'
    ls -la /data/
    echo
    echo 'Generated Caddyfile:'
    cat /data/Caddyfile 2>/dev/null || echo 'Caddyfile not found'
    echo
    echo 'Generated dnsmasq.conf:'
    cat /data/dnsmasq.conf 2>/dev/null || echo 'dnsmasq.conf not found'
    echo
    echo 'Generated index.html:'
    head -40 /data/index.html 2>/dev/null || echo 'index.html not found'
    echo
    echo 'Recent Logs:'
    tail -40 /data/logs/app.log 2>/dev/null || echo 'No logs found'
  " || true
}

build_images() {
  log_info "Building Docker image from docker/Dockerfile..."
  compose build --no-cache
}

down_services() { compose down; }
reload_dnsmasq() {
  log_info "Sending SIGHUP to dnsmasq for config reload..."
  compose kill -s HUP dnsmasq
  log_success "dnsmasq reload signal sent"
}

clean_all() {
  log_warn "This will remove containers, networks, and volumes. Continue? (y/N)"
  read -r response
  if [[ "$response" =~ ^[Yy]$ ]]; then
    compose down -v --remove-orphans
    docker system prune -f
  fi
}

verify_project() {
  cd "$SCRIPT_DIR"
  python3 -m py_compile \
    src/certify_reverse/cli.py \
    src/certify_reverse/status_cli.py \
    src/certify_reverse/status_page.py \
    src/certify_reverse/templates.py \
    tools/docs/build.py
  python3 - <<'PY'
import re
import tomllib
from pathlib import Path

with Path("pyproject.toml").open("rb") as f:
    project_version = tomllib.load(f)["project"]["version"]
init_text = Path("src/certify_reverse/__init__.py").read_text(encoding="utf-8")
match = re.search(r'^__version__ = "([0-9]+\.[0-9]+\.[0-9]+)"$', init_text, re.M)
if match is None or match.group(1) != project_version:
    raise SystemExit("Version mismatch between pyproject.toml and certify_reverse.__version__")
PY
  if command -v uv >/dev/null 2>&1; then
    uv sync --frozen --group dev
    uv run --frozen --group dev pytest -q
    uv run --frozen --group dev ruff check src tests scripts tools examples/wordpress-telegram/telegram-bot/app.py
    uv run --frozen --group dev mypy src/certify_reverse scripts/bump_version.py tools/docs/build.py
    local build_dir
    build_dir="$(mktemp -d)"
    uv build --out-dir "$build_dir" >/dev/null
    rm -rf "$build_dir"
  else
    log_warn "uv not found; running the reduced stdlib verification path"
    python3 -m unittest discover -s tests -p 'test_*.py'
  fi
  bash -n caddy-docker.sh
  sh -n boot.sh
  sh -n examples/wordpress-telegram/register-webhook.sh
  compose config >/dev/null
  compose_caddyfile config >/dev/null
  compose -f examples/quickstart/compose.override.yml config >/dev/null
  compose --env-file examples/wordpress-telegram/.env.example \
    -f examples/wordpress-telegram/compose.override.yml config >/dev/null
  python3 tools/docs/build.py check
  log_success "Verification passed"
}

build_docs() { cd "$SCRIPT_DIR"; python3 tools/docs/build.py build; }
check_docs() { cd "$SCRIPT_DIR"; python3 tools/docs/build.py check; }
build_docs_site() { cd "$SCRIPT_DIR"; python3 tools/docs/build.py site; }
serve_docs() { cd "$SCRIPT_DIR"; python3 tools/docs/build.py serve; }
clean_docs() { cd "$SCRIPT_DIR"; python3 tools/docs/build.py clean; }
update_docs_lock() { cd "$SCRIPT_DIR"; python3 tools/docs/build.py update-lock; }

show_version() { project_version; }
bump_patch() { cd "$SCRIPT_DIR"; python3 scripts/bump_version.py patch; }
bump_minor() { cd "$SCRIPT_DIR"; python3 scripts/bump_version.py minor; }
bump_major() { cd "$SCRIPT_DIR"; python3 scripts/bump_version.py major; }
release_note() { echo "Release v$(project_version)"; }
create_tag() {
  cd "$SCRIPT_DIR"
  local v="v$(project_version)"
  git tag "$v"
  log_success "Created tag $v"
}

main() {
  local command="${1:-}"
  case "$command" in
    version) show_version; return ;;
    docs) build_docs; return ;;
    docs-check) check_docs; return ;;
    docs-site) build_docs_site; return ;;
    docs-serve) serve_docs; return ;;
    docs-clean) clean_docs; return ;;
    docs-update-lock) update_docs_lock; return ;;
    bump-patch) bump_patch; return ;;
    bump-minor) bump_minor; return ;;
    bump-major) bump_major; return ;;
    release-note) release_note; return ;;
    tag) create_tag; return ;;
    help|--help|-h|"") show_usage; return ;;
  esac

  check_docker_compose
  case "$command" in
    start) start_services ;;
    stop) stop_services ;;
    restart) restart_services ;;
    logs) shift; show_logs "$@" ;;
    shell) open_shell ;;
    exec) shift; exec_command "$@" ;;
    app) shift; run_app "$@" ;;
    show-certs) show_certificates ;;
    check-updates) check_updates ;;
    rebuild-caddy|force-rebuild) rebuild_caddy ;;
    print-caddyfile) print_caddyfile ;;
    config) show_config ;;
    data) show_data ;;
    status) show_status ;;
    build) build_images ;;
    down) down_services ;;
    clean) clean_all ;;
    reload-dnsmasq) reload_dnsmasq ;;
    verify) verify_project ;;
    *) log_error "Unknown command: $1"; show_usage; exit 1 ;;
  esac
}

main "$@"
