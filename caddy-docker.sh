#!/usr/bin/env bash
# Caddy Docker Helper Script
# Simplifies common Docker operations for the Caddy reverse proxy setup

set -euo pipefail

COMPOSE_SERVICE="caddy"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warn() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if docker-compose is available
check_docker_compose() {
    if command -v docker-compose >/dev/null 2>&1; then
        DOCKER_COMPOSE="docker-compose"
    elif command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
        DOCKER_COMPOSE="docker compose"
    else
        log_error "Neither 'docker-compose' nor 'docker compose' found. Please install Docker Compose."
        exit 1
    fi
}

# Show usage information
show_usage() {
    cat << EOF
Caddy Docker Helper Script

Usage: $0 <command> [options]

Commands:
  start                 Start the Caddy services
  stop                  Stop the Caddy services  
  restart               Restart the Caddy services
  logs [--follow]       Show Caddy logs (optionally follow)
  shell                 Open interactive shell in Caddy container
  exec <command>        Execute command in Caddy container
  app [args...]         Run app.py in container with optional arguments
  show-certs            Show Caddy internal certificates
  force-rebuild         Force rebuild Caddy with DNS provider
  config                Show current configuration
  data                  Show all generated files in /data directory
  status                Show container status
  build                 Build/rebuild the Docker images
  down                  Stop and remove containers
  clean                 Remove containers, networks, and volumes

Examples:
  $0 app --show-certs              # Show certificates
  $0 app --export-certs            # Export CA certificates
  $0 app --create-service-dirs     # Create service-specific CA directories
  $0 app --force-build             # Force rebuild Caddy
  $0 exec caddy version            # Check Caddy version
  $0 logs --follow                 # Follow logs in real-time
  $0 shell                         # Interactive shell

EOF
}

# Start services
start_services() {
    log_info "Starting Caddy services..."
    cd "$SCRIPT_DIR"
    $DOCKER_COMPOSE up -d
    log_success "Services started"
}

# Stop services
stop_services() {
    log_info "Stopping Caddy services..."
    cd "$SCRIPT_DIR"
    $DOCKER_COMPOSE stop
    log_success "Services stopped"
}

# Restart services
restart_services() {
    log_info "Restarting Caddy services..."
    cd "$SCRIPT_DIR"
    $DOCKER_COMPOSE restart
    log_success "Services restarted"
}

# Show logs
show_logs() {
    cd "$SCRIPT_DIR"
    if [[ "${1:-}" == "--follow" ]]; then
        log_info "Following Caddy logs (Ctrl+C to exit)..."
        $DOCKER_COMPOSE logs -f $COMPOSE_SERVICE
    else
        log_info "Showing recent Caddy logs..."
        $DOCKER_COMPOSE logs --tail=50 $COMPOSE_SERVICE
    fi
}

# Open shell
open_shell() {
    log_info "Opening interactive shell in Caddy container..."
    cd "$SCRIPT_DIR"
    $DOCKER_COMPOSE exec $COMPOSE_SERVICE /bin/sh
}

# Execute command
exec_command() {
    if [[ $# -eq 0 ]]; then
        log_error "No command specified for exec"
        exit 1
    fi
    
    log_info "Executing: $*"
    cd "$SCRIPT_DIR"
    $DOCKER_COMPOSE exec $COMPOSE_SERVICE "$@"
}

# Run app.py
run_app() {
    log_info "Running app.py with arguments: $*"
    cd "$SCRIPT_DIR"
    $DOCKER_COMPOSE exec $COMPOSE_SERVICE app "$@"
}

# Show certificates
show_certificates() {
    log_info "Retrieving Caddy internal certificates..."
    cd "$SCRIPT_DIR"
    $DOCKER_COMPOSE exec $COMPOSE_SERVICE app --show-certs
}

# Force rebuild
force_rebuild() {
    log_info "Force rebuilding Caddy with DNS provider..."
    cd "$SCRIPT_DIR"
    $DOCKER_COMPOSE exec $COMPOSE_SERVICE app --force-build
}

# Show config
show_config() {
    log_info "Current configuration:"
    cd "$SCRIPT_DIR"
    echo
    echo "=== config.yml ==="
    cat config.yml 2>/dev/null || log_warn "config.yml not found"
    echo
    echo "=== Generated Files in /data ==="
    $DOCKER_COMPOSE exec $COMPOSE_SERVICE sh -c "ls -la /data/ && echo && echo '=== Caddyfile Preview ===' && head -20 /data/Caddyfile 2>/dev/null || echo 'Caddyfile not found'" 2>/dev/null || log_warn "Could not access container files"
    echo
    echo "=== Container Status ==="
    $DOCKER_COMPOSE ps
}

# Show status
show_status() {
    log_info "Container status:"
    cd "$SCRIPT_DIR"
    $DOCKER_COMPOSE ps
    echo
    log_info "Resource usage:"
    $DOCKER_COMPOSE exec $COMPOSE_SERVICE sh -c "df -h /data && echo && free -h" 2>/dev/null || log_warn "Could not retrieve resource usage"
}

# Show data directory contents
show_data() {
    log_info "Contents of /data directory:"
    cd "$SCRIPT_DIR"
    $DOCKER_COMPOSE exec $COMPOSE_SERVICE sh -c "
        echo 'Data Directory Structure:'
        ls -la /data/
        echo
        echo 'Generated Caddyfile:'
        cat /data/Caddyfile 2>/dev/null || echo 'Caddyfile not found'
        echo
        echo 'Generated dnsmasq.conf:'
        cat /data/dnsmasq.conf 2>/dev/null || echo 'dnsmasq.conf not found'
        echo
        echo 'Recent Logs:'
        tail -20 /data/logs/app.log 2>/dev/null || echo 'No logs found'
    " 2>/dev/null || log_warn "Could not access container"
}

# Build images
build_images() {
    log_info "Building Docker images..."
    cd "$SCRIPT_DIR"
    $DOCKER_COMPOSE build --no-cache
    log_success "Images built"
}

# Stop and remove everything
down_services() {
    log_info "Stopping and removing containers..."
    cd "$SCRIPT_DIR"
    $DOCKER_COMPOSE down
    log_success "Containers removed"
}

# Clean everything
clean_all() {
    log_warn "This will remove containers, networks, and volumes. Are you sure? (y/N)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        log_info "Cleaning up everything..."
        cd "$SCRIPT_DIR"
        $DOCKER_COMPOSE down -v --remove-orphans
        docker system prune -f
        log_success "Cleanup complete"
    else
        log_info "Cleanup cancelled"
    fi
}

# Main script logic
main() {
    check_docker_compose
    
    if [[ $# -eq 0 ]]; then
        show_usage
        exit 0
    fi
    
    case "${1:-}" in
        start)
            start_services
            ;;
        stop)
            stop_services
            ;;
        restart)
            restart_services
            ;;
        logs)
            shift
            show_logs "$@"
            ;;
        shell)
            open_shell
            ;;
        exec)
            shift
            exec_command "$@"
            ;;
        app)
            shift
            run_app "$@"
            ;;
        show-certs)
            show_certificates
            ;;
        force-rebuild)
            force_rebuild
            ;;
        config)
            show_config
            ;;
        data)
            show_data
            ;;
        status)
            show_status
            ;;
        build)
            build_images
            ;;
        down)
            down_services
            ;;
        clean)
            clean_all
            ;;
        help|--help|-h)
            show_usage
            ;;
        *)
            log_error "Unknown command: $1"
            echo
            show_usage
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"
