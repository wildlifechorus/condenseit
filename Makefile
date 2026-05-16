.PHONY: install dev test lint run dry-run serve docker-ui-digest \
	docker-up docker-down docker-run docker-dry-run \
	run-with-ollama run-with-ollama-pwa-deploy run-without-ollama native-setup \
	seed-next-pwa-deploy-sources \
	native-serve digest-pwa digest-pwa-deploy digest-pwa-bootstrap \
	schedule-install schedule-uninstall schedule-status teardown logs-clean

PYTHON ?= $(shell if [ -x .venv/bin/python ]; then echo .venv/bin/python; else echo python3; fi)

install:
	pip install -e .

dev:
	pip install -e ".[dev]"

run:
	condenseit run

dry-run:
	condenseit run --dry-run

serve:
	condenseit serve --port 8899

# Docker UI + native digest (see ./scripts/docker-ui-digest.sh ui | restart)
docker-ui-digest:
	./scripts/docker-ui-digest.sh

# UI in Docker (rebuilds image FE), digest on host, then static PWA build + rsync
run-with-ollama-pwa-deploy: seed-next-pwa-deploy-sources
	./scripts/run-with-ollama.sh && ./scripts/deploy-digest-pwa.sh

# UI in Docker; digest on host (Ollama / Metal)
run-with-ollama:
	./scripts/run-with-ollama.sh

seed-next-pwa-deploy-sources:
	$(PYTHON) scripts/seed-next-pwa-deploy-sources.py

run-without-ollama:
	./scripts/run-without-ollama.sh

native-setup:
	./scripts/native-setup.sh

native-serve:
	./scripts/native-serve.sh

docker-up:
	./scripts/docker-up.sh

docker-down:
	./scripts/docker-down.sh

docker-run:
	./scripts/docker-run.sh

docker-dry-run:
	./scripts/docker-dry-run.sh

digest-pwa:
	condenseit pwa-build

digest-pwa-deploy:
	./scripts/deploy-digest-pwa.sh

digest-pwa-bootstrap:
	./scripts/bootstrap-digest-pwa-server.sh

teardown:
	./scripts/teardown-after-digest.sh

# launchd agent: twice-daily digest at 06:00 and 21:00
PLIST_SRC  := launchd/com.condenseit.scheduled-digest.plist
PLIST_DEST := $(HOME)/Library/LaunchAgents/com.condenseit.scheduled-digest.plist
AGENT_LABEL := com.condenseit.scheduled-digest

schedule-install:
	cp "$(PLIST_SRC)" "$(PLIST_DEST)"
	launchctl load -w "$(PLIST_DEST)"
	@echo "Installed. Next runs: 06:00 and 21:00 daily."
	@echo "Force a manual run: make schedule-run"

schedule-uninstall:
	launchctl unload "$(PLIST_DEST)" 2>/dev/null || true
	rm -f "$(PLIST_DEST)"
	@echo "Uninstalled."

schedule-status:
	launchctl list $(AGENT_LABEL) 2>/dev/null || echo "Agent not loaded"

schedule-run:
	launchctl start $(AGENT_LABEL)

# Trim digest logs when safe (skips files another process has open).
logs-clean:
	./scripts/cleanup-condenseit-logs.sh all-safe

test:
	pytest -q

lint:
	ruff check src tests
