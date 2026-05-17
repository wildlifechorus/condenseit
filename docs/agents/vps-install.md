# Agent guide: deploy CondenseIt to a VPS (Ubuntu 24.04 / Hetzner)

This document is written for an AI coding agent. Follow every phase in order.
Verify each step's output before continuing. Commands labeled **[LOCAL]** run
on the developer's machine; **[SERVER]** run on the VPS.

---

## Architecture overview

```
Browser
  └─→ nginx (port 80/443, TLS via Certbot)
         ├── /api/** → uvicorn at 127.0.0.1:8765 (condenseit-web.service)
         └── /**     → /var/www/<domain>  (frontend/dist, static files)
```

- nginx terminates TLS and serves the static SPA from disk.
- `condenseit-web` (systemd) runs the Python FastAPI backend.
- SQLite lives at `~/condenseit/data/condenseit.db` on the VPS.

---

## Phase 0: prerequisites [LOCAL]

Verify local tools:

```bash
ssh -V           # OpenSSH must be present
rsync --version  # rsync must be present
uv --version     # uv must be present (pip install uv)
node --version   # Node.js 18+ required
```

---

## Phase 1: obtain a VPS with Ubuntu 24.04

### Option A: Hetzner Cloud Console

1. Log in at [console.hetzner.cloud](https://console.hetzner.cloud).
2. Create a new project if needed.
3. Click **Add Server**.
4. Image: **Ubuntu 24.04**.
5. Type: **CX22** (2 vCPU / 4 GB RAM) or larger.
6. SSH keys: add your public key (`~/.ssh/id_ed25519.pub` or similar).
7. Click **Create & Buy Now**.
8. Note the **IPv4 address** shown in the server list.

### Option B: hcloud CLI [LOCAL]

```bash
# Install
brew install hcloud

# Authenticate
hcloud context create condenseit
# Paste your Hetzner API token when prompted

# Create server
hcloud server create \
  --name condenseit \
  --type cx22 \
  --image ubuntu-24.04 \
  --ssh-key ~/.ssh/id_ed25519.pub \
  --location nbg1

# Get IP
hcloud server ip condenseit
```

---

## Phase 2: configure SSH [LOCAL]

Add an alias to `~/.ssh/config`. Replace `203.0.113.10` with the actual IP:

```
Host digest-vps
    HostName 203.0.113.10
    User root
    IdentityFile ~/.ssh/id_ed25519
```

Test the connection:

```bash
ssh digest-vps 'echo "SSH OK"'
# Expected: SSH OK
```

If this fails, check:
- The IP address is correct in `~/.ssh/config`.
- The SSH key was added when creating the server.
- Hetzner firewall/security group allows port 22.

---

## Phase 3: provision the server [LOCAL → SERVER]

Run the provisioning script from the repo root on your local machine:

```bash
ssh digest-vps 'bash -s' < scripts/provision-ubuntu.sh
```

Expected output ends with:

```
[provision] Provisioning complete.
  Python:  Python 3.12.x
  nginx:   nginx/1.x.x
  UFW:     enabled (OpenSSH + Nginx Full)
  fail2ban: enabled

  Next step (run from your LOCAL machine):
    ./scripts/bootstrap-server.sh
```

Verify on the server:

```bash
ssh digest-vps 'nginx -v && python3 --version && ufw status'
# Expected: nginx version, Python 3.12.x, Status: active
```

---

## Phase 4: point DNS at the VPS [DOMAIN REGISTRAR]

Create an A record:

```
your.domain.  300  IN  A  203.0.113.10
```

Replace `203.0.113.10` with the actual server IP and `your.domain` with the
real domain. DNS propagation can take up to 1 hour. Verify:

```bash
dig +short your.domain @8.8.8.8
# Expected: the VPS IP address
```

Do not proceed to TLS until this resolves correctly.

---

## Phase 5: configure local `.env` [LOCAL]

Open `.env` in the repo root. Set or add:

```
DIGEST_PWA_SSH_HOST=digest-vps
DIGEST_PWA_DOMAIN=your.domain
CONDENSEIT_AUTH_PASSWORD=choose-a-strong-password
OPENROUTER_API_KEY=sk-or-...
CONDENSEIT_SCHEDULER_ENABLED=1
```

Optional but recommended:

```
DIGEST_PWA_SESSION_SECRET=<output of: openssl rand -hex 32>
```

---

## Phase 6: copy and edit the nginx template [LOCAL]

```bash
cp scripts/nginx/digest.example.com.conf scripts/nginx/your.domain.conf
```

Edit `scripts/nginx/your.domain.conf`:
- Replace every occurrence of `digest.example.com` with `your.domain`.
- Replace `/var/www/digest.example.com` with `/var/www/your.domain`.

Verify no old domain strings remain:

```bash
grep -c 'digest.example.com' scripts/nginx/your.domain.conf
# Expected: 0
```

---

## Phase 7: bootstrap the VPS [LOCAL]

```bash
./scripts/bootstrap-server.sh
```

The script will:
1. Build and upload the condenseit Python wheel.
2. Prompt for: OpenRouter API key, app password, enable scheduler (Y/n).
3. Write `~/condenseit/.env` on the server.
4. Install and start `condenseit-web.service`.
5. Install nginx vhost.

When prompted:
- **OpenRouter API key**: paste your key or press Enter to skip.
- **App password**: enter the same value as `CONDENSEIT_AUTH_PASSWORD` in `.env`.
- **Enable scheduler**: press Y.

Expected final output:

```
[bootstrap] Bootstrap complete.

  1. Deploy content:
       ./scripts/deploy.sh
  ...
```

Verify the service is running:

```bash
ssh digest-vps 'sudo systemctl status condenseit-web'
# Expected: Active: active (running)
```

---

## Phase 8: deploy content [LOCAL]

```bash
./scripts/deploy.sh
```

This builds the frontend, packages a new wheel, rsyncs to the VPS, and
restarts the service.

Expected output ends with:

```
[deploy] Done. Live URL: https://your.domain
```

Smoke check:

```bash
curl -sf http://your.domain/health
# Expected: {"status":"ok"}
```

---

## Phase 9: enable TLS [LOCAL]

DNS must resolve correctly before this step (verified in Phase 4).

```bash
ssh digest-vps 'sudo certbot --nginx -d your.domain --non-interactive --agree-tos -m admin@your.domain'
```

Wait for Certbot to succeed. Verify HTTPS:

```bash
curl -sf https://your.domain/health
# Expected: {"status":"ok"}
```

Verify auto-renewal:

```bash
ssh digest-vps 'sudo certbot renew --dry-run'
# Expected: Congratulations, all simulated renewals succeeded
```

---

## Phase 10: verify the full deployment

### 10.1 Open the UI

Open `https://your.domain` in a browser. The Preact SPA should load.

### 10.2 Log in

Enter the password set in `CONDENSEIT_AUTH_PASSWORD`.

### 10.3 Check Admin > Sources

Navigate to `/admin/sources`. The sources configured in `config.yaml` should
appear without errors.

### 10.4 Trigger a test digest run

Click **Run digest** in the header or:

```bash
curl -sf -X POST https://your.domain/api/digest/run \
  -H "Authorization: Bearer your-password"
# Expected: {"ok":true,"message":"Digest started.","job":{...}}
# If a run is already in progress: {"ok":false,"message":"...","job":{...}} (HTTP 409)
```

Monitor logs:

```bash
ssh digest-vps 'journalctl -u condenseit-web -f'
```

---

## Ongoing operations reference

```bash
# View logs
ssh digest-vps 'journalctl -u condenseit-web -n 100'

# Restart service
ssh digest-vps 'sudo systemctl restart condenseit-web'

# Deploy code update
./scripts/deploy.sh

# Deploy without rebuilding frontend
./scripts/deploy.sh --skip-build

# Backup database
rsync -avz digest-vps:~/condenseit/data/condenseit.db ./data/condenseit.db.bak
```

---

## Troubleshooting checklist

| Symptom | Action |
|---------|--------|
| SSH connection refused | Check IP in `~/.ssh/config`; verify Hetzner firewall allows port 22 |
| `bootstrap-server.sh` fails: "No nginx config" | Complete Phase 6 first |
| Service not running after bootstrap | `ssh digest-vps 'journalctl -u condenseit-web -n 50'` |
| nginx 502 Bad Gateway | Check `CONDENSEIT_VPS_PORT` matches nginx conf `proxy_pass` port |
| Certbot fails: connection timeout | DNS not propagated; re-run Phase 4 verification |
| Session resets on every deploy | Set `DIGEST_PWA_SESSION_SECRET` in `.env` and redeploy |
| Out of disk space | `ssh digest-vps 'df -h'`; prune old digests in `~/condenseit/data/digests/` |
