# Deployment notes

## Digest PWA (static public site)

For an installable static digest (for example `digest.example.com` on nginx),
see [digest-pwa.md](digest-pwa.md).

## macOS schedule (launchd)

For cron and systemd timer examples (Linux) and more launchd notes, see
[scheduling.md](scheduling.md).

See `launchd/com.condenseit.digest.plist`. Edit paths to your venv `condenseit`
binary and config, then:

```bash
cp launchd/com.condenseit.digest.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.condenseit.digest.plist
```

## Static site + HTTPS (Caddy)

If you rsync digests to a VPS, Caddy can serve files with automatic HTTPS:

```caddy
digest.example.com {
    root * /var/www/condenseit
    file_server
}
```

Point `vps.digest_url` in `config.yaml` at the public URL for email links.

## Docker UI only

The provided `docker-compose.yml` runs the FastAPI UI. Run `condenseit run` on the
host for Ollama (Metal). Set `OLLAMA_HOST=http://host.docker.internal:11434` in
compose when the UI triggers pulls or digests from inside the container.

For script entry points (`run-with-ollama.sh`, `docker-up.sh`, Make targets, and
environment knobs), see [scripts.md](scripts.md).
