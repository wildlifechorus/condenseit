# Digest PWA (static nginx deploy)

The digest can be exported as a **static Progressive Web App**: installable on
iOS and Android, offline cache of the last build, same typography as the local
UI (`app.css`).

## Build

```bash
condenseit pwa-build
# or: make digest-pwa
```

Output directory defaults to `data/pwa-dist/` (override with `digest_pwa.output_dir`
in `config.yaml` or `condenseit pwa-build -o /tmp/out`).

Set `vps.digest_url` to your public URL so `index.html` gets a correct `<link
rel="canonical">` (for example `https://digest.example.com`).

## First-time server setup

Pick a hostname (example: `digest.example.com`) and an SSH target (host alias
from `~/.ssh/config`, or `user@203.0.113.10`). Export overrides **or** rely on
the script defaults below, then run from the CondenseIt repo on your laptop:

```bash
chmod +x scripts/bootstrap-digest-pwa-server.sh scripts/deploy-digest-pwa.sh
./scripts/bootstrap-digest-pwa-server.sh
ssh your-ssh-host 'sudo certbot --nginx -d digest.example.com'
```

Use your real SSH host and domain in the `ssh` line (they must match
`DIGEST_PWA_SSH_HOST` and `DIGEST_PWA_DOMAIN`).

Then deploy whenever you have a new digest:

```bash
./scripts/deploy-digest-pwa.sh
# or: make digest-pwa-deploy
```

One step from the repo root (Docker UI with image rebuild, host digest, then
this deploy script): `make run-with-ollama-pwa-deploy` (same as
`make run-with-ollama && make digest-pwa-deploy`). See [scripts.md](scripts.md).

Environment overrides (optional). If you **omit** `DIGEST_PWA_*`, deploy and
bootstrap read **`vps.host`**, **`vps.path`**, and **`vps.digest_url`** from
`config.yaml` (the same fields the digest pipeline uses for post-run rsync).
That way `make run-with-ollama-pwa-deploy` can work with only YAML VPS
settings. You can still set env vars to override YAML for one-off runs.

Defaults when YAML has no `vps.host` are placeholders for a public repo; add a
matching `Host` block in `~/.ssh/config` or set `DIGEST_PWA_SSH_HOST`.

| Variable | If unset, script uses | Final fallback |
|----------|------------------------|----------------|
| `DIGEST_PWA_SSH_HOST` | `vps.host` from `config.yaml` | `digest-vps` |
| `DIGEST_PWA_DOMAIN` | hostname from `vps.digest_url` | `digest.example.com` |
| `DIGEST_PWA_REMOTE_DIR` | `vps.path` from `config.yaml` | `/var/www/<domain>` |
| `DIGEST_PWA_LIVE_URL` | `vps.digest_url` from `config.yaml` | `https://<domain>` |

Bootstrap reads the nginx template at `scripts/nginx/<DIGEST_PWA_DOMAIN>.conf`.
If you use another hostname, copy `scripts/nginx/digest.example.com.conf` to
that filename (same basename as your domain) or adjust the script.

**404 on `/` after deploy:** the example vhost serves `/` from `index.html`
(PWA) first, then `latest.html`. If you copied an older template that only used
`latest.html`, update `location = /` on the server to
`try_files /index.html /latest.html =404;` then `sudo nginx -t && sudo systemctl reload nginx`.

The deploy script prefers `.venv/bin/condenseit` when present (see script body).

## PWA article ratings (remote phone, local pipeline)

Ratings use the **same article URL strings** as the SQLite `ratings` table and
the FastAPI `/rate` page (see `PreferenceEngine`).

On the static PWA:

- Open the digest, use **Rate digest items** (1 to 5 per row), then **Download
  ratings JSON**.
- Ratings persist in **localStorage** on that device. Optional: set
  `digest_pwa.ratings_merge_url` in `config.yaml` before `pwa-build`. At load
  time the PWA GETs that URL and fills **only URLs you have not rated yet** on
  the device (for example a `ratings.json` you uploaded next to the site).

On your laptop before the next `condenseit run`:

1. Save the downloaded file (for example `~/Downloads/condenseit-ratings.json`).
2. Either run **`condenseit ratings-import path/to/condenseit-ratings.json`**
   once, **or** set env **`CONDENSEIT_RATINGS_IMPORT_PATH`** (and optionally
   **`CONDENSEIT_RATINGS_IMPORT_URL`**) so the pipeline imports automatically at
   the start of each run.
3. Optional authenticated URL fetch: set **`CONDENSEIT_RATINGS_IMPORT_BEARER_TOKEN`**
   in `.env` (never commit it). YAML `digest_pwa.ratings_import_url` holds only
   the URL string.

**Limits:** plain nginx cannot accept browser writes to a JSON file. There is
no server-side store in this MVP. Sharing ratings between devices needs export,
upload of a static JSON, or your own small HTTPS endpoint.
