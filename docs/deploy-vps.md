# Deploy to a VPS (Ubuntu 24.04 / Hetzner)

CondenseIt runs well on a small Ubuntu 24.04 VPS. This guide uses Hetzner
Cloud as the provider example but the steps apply to any Ubuntu 24.04 server
(DigitalOcean, Linode, AWS EC2, etc.).

## Architecture

```
Browser → nginx (80/443, TLS via Certbot)
              │
              ├── /api/**  → uvicorn at 127.0.0.1:8765 (condenseit-web.service)
              └── /**      → /var/www/your.domain  (frontend/dist, static files)
```

- **nginx** terminates TLS and serves the static SPA directly from disk.
- **condenseit-web.service** (systemd) runs uvicorn on a local port.
- SQLite lives at `~/condenseit/data/condenseit.db` on the VPS.
- The built-in scheduler handles digest runs if you enable it.

## Prerequisites

| Item | Notes |
|------|-------|
| Hetzner Cloud account | [console.hetzner.cloud](https://console.hetzner.cloud) |
| SSH key | Generate one locally if you do not have one |
| Domain name | Pointed at the VPS IP via an A record |
| Local tools: `uv`, `rsync`, `ssh` | Already installed on macOS |

## Step 1: create and connect to the server

### Via Hetzner Cloud Console

1. Go to **New Server**.
2. Select **Ubuntu 24.04** as the image.
3. Pick a type: **CX22** (2 vCPU, 4 GB RAM) is enough for personal use.
4. Select your SSH key (or paste the public key).
5. Create the server and note the IP address.

### Via hcloud CLI (optional)

```bash
# Install hcloud
brew install hcloud   # macOS

# Create server
hcloud server create \
  --name condenseit \
  --type cx22 \
  --image ubuntu-24.04 \
  --ssh-key ~/.ssh/id_ed25519.pub \
  --location nbg1
```

### Add an SSH alias

Add to `~/.ssh/config` on your local machine:

```
Host digest-vps
    HostName 203.0.113.10      # replace with your actual IP
    User root
    IdentityFile ~/.ssh/id_ed25519
```

Test the connection:

```bash
ssh digest-vps 'echo ok'
```

## Step 2: provision the server (run once)

The provisioning script installs system dependencies on the fresh Ubuntu 24.04
server. Run it from your local machine:

```bash
ssh digest-vps 'bash -s' < scripts/provision-ubuntu.sh
```

Or copy it and run it directly on the server:

```bash
scp scripts/provision-ubuntu.sh digest-vps:/tmp/
ssh digest-vps 'sudo bash /tmp/provision-ubuntu.sh'
```

This installs: nginx, python3, certbot, ufw, fail2ban, rsync, curl. It also
creates a 2 GB swap file and enables unattended security upgrades.

## Step 3: configure your local `.env`

Add to `.env` in the repo root:

```
DIGEST_PWA_SSH_HOST=digest-vps       # matches your ~/.ssh/config alias
DIGEST_PWA_DOMAIN=your.domain        # e.g. digest.example.com
CONDENSEIT_AUTH_PASSWORD=strong-password
```

`DIGEST_PWA_AUTH_PASSWORD` is still accepted for older deployments, but new
installs should use `CONDENSEIT_AUTH_PASSWORD`.

Optional:

```
OPENROUTER_API_KEY=sk-or-...
CONDENSEIT_VPS_PORT=8765             # default, change if needed
CONDENSEIT_SCHEDULER_ENABLED=1      # run digests automatically
```

## Step 4: copy the nginx template

```bash
cp scripts/nginx/digest.example.com.conf scripts/nginx/your.domain.conf
```

Edit the new file and replace every occurrence of `digest.example.com` with
your actual domain. Also update the log paths if you like.

## Step 5: bootstrap the VPS (run once)

From your local machine, with the project root as the working directory:

```bash
./scripts/bootstrap-server.sh
```

This will:

1. Build a Python wheel and upload it to the VPS.
2. Prompt for your OpenRouter API key, app password, and scheduler preference.
3. Write `~/condenseit/.env` on the VPS (secrets stay on the server, never
   in git).
4. Install the `condenseit-web` systemd service and start it.
5. Install and enable the nginx vhost.

## Step 6: deploy

```bash
./scripts/deploy.sh
```

This builds the frontend, packages a new wheel, rsyncs everything to the VPS,
and restarts the service.

## Step 7: enable TLS

Once the DNS A record for your domain is pointing at the VPS IP:

```bash
ssh digest-vps 'sudo certbot --nginx -d your.domain'
```

Certbot will edit the nginx config and enable HTTPS with auto-renewal.

Verify renewal works:

```bash
ssh digest-vps 'sudo certbot renew --dry-run'
```

## Deploying updates

After changing code, config, or feeds:

```bash
./scripts/deploy.sh
```

Skip the frontend build if only the Python code changed:

```bash
./scripts/deploy.sh --skip-build
```

## Service management

```bash
# View live logs
ssh digest-vps 'journalctl -u condenseit-web -f'

# Last 50 lines
ssh digest-vps 'journalctl -u condenseit-web -n 50'

# Status
ssh digest-vps 'sudo systemctl status condenseit-web'

# Restart
ssh digest-vps 'sudo systemctl restart condenseit-web'

# Stop
ssh digest-vps 'sudo systemctl stop condenseit-web'
```

## Updating configuration

The VPS reads `~/condenseit/.env` and `~/condenseit/config.yaml`. After
`deploy.sh` syncs a new wheel you can also push a fresh config:

```bash
# Push config only (no code rebuild)
ssh digest-vps 'cat > ~/condenseit/config.yaml' < config.yaml
ssh digest-vps 'sudo systemctl restart condenseit-web'
```

## Backups

The SQLite database lives at `~/condenseit/data/condenseit.db` on the VPS.
Back it up before major updates:

```bash
ssh digest-vps 'cp ~/condenseit/data/condenseit.db ~/condenseit/data/condenseit.db.bak'
```

Or pull it locally:

```bash
rsync -avz digest-vps:~/condenseit/data/condenseit.db ./data/condenseit.db.remote
```

## Troubleshooting

**Cannot SSH to the VPS**

Check the IP in `~/.ssh/config` matches the Hetzner console, and that the SSH
key is added to the server.

**Bootstrap fails: "No nginx config found"**

Copy and edit the template as described in Step 4, then re-run
`./scripts/bootstrap-server.sh`.

**Service starts but the domain returns 502**

The systemd service might be on a different port from what nginx expects.
Verify `CONDENSEIT_VPS_PORT` matches the `proxy_pass` port in the nginx conf
(default `8765`).

**Certbot fails: "Connection refused" or timeout**

DNS has not propagated yet. Wait and retry. Use
`dig +short your.domain @8.8.8.8` to check.

**Out of memory on a small VPS (CX11)**

The swap file created by `provision-ubuntu.sh` (2 GB) should handle this.
Alternatively, upgrade to CX22 or reduce `max_articles_per_digest` in
`config.yaml`.
