# Scheduling

CondenseIt includes a built-in scheduler that runs digests automatically at
the times you configure. No cron, launchd, or systemd timer needed.

## Enable the scheduler

Set `CONDENSEIT_SCHEDULER_ENABLED=1` in your `.env` file, then start
`condenseit serve`. The scheduler runs as a background task inside the
web service process.

## Configure run times

Open **Admin > Schedule** in the web UI to set the times and save. Changes
take effect immediately without a restart.

You can also set a default in `config.yaml` (used when no times have been
saved via the admin UI yet):

```yaml
schedule:
  times: ["07:00", "18:00"]
```

Times are in UTC (24-hour `HH:MM`). The status response exposes
`next_run_utc` so you can verify the next fire time after saving changes.

## Check scheduler status

The **Schedule** admin page shows whether the scheduler is enabled and the
next scheduled run time. You can also call the API directly:

```
GET /api/scheduler/status
```

Response:

```json
{
  "enabled": true,
  "next_run_utc": "2026-05-17T07:00:00Z",
  "schedule_times": ["07:00", "18:00"]
}
```

## Manual digest trigger

You can always trigger a digest manually from the web UI (the "Run digest"
button in the header) or from the CLI:

```bash
condenseit run
```
