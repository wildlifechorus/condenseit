# Local installation

This guide covers a **native** install with [uv](https://docs.astral.sh/uv/)
(recommended) so you match `requires-python` and dependencies from
[`pyproject.toml`](../pyproject.toml) (`>=3.11`).

Docker runs the web UI only; digests with a local LLM still use the host. For a
full map of `scripts/*.sh` and Make targets, see [scripts.md](scripts.md).

## Prerequisites

- **Python 3.11+** (3.12 is fine).
- **uv** (install: see [uv installation](https://docs.astral.sh/uv/getting-started/installation/)).
- **Git** (to clone the repo).
- **Ollama** on the machine that runs `condenseit run`, if you use the default
  `ollama` provider (not required for a dry run or OpenRouter-only setups).

## Clone and sync

```bash
git clone https://github.com/wildlifechorus/condenseit
cd condenseit
uv sync
```

Optional dev tools (mypy, pytest, ruff):

```bash
uv sync --extra dev
```

## Configuration files

1. Copy the example YAML next to the repo root (or set `CONDENSEIT_CONFIG` later):

   ```bash
   cp config.example.yaml config.yaml
   ```

2. Copy environment template and edit values (no real secrets in git):

   ```bash
   cp .env.example .env
   ```

Adjust feeds in `config.yaml` and set `OLLAMA_HOST`, `OLLAMA_MODEL`, and any
API keys in `.env` as needed. See [configuration.md](configuration.md).

## First run

From the repository root, with dependencies installed:

```bash
uv run condenseit run
```

Serve the web UI:

```bash
uv run condenseit serve
```

The CLI entrypoint is declared in `pyproject.toml` as `condenseit =
"condenseit.cli:cli"`.

## Interactive installer (configs + schedule snippets)

> **Tip:** If you set `CONDENSEIT_SCHEDULER_ENABLED=1` in `.env`, the
> built-in scheduler runs digests automatically at the times in
> `config.schedule.times`. You can skip the installer entirely in that case.

To check prerequisites, optionally create `config.yaml` / `.env` from the
examples, and print **ready-to-paste** cron lines plus a **launchd** plist
template for your chosen time and cadence:

```bash
bash scripts/install.sh
```

From the repo root you can also run:

```bash
bash install.sh
```

For automation or smoke checks (no prompts, default repo root, `09:00`, once
daily):

```bash
INSTALLER_NONINTERACTIVE=1 bash scripts/install.sh
```

Optional environment variables (non-interactive or to skip prompts when you
extend the script later): `INSTALL_DIR`, `INSTALLER_FIRST_TIME`,
`INSTALLER_CADENCE` (`1`, `2`, or `3`), `INSTALLER_SKIP_COPY` (`1` skips the
config copy offer).

Generated lines use your resolved `cd` path and `uv` location so you can paste
them locally; scrub paths if you share the output.

See [scheduling.md](scheduling.md) for manual cron, systemd, and LaunchAgent
setup. **Windows** is not covered by the installer; use Task Scheduler on the
host or run CondenseIt under **WSL** and follow the Linux section in
[scheduling.md](scheduling.md).
