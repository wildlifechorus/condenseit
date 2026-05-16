# Scheduling digests

CondenseIt does **not** stay resident as a scheduler. Run `condenseit run` from
cron, **systemd** timers, or macOS **launchd** at the times you want.

Replace placeholders such as `/path/to/condenseit` and `/path/to/uv` with your
machine paths. Cron uses the **server timezone** unless you set `CRON_TZ`.

## One command pattern

From the repo root, typical invocations:

```bash
cd /path/to/condenseit && /path/to/uv run condenseit run
```

If you use a virtualenv instead of `uv run`:

```bash
cd /path/to/condenseit && /path/to/.venv/bin/condenseit run
```

Set `WorkingDirectory` (launchd) or `cd` (cron) so relative `config.yaml` and
`.env` resolve as you expect, or pass absolute `--config` and env vars.

## Examples by cadence

### Once daily at 09:00

**cron** (user crontab: `crontab -e`):

```cron
0 9 * * * cd /path/to/condenseit && /path/to/uv run condenseit run
```

### Twice daily (09:00 and 21:00)

Two lines or one line with multiple time fields is not portable; use **two**
lines:

```cron
0 9 * * * cd /path/to/condenseit && /path/to/uv run condenseit run
0 21 * * * cd /path/to/condenseit && /path/to/uv run condenseit run
```

### Three times daily (evenly spaced, starting 08:00)

Eight hours apart: 08:00, 16:00, 00:00:

```cron
0 8 * * * cd /path/to/condenseit && /path/to/uv run condenseit run
0 16 * * * cd /path/to/condenseit && /path/to/uv run condenseit run
0 0 * * * cd /path/to/condenseit && /path/to/uv run condenseit run
```

Use `bash scripts/install.sh` to generate cron fields and a launchd template
from a first run time and cadence (1x, 2x, or 3x per day with even spacing).

## Linux: systemd user timer

User units live under `~/.config/systemd/user/`. Example **service** at
`~/.config/systemd/user/condenseit-digest.service`:

```ini
[Unit]
Description=CondenseIt digest run

[Service]
Type=oneshot
WorkingDirectory=/path/to/condenseit
ExecStart=/path/to/uv run condenseit run
```

**Timer** at `~/.config/systemd/user/condenseit-digest.timer` (daily at 09:00):

```ini
[Unit]
Description=Run CondenseIt digest daily

[Timer]
OnCalendar=*-*-* 09:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable and start:

```bash
systemctl --user daemon-reload
systemctl --user enable --now condenseit-digest.timer
systemctl --user list-timers
```

For several explicit times, either several `.timer` units or one timer with
multiple `OnCalendar=` lines. See `man systemd.timer`.

## macOS: LaunchAgent

The repo includes an example plist you can copy and edit:

- [`launchd/com.condenseit.digest.plist`](../launchd/com.condenseit.digest.plist)

Copy to your user agents folder and load:

```bash
cp /path/to/condenseit/launchd/com.condenseit.digest.plist \
  ~/Library/LaunchAgents/
# Edit the plist: ProgramArguments, WorkingDirectory, StartCalendarInterval
launchctl load ~/Library/LaunchAgents/com.condenseit.digest.plist
```

After edits to the plist, `launchctl unload` then `launchctl load` again.

## Windows

The shell installer does not configure Windows. Use **Task Scheduler** with a
`condenseit run` action and correct working directory, or run under **WSL** and
use the Linux sections above.

## Related

- [installation.md](installation.md) (clone, `uv sync`, first run, installer)
- [deployment.md](deployment.md) (PWA, nginx, high-level launchd pointer)
