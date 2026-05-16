# Shell scripts (`scripts/`)

Bash helpers under `scripts/` start the **Docker web UI**, run the **digest
pipeline on the host** (Ollama with Metal on Mac, or `--dry-run`), and cover
install, config export, and optional PWA deploy. The **CLI** (`condenseit`)
remains the source of truth; scripts wrap common flows from the repo root.

For prerequisites and `uv` setup, see [installation.md](installation.md).
For digest PWA and nginx, see [digest-pwa.md](digest-pwa.md).

## Where components run

| Piece | Typical location |
|-------|------------------|
| Web UI (digest pages, admin, ratings) | **Docker** (`docker compose`) |
| `condenseit run` with Ollama | **Host** (not in the UI container) |

Shared data: `./data` is mounted into the UI container so native runs show up
in the browser.

## Canonical entry points

Use these when you are unsure which file to run:

| Script | Purpose |
|--------|---------|
| `scripts/run-with-ollama.sh` | Bring up the UI stack, then `condenseit run` on the host (full digest). |
| `scripts/run-without-ollama.sh` | `condenseit run --dry-run` on the host. Add `--with-ui` first to start Docker UI. |

**Optional first argument to `run-with-ollama.sh`:**

- `native` … `exec` `native-run.sh` only (no Docker UI step). Same as
  `scripts/native-run.sh` with the same trailing flags.
- `docker` … strip that token, then UI up + digest (rare; for symmetry).

Any other first token (for example `--dry-run`) is left in place and passed to
`condenseit run` after the UI step.

## Thin aliases (same flows, stable names)

| Script | Behavior |
|--------|----------|
| `scripts/docker-run.sh` | Same as `run-with-ollama.sh`, but sets `CONDENSEIT_DOCKER_UI_BEST_EFFORT=1` so a failing `docker compose` does not block the digest. |
| `scripts/docker-dry-run.sh` | Same as `run-without-ollama.sh` without `--with-ui`. Keeps `make docker-dry-run` and old habits working. |

## Docker UI only

Compose sets `CONDENSEIT_FRONTEND_DIST=/app/frontend/dist` so the FastAPI app
serves the Vite bundle from the image instead of legacy Jinja templates.

| Script | Purpose |
|--------|---------|
| `scripts/docker-up.sh` | `ensure_config`, `data/digests`, `docker compose up -d --build`, print URLs. |
| `scripts/docker-down.sh` | `docker compose down`. |

If `CONDENSEIT_DOCKER_UI_BEST_EFFORT=1` is set in the environment,
`docker-up.sh` runs compose with errors ignored (used by `docker-run.sh`).

## Native pipeline (no Docker orchestration in the script body)

| Script | Purpose |
|--------|---------|
| `scripts/native-setup.sh` | `config.yaml` if missing, venv + `pip install -e .`, `ollama pull` when `ollama` is on `PATH`. |
| `scripts/native-run.sh` | `condenseit run` with your args. |
| `scripts/native-dry-run.sh` | `condenseit run --dry-run`. |
| `scripts/native-serve.sh` | `condenseit serve` (default port `8899`, override with `PORT`). |

## `docker-ui-digest.sh` (all-in-one helper)

Combines UI lifecycle and digest in one script:

| Invocation | Effect |
|------------|--------|
| `./scripts/docker-ui-digest.sh` | Same as `run-with-ollama.sh` with the same trailing args. |
| `./scripts/docker-ui-digest.sh run …` | Leading `run` is stripped, then same as above. |
| `./scripts/docker-ui-digest.sh ui` | UI only (`docker-up.sh`). |
| `./scripts/docker-ui-digest.sh restart` | `docker-down.sh` then `docker-up.sh`. |

For UI-only or digest-only without this wrapper, use `make docker-up` or
`make run` (see [Makefile](../Makefile)).

## Shared library

`scripts/lib/common.sh` sets `ROOT`, `cd` to the repo root, and defines:

- `log`
- `ensure_config` (copy `config.example.yaml` to `config.yaml` if missing)
- `ensure_venv` (create `.venv`, activate, `pip install -e .`)

Scripts that need the repo root should `source` this file unless they only
`exec` another script that already does.

## Other scripts

| Script | Purpose |
|--------|---------|
| `scripts/install.sh` | Interactive installer, config copies, cron and launchd snippets (see [installation.md](installation.md)). |
| `scripts/export-config.sh` | Print `config.yaml` with lines that look like secret keys removed. Override file with `CONDENSEIT_CONFIG`. |
| `scripts/bootstrap-digest-pwa-server.sh` | One-time server prep for the static digest site. |
| `scripts/deploy-digest-pwa.sh` | Build PWA, rsync, nginx reload (see [digest-pwa.md](digest-pwa.md); SSH defaults from `vps.*` in `config.yaml`). |
| `scripts/lib/pwa-vps-from-config.sh` | Shared helper: load `vps.host` / `vps.path` / `vps.digest_url` for PWA scripts. |
| `scripts/setup-vps.sh` | Optional VPS helper (see script header and [deployment.md](deployment.md)). |

Templates: `scripts/nginx/digest.example.com.conf` (copy and rename for your
hostname; see [digest-pwa.md](digest-pwa.md)).

## Makefile targets

From the repo root, `make` delegates to `scripts/` for many of the flows above,
for example:

- `make run-with-ollama`, `make run-without-ollama`
- `make run-with-ollama-pwa-deploy` (same as `make run-with-ollama` then
  `make digest-pwa-deploy`: Docker UI with a fresh image build, host digest,
  then `pwa-build` and rsync to your VPS; see [digest-pwa.md](digest-pwa.md))
- `make docker-up`, `make docker-down`, `make docker-run`, `make docker-dry-run`
- `make native-setup`, `make native-serve`, `make docker-ui-digest`
- `make digest-pwa-deploy`, `make digest-pwa-bootstrap`

Exact commands are in [Makefile](../Makefile).

