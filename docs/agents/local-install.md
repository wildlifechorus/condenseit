# Agent guide: deploy CondenseIt locally

This document is for an AI coding agent setting up CondenseIt on a developer's
local machine. Follow phases in order. Verify each step's output before
continuing.

---

## Context

CondenseIt is a Python/FastAPI app with a Preact SPA frontend and an SQLite
database. For local deployment it runs natively with `uv` or inside Docker
(web UI only; digests run on the host). The recommended path is native.

---

## Phase 0: check prerequisites

Run all checks. Do not proceed past a failing check without resolving it first.

```bash
# Python 3.11+
python3 --version
# Expected: Python 3.11.x, 3.12.x, or newer

# uv
uv --version
# Expected: uv 0.x.x
# Install if missing: pip install uv   or   brew install uv

# Node.js 18+
node --version
# Expected: v18.x.x, v20.x.x, or newer

# npm
npm --version
# Expected: 10.x.x or newer

# Ollama (optional - only needed for local LLM)
ollama --version
# Expected: ollama version x.x.x
# Install from https://ollama.ai if you want local LLM inference
```

---

## Phase 1: clone the repository

```bash
git clone https://github.com/wildlifechorus/condenseit
cd condenseit
```

Verify:

```bash
ls pyproject.toml config.example.yaml .env.example
# All three files must be present
```

---

## Phase 2: install Python dependencies

```bash
uv sync
```

Verify:

```bash
uv run condenseit --help
# Expected: usage text with commands: run, serve, ratings-import, read-import, status
```

---

## Phase 3: pull an Ollama model (skip if using OpenRouter)

```bash
ollama pull llama3.2:3b
```

Wait for the download to complete. Verify:

```bash
ollama list
# Expected: llama3.2:3b appears in the list
```

If Ollama is not running, start it:

```bash
ollama serve &
```

---

## Phase 4: create config files

```bash
cp config.example.yaml config.yaml
cp .env.example .env
```

### 4.1 Edit `config.yaml`

At minimum:
- Add at least one feed to the `feeds:` section (examples are already there).
- Verify `llm.provider` is `"ollama"` (or change to `"openrouter"` if skipped
  Phase 3).

For OpenRouter, also set:

```yaml
llm:
  provider: "openrouter"
  openrouter_model: "openai/gpt-4o-mini"
  openrouter_daily_budget_usd: 0.50
```

### 4.2 Edit `.env`

Set values for the tools you are using:

```
# Ollama (default port is fine for local installs)
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b

# OpenRouter (if using cloud LLM instead of Ollama)
OPENROUTER_API_KEY=sk-or-...

# Optional: built-in scheduler
CONDENSEIT_SCHEDULER_ENABLED=1
```

Verify no placeholder values remain that would cause errors:

```bash
grep 'your-' .env | grep -v '^#'
# Expected: empty (no un-substituted placeholder lines)
```

---

## Phase 5: build the frontend

```bash
cd frontend
npm ci
npm run build
cd ..
```

Verify:

```bash
ls frontend/dist/index.html
# Expected: file exists
```

---

## Phase 6: start the web UI

```bash
uv run condenseit serve
```

Expected output:

```
INFO:     Uvicorn running on http://127.0.0.1:8899 (Press CTRL+C to quit)
```

Open [http://localhost:8899](http://localhost:8899) in a browser. The Preact
SPA should load.

---

## Phase 7: run a digest

In a second terminal (or from the web UI header):

```bash
cd /path/to/condenseit
uv run condenseit run
```

Expected output shows feed collection, LLM summarization, and finishes with:

```
[condenseit] Digest complete. X articles.
```

Return to the browser. The digest should appear in the left sidebar.

---

## Phase 8: enable the built-in scheduler (optional)

If `CONDENSEIT_SCHEDULER_ENABLED=1` is set in `.env`, the server already runs
digests automatically at the times in `config.schedule.times` (default `07:00`
and `18:00`). Verify the scheduler is active:

```bash
curl -sf http://localhost:8899/api/scheduler/status
# Expected: {"enabled":true,"next_run":"..."}
```

No cron or launchd entry is needed when using the built-in scheduler.

For manual cron scheduling instead, see `docs/scheduling.md`.

---

## Phase 9: verify the full setup

### 9.1 Health endpoint

```bash
curl -sf http://localhost:8899/api/health
# Expected: {"status":"ok"}
```

### 9.2 Admin sources

```bash
curl -sf http://localhost:8899/api/admin/sources
# Expected: JSON array of configured sources
```

### 9.3 Ratings (empty on fresh install)

```bash
curl -sf http://localhost:8899/api/ratings
# Expected: []
```

### 9.4 Check the UI

Navigate to [http://localhost:8899](http://localhost:8899):
- The most recent digest is visible in the sidebar.
- Admin > Sources shows the feeds from `config.yaml`.
- Admin > LLM Config shows the configured provider and model.
- `/admin` redirects to `/admin/sources`.

---

## Docker alternative (web UI only)

If the user prefers Docker instead of native:

```bash
# Start the web UI container
./scripts/docker-up.sh

# Run a digest on the host (keeps Metal GPU acceleration)
uv run condenseit run

# Stop
./scripts/docker-down.sh
```

Docker shares `./data/` with the host so both paths see the same SQLite
database.

---

## Troubleshooting checklist

| Symptom | Action |
|---------|--------|
| `uv: command not found` | `pip install uv` or `brew install uv` |
| `condenseit: command not found` | Use `uv run condenseit` instead |
| Frontend shows blank page | Verify `frontend/dist/index.html` exists; rebuild with `cd frontend && npm run build` |
| Ollama timeout during digest | Ensure `ollama serve` is running; check `OLLAMA_HOST` in `.env` |
| OpenRouter 401 error | Check `OPENROUTER_API_KEY` in `.env` is valid |
| Port 8899 already in use | Use `condenseit serve --port 9000` |
| Digests not appearing in UI | Check the terminal running `condenseit serve` for Python errors |
| `uv sync` fails on Python version | Install Python 3.11 or 3.12: `brew install python@3.12` |
