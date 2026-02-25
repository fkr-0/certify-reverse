SHELL := /bin/bash
.DEFAULT_GOAL := help

VERSION_FILE := pyproject.toml
VERSION := $(shell sed -n 's/^version = "\([0-9]\+\.[0-9]\+\.[0-9]\+\)"/\1/p' $(VERSION_FILE))

.PHONY: help start stop restart logs status down clean build verify version bump-patch bump-minor bump-major release-note

help:
	@echo "Targets:"
	@echo "  start        Start services"
	@echo "  stop         Stop services"
	@echo "  restart      Restart services"
	@echo "  logs         Follow logs"
	@echo "  status       Show status"
	@echo "  down         Stop and remove containers"
	@echo "  clean        Interactive cleanup"
	@echo "  build        Rebuild images"
	@echo "  verify       Run local verification checks"
	@echo "  version      Print current semantic version"
	@echo "  bump-patch   Bump X.Y.Z -> X.Y.(Z+1)"
	@echo "  bump-minor   Bump X.Y.Z -> X.(Y+1).0"
	@echo "  bump-major   Bump X.Y.Z -> (X+1).0.0"
	@echo "  release-note Print suggested release title"

start:
	./caddy-docker.sh start

stop:
	./caddy-docker.sh stop

restart:
	./caddy-docker.sh restart

logs:
	./caddy-docker.sh logs --follow

status:
	./caddy-docker.sh status

down:
	./caddy-docker.sh down

clean:
	./caddy-docker.sh clean

build:
	./caddy-docker.sh build

verify:
	python3 -m py_compile app.py status.py templates.py
	bash -n caddy-docker.sh
	sh -n boot.sh
	docker compose config >/dev/null

version:
	@echo $(VERSION)

bump-patch:
	@python3 scripts/bump_version.py patch

bump-minor:
	@python3 scripts/bump_version.py minor

bump-major:
	@python3 scripts/bump_version.py major

release-note:
	@echo "Release v$(VERSION)"
