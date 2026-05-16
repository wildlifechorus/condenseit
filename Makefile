.PHONY: install dev test lint run dry-run serve \
	run-with-ollama run-without-ollama native-setup native-serve \
	docker-up docker-down docker-run docker-dry-run docker-ui-digest \
	build-frontend deploy bootstrap logs-clean

PYTHON    ?= $(shell if [ -x .venv/bin/python ]; then echo .venv/bin/python; else echo python3; fi)
CONDENSEIT ?= $(shell if [ -x .venv/bin/condenseit ]; then echo .venv/bin/condenseit; else echo condenseit; fi)

# ---------------------------------------------------------------------------
# Development
# ---------------------------------------------------------------------------

install:
	pip install -e .

dev:
	pip install -e ".[dev]"

# Run the digest pipeline once (local mode).
run:
	$(CONDENSEIT) run

dry-run:
	$(CONDENSEIT) run --dry-run

# Start the web UI and admin panel (local mode).
serve:
	$(CONDENSEIT) serve --port 8899

# ---------------------------------------------------------------------------
# Local helpers
# ---------------------------------------------------------------------------

# One-time setup: venv + Ollama model pull + frontend build.
setup:
	./scripts/native-setup.sh

# Start the web UI (builds frontend if missing).
native-serve:
	./scripts/native-serve.sh

# Run digest with Ollama.
run-with-ollama:
	./scripts/run-with-ollama.sh

# Dry run - collect only, no LLM.
run-without-ollama:
	./scripts/run-without-ollama.sh

native-setup:
	./scripts/native-setup.sh

# ---------------------------------------------------------------------------
# Docker UI
# ---------------------------------------------------------------------------

docker-ui-digest:
	./scripts/docker-ui-digest.sh

docker-up:
	./scripts/docker-up.sh

docker-down:
	./scripts/docker-down.sh

docker-run:
	./scripts/docker-run.sh

docker-dry-run:
	./scripts/docker-dry-run.sh

# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------

build-frontend:
	cd frontend && npm ci && npm run build

# ---------------------------------------------------------------------------
# Remote VPS deployment
# ---------------------------------------------------------------------------

# Deploy to VPS (build frontend + wheel, rsync, restart service).
deploy:
	./scripts/deploy.sh

# One-time VPS setup (venv, systemd unit, nginx, .env).
bootstrap:
	./scripts/bootstrap-server.sh

# ---------------------------------------------------------------------------
# Maintenance
# ---------------------------------------------------------------------------

logs-clean:
	./scripts/cleanup-condenseit-logs.sh all-safe

test:
	pytest -q

lint:
	ruff check src tests
