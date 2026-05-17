# Agent guide: deploy CondenseIt to Firebase + Cloud Run

This document is written for an AI coding agent executing deployment steps
autonomously. Follow every step in order. After each command, verify the
expected output before continuing. Never skip a verification step.

---

## Context

CondenseIt is a Python/FastAPI app with a Preact SPA frontend and an SQLite
database. The Firebase deployment uses:

- **Firebase Hosting** for the SPA (CDN-hosted static files).
- **Cloud Run** for the Python backend (containerized, `Dockerfile.cloudrun`).
- **GCS bucket** for persistent SQLite storage (mounted via Cloud Storage FUSE).
- **Firebase Hosting rewrites** to proxy `/api/**` to Cloud Run.

---

## Phase 0: verify prerequisites on the local machine

Run each check. If a tool is missing, install it before continuing.

```bash
# gcloud CLI
gcloud version
# Expected: Google Cloud SDK (any recent version; 455+ required for Cloud Run
# volume mounts - gcloud will warn if an update is needed during deploy)

# firebase CLI
firebase --version
# Expected: any recent 13.x.x or newer

# Docker
docker --version
# Expected: Docker Desktop or Engine (24.x or newer recommended)

# Node.js
node --version
# Expected: v18.x.x or newer

# npm
npm --version
# Expected: 10.x.x or newer
```

---

## Phase 1: authenticate

```bash
gcloud auth login
# Opens browser. Log in with the Google account that owns the Firebase project.

gcloud auth application-default login
# Opens browser again. Required for gcloud SDK calls inside the deploy script.

firebase login
# Opens browser. Log in with the same Google account.
```

Verify:

```bash
gcloud auth list
# The account used above should be marked as ACTIVE.

firebase projects:list
# Should show your Firebase project in the list.
```

---

## Phase 2: configure the repository

All commands run from the repository root unless otherwise stated.

### 2.1 Set required environment variables

Read `.env.example` to understand all available variables. Then create or
update `.env` with at minimum:

```
FIREBASE_PROJECT_ID=your-actual-project-id
OPENROUTER_API_KEY=sk-or-...        # required for cloud LLM
CONDENSEIT_AUTH_PASSWORD=strong-password-here
```

To generate a session secret:

```bash
openssl rand -hex 32
```

Add the output as `DIGEST_PWA_SESSION_SECRET=<output>` in `.env`.

### 2.2 Create `.firebaserc`

```bash
cp .firebaserc.example .firebaserc
```

Edit `.firebaserc` and replace `YOUR_FIREBASE_PROJECT_ID` with the actual
project ID. Verify:

```bash
cat .firebaserc
# Should show: {"projects":{"default":"your-actual-project-id"}}
```

### 2.3 Verify `firebase.json`

```bash
cat firebase.json
```

Expected structure:

- `hosting.public` is `frontend/dist`.
- `hosting.rewrites` contains a rule for `/api/**` pointing to Cloud Run
  service `condenseit-api` in region `us-central1` (or the value of
  `CLOUD_RUN_REGION`).
- `hosting.rewrites` contains a catch-all pointing to `/index.html`.

If `CLOUD_RUN_REGION` is not `us-central1`, edit `firebase.json` and update
the `"region"` field inside the `/api/**` rewrite to match.

---

## Phase 3: run the deploy script

```bash
./scripts/firebase-deploy.sh
```

The script will print `[firebase-deploy] ...` prefixed status lines. Follow
each one:

1. **Enabling GCP APIs** - waits for Cloud Run, Artifact Registry, and Cloud
   Storage APIs to become active. This can take up to 2 minutes on a new
   project.

2. **Creating Artifact Registry repository** - only runs on first deploy.

3. **Creating GCS bucket** - only runs on first deploy.

4. **Building frontend SPA** - runs `npm ci && npm run build` inside
   `frontend/`. Expect `dist/index.html` and `dist/assets/` to be created.

5. **Authenticating Docker with Artifact Registry** - runs
   `gcloud auth configure-docker`.

6. **Building Cloud Run image** - runs `docker build -f Dockerfile.cloudrun`.
   This takes 2-5 minutes on first build.

7. **Pushing image to Artifact Registry** - uploads the built image.

8. **Deploying Cloud Run service** - deploys `condenseit-api`. The
   `--add-volume` flags mount the GCS bucket at `/app/data`. Requires
   gcloud >= 455.

9. **Deploying SPA to Firebase Hosting** - runs `firebase deploy --only hosting`.

10. **Summary** - prints the Hosting URL and the Cloud Run URL.

Expected final output:

```
[firebase-deploy] Deployment complete.

  Hosting (SPA):   https://YOUR_PROJECT.web.app
  API (Cloud Run): https://condenseit-api-HASH-uc.a.run.app
```

---

## Phase 4: verify the deployment

### 4.1 Health check

The `/health` endpoint is on the Cloud Run service, not on the Firebase
Hosting URL (Hosting only proxies `/api/**`). Use the Cloud Run URL printed
by the deploy script:

```bash
CLOUD_RUN_URL="https://condenseit-api-HASH-uc.a.run.app"  # from deploy output

curl -sf "$CLOUD_RUN_URL/health"
# Expected: {"status":"ok"}
```

### 4.2 Auth check

If `CONDENSEIT_AUTH_PASSWORD` is set:

```bash
curl -sf -X POST "$HOSTING_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"password":"your-password"}'
# Expected: HTTP 200 with a Set-Cookie header (session cookie)
```

### 4.3 Open the UI

Open `$HOSTING_URL` in a browser. The Preact SPA should load. Log in if auth
is enabled, then verify:

- `/admin` redirects to Admin > Sources and the sources list loads without errors.
- The Budget page shows no API errors (may show $0.00 if no runs yet).

### 4.4 Trigger a digest run

From the web UI header, click **Run digest**.
Alternatively:

```bash
curl -sf -X POST "$HOSTING_URL/api/digest/run" \
  -H "Authorization: Bearer your-password"
# Expected: {"ok":true,"message":"Digest started.","job":{...}}
# If a run is already in progress: {"ok":false,"message":"...","job":{...}} (HTTP 409)
```

Check logs:

```bash
gcloud run services logs read condenseit-api --region us-central1 --limit 50
```

---

## Phase 5: configure the built-in scheduler (optional)

The scheduler is enabled by default (`CONDENSEIT_SCHEDULER_ENABLED=1`). It
runs digests at the times configured in **Admin > Schedule** (stored in the
database, takes effect immediately without a redeploy). The default times are
`07:00` and `18:00` UTC.

To change run times, open the web UI, go to **Admin > Schedule**, and update
them there. Alternatively, set `config.schedule.times` in `config.yaml` as the
initial default before the first run.

To disable:

```
CONDENSEIT_SCHEDULER_ENABLED=0
```

in `.env`, then run `./scripts/firebase-deploy.sh --skip-build`.

---

## Phase 6: custom domain (optional)

1. Open Firebase Console > Hosting > Add custom domain.
2. Enter your domain, verify DNS ownership, add the A/AAAA records.
3. Firebase provisions a TLS certificate automatically within minutes.

---

## Troubleshooting checklist

| Symptom | Check |
|---------|-------|
| `firebase deploy` fails with "not logged in" | Run `firebase login` |
| `gcloud run deploy` fails mentioning volume mounts | Update gcloud: `gcloud components update` |
| `/api/**` returns 404 on Hosting URL but works on Cloud Run URL | Verify `firebase.json` serviceId and region match your Cloud Run deployment |
| Session resets on every redeploy | Set `DIGEST_PWA_SESSION_SECRET` in `.env` |
| Container crashes on startup | Run `gcloud run services logs read condenseit-api --region us-central1` |
| GCS FUSE mount fails | Ensure `--execution-environment gen2` is set and gcloud >= 455 |
| Billing not enabled | Go to Firebase Console > Upgrade to Blaze plan |
