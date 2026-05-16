# Scripts reference

## Deployment scripts

### `scripts/deploy.sh`

Builds the frontend SPA, packages a condenseit wheel, rsyncs everything to
the VPS, and restarts the `condenseit-web` systemd service.

```bash
./scripts/deploy.sh              # full build + deploy
./scripts/deploy.sh --skip-build # rsync only, no rebuild
```

Requires `DIGEST_PWA_SSH_HOST` and `DIGEST_PWA_DOMAIN` in `.env` (or the
`vps` section of `config.yaml`).

### `scripts/bootstrap-server.sh`

One-time VPS setup. Prompts for your OpenRouter API key and app password,
creates the Python venv, installs condenseit, writes `~/condenseit/.env`
on the VPS, installs a systemd unit with `EnvironmentFile`, and configures
nginx.

```bash
./scripts/bootstrap-server.sh
```

### `scripts/provision-ubuntu.sh`

Prepare a fresh Ubuntu 24.04 VPS before bootstrapping: installs nginx,
python3, certbot, ufw, fail2ban, rsync, creates a swap file, and enables
unattended security upgrades.

```bash
ssh digest-vps 'bash -s' < scripts/provision-ubuntu.sh
```

Run this once before `bootstrap-server.sh`. See [deploy-vps.md](deploy-vps.md)
for the full step-by-step guide.

### `scripts/firebase-deploy.sh`

Deploy the full stack to Firebase Hosting + Cloud Run. Enables GCP APIs,
creates the Artifact Registry repo and GCS bucket on first run, builds the
frontend, builds and pushes the Docker image, deploys the Cloud Run service,
and deploys the SPA to Firebase Hosting.

```bash
./scripts/firebase-deploy.sh
./scripts/firebase-deploy.sh --skip-build  # re-deploy without rebuilding
```

Requires `FIREBASE_PROJECT_ID` in `.env` and local `gcloud`, `firebase`, and
`docker` CLIs. See [deploy-firebase.md](deploy-firebase.md) for full setup.

## Docker scripts

### `scripts/docker-up.sh` / `scripts/docker-down.sh`

Start or stop the Docker web UI container.

```bash
./scripts/docker-up.sh
./scripts/docker-down.sh
```

### `scripts/docker-run.sh`

Run a digest inside a Docker helper container (Ollama must be running on the
host at `host.docker.internal`).

### `scripts/docker-ui-digest.sh`

Combined helper: starts the web UI container, runs a digest on the host, then
stops the container.

### `scripts/docker-dry-run.sh`

Alias for `run-without-ollama.sh` (collect only, no LLM) run via Docker
conventions.

## Local Ollama scripts

### `scripts/run-with-ollama.sh`

Run a full digest on the host using a local Ollama instance (Metal on Apple
Silicon).

```bash
./scripts/run-with-ollama.sh
```

### `scripts/run-without-ollama.sh`

Dry run: collect and rank feeds only, no LLM summarization. Useful for
testing sources and config quickly.

```bash
./scripts/run-without-ollama.sh
```

### `scripts/native-dry-run.sh`

Alias for `run-without-ollama.sh`.

### `scripts/native-setup.sh`

One-time local setup: creates the Python venv, pulls the configured Ollama
model, and builds the frontend.

```bash
./scripts/native-setup.sh
```

### `scripts/native-serve.sh`

Start the web UI natively (without Docker). Builds the frontend automatically
on first run if `frontend/dist` is missing.

```bash
./scripts/native-serve.sh
PORT=8080 ./scripts/native-serve.sh
```

## Install helper

### `scripts/install.sh`

Interactive helper that checks prerequisites, optionally copies
`config.example.yaml` and `.env.example`, and prints ready-to-paste cron
lines and a launchd plist snippet for a chosen run time and cadence.

```bash
bash scripts/install.sh
INSTALLER_NONINTERACTIVE=1 bash scripts/install.sh
```

> **Note:** If you use `CONDENSEIT_SCHEDULER_ENABLED=1`, the built-in
> scheduler handles digest runs automatically at the times set in
> `config.schedule.times`. `install.sh` is only needed if you prefer cron or
> launchd for scheduling.

## Maintenance

### `scripts/cleanup-condenseit-logs.sh`

Trim old log files.

```bash
./scripts/cleanup-condenseit-logs.sh all-safe
```

### `scripts/export-config.sh`

Print a sanitized view of `config.yaml` with secret values (API keys,
passwords) redacted. Useful for sharing config for debugging.

```bash
./scripts/export-config.sh
```

### `scripts/teardown-after-digest.sh`

Stop the Docker web UI stack and the Ollama Homebrew launch agent after a
scheduled digest run. Used in automation setups that start and stop services
around each run.

```bash
./scripts/teardown-after-digest.sh
```

## Makefile shortcuts

```bash
make serve            # Start web UI locally
make run              # Run digest once
make dry-run          # Collect without LLM
make native-setup     # One-time local setup
make native-serve     # Start web UI (builds frontend if missing)
make run-with-ollama  # Full digest with local Ollama
make run-without-ollama # Dry run
make docker-up        # Start Docker web UI
make docker-down      # Stop Docker web UI
make docker-run       # Digest via Docker helper
make build-frontend   # Build frontend/dist
make deploy           # Build + deploy to VPS
make bootstrap        # One-time VPS setup
make logs-clean       # Trim log files
make test             # Run pytest
make lint             # Run ruff
```
