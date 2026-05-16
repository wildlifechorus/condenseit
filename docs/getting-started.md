# Getting started

For a full **local install** (uv, `config.yaml`, `.env`, first run), see
[installation.md](installation.md). To run digests on a **schedule** (cron,
systemd, launchd), see [scheduling.md](scheduling.md).

Quick path:

1. Copy `config.example.yaml` to `config.yaml` and adjust feeds and channels.
2. Install Ollama on the host (Mac: Metal GPU). Pull a small model, for example
   `ollama pull llama3.2:3b`.
3. Install deps: `uv sync` (see [installation.md](installation.md)) or a
   venv with `pip install -e ".[dev]"`.
4. Run the web UI: `condenseit serve` (or `make docker-up` for Docker UI only).
5. Run a digest: use **Run digest** in the header, or `uv run condenseit run`
   (or `condenseit run` if your shell uses the project venv).

See [configuration.md](configuration.md) for YAML and environment variables.

For **Docker UI + host digest**, dry runs, and what each script does, see
[scripts.md](scripts.md).

Optional: `bash scripts/install.sh` (or `bash install.sh` from the repo root)
prints cron and LaunchAgent snippets from your chosen time and cadence (see
[installation.md](installation.md)).
