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
  HOST_UID="$(id -u)" HOST_GID="$(id -g)" $DOCKER_COMPOSE -f "$COMPOSE_FILE" "$@"
}

compose_caddyfile() {
  cd "$SCRIPT_DIR"
  HOST_UID="$(id -u)" HOST_GID="$(id -g)" $DOCKER_COMPOSE -f "$COMPOSE_FILE" -f "$COMPOSE_CADDYFILE_OVERRIDE" "$@"
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
  logs [--follow]
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

Project commands:
  verify
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
  if [[ "${1:-}" == "--follow" ]]; then
    compose logs -f "$COMPOSE_SERVICE"
  else
    compose logs --tail=50 "$COMPOSE_SERVICE"
  fi
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
rebuild_caddy() { compose exec "$COMPOSE_SERVICE" certify-reverse --rebuild-caddy; }
print_caddyfile() { compose_caddyfile run --rm caddy; }

show_config() {
  log_info "Runtime configuration"
  echo "=== .env ==="
  cat .env 2>/dev/null || log_warn ".env not found"
  echo
  echo "=== upstreams.yml ==="
  cat upstreams.yml 2>/dev/null || log_warn "upstreams.yml not found"
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
  python3 -m py_compile src/certify_reverse/cli.py src/certify_reverse/status_cli.py src/certify_reverse/templates.py
  python3 -m unittest discover -s tests -p 'test_*.py'
  bash -n caddy-docker.sh
  sh -n boot.sh
  docker compose -f docker/docker-compose.yml config >/dev/null
  docker compose -f docker/docker-compose.yml -f docker/docker-compose.caddyfile.yml config >/dev/null
  log_success "Verification passed"
}

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
  check_docker_compose
  case "${1:-}" in
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
    verify) verify_project ;;
    version) show_version ;;
    bump-patch) bump_patch ;;
    bump-minor) bump_minor ;;
    bump-major) bump_major ;;
    release-note) release_note ;;
    tag) create_tag ;;
    help|--help|-h|"") show_usage ;;
    *) log_error "Unknown command: $1"; show_usage; exit 1 ;;
  esac
}

main "$@"
