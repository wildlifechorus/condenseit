# Deployment

CondenseIt runs in two modes: local (on your machine) or remote (on a VPS).
Both use the same web UI, API, and admin panel.

## Local deployment

Start the web UI and admin panel on your machine:

```bash
condenseit serve --port 8899
```

Open `http://localhost:8899`. Run digests from the UI or with `condenseit run`.

Enable the built-in scheduler so digests run automatically:

```
CONDENSEIT_SCHEDULER_ENABLED=1  # in .env
```

The scheduler reads `config.schedule.times` (default `["07:00", "18:00"]`).

## Remote deployment (VPS)

### One-time server setup

1. Copy the nginx template and edit for your domain:

   ```bash
   cp scripts/nginx/digest.example.com.conf scripts/nginx/your.domain.conf
   # Replace digest.example.com with your domain in the file
   ```

2. Set SSH connection in `.env`:

   ```
   DIGEST_PWA_SSH_HOST=your-ssh-alias   # or user@ip
   DIGEST_PWA_DOMAIN=your.domain
   ```

3. Run the bootstrap script (prompts for secrets):

   ```bash
   ./scripts/bootstrap-server.sh
   ```

   This installs condenseit, the systemd service, nginx vhost, and writes
   `~/condenseit/.env` on the VPS with your OpenRouter key and app password.

4. Get a TLS certificate (after DNS is pointed at your VPS):

   ```bash
   ssh your-vps 'sudo certbot --nginx -d your.domain'
   ```

### Deploying updates

```bash
./scripts/deploy.sh
```

This builds the frontend, packages a wheel, rsyncs everything to the VPS,
and restarts the `condenseit-web` service.

### Service management

```bash
# Logs
ssh your-vps 'journalctl -u condenseit-web -f'

# Status
ssh your-vps 'sudo systemctl status condenseit-web'

# Restart
ssh your-vps 'sudo systemctl restart condenseit-web'
```

## Environment variables

See [`.env.example`](../.env.example) for all variables with comments.
See [`configuration.md`](configuration.md) for YAML config options.
