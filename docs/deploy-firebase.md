# Deploy to Firebase

CondenseIt can be deployed to Google's Firebase / Cloud Run platform. The
frontend SPA is served from Firebase Hosting (global CDN) while the Python
FastAPI backend runs in Cloud Run.

## Architecture

```
Browser → Firebase Hosting (CDN)
                │
                ├── /api/**  → Cloud Run (condenseit-api)
                │               FastAPI + Uvicorn + SQLite
                │               GCS bucket for data persistence
                └── /**      → Preact SPA (frontend/dist)
```

- **Firebase Hosting** serves `frontend/dist` as a static CDN site.
- **Cloud Run** runs the containerized Python backend (see `Dockerfile.cloudrun`).
  - Firebase Hosting rewrites `/api/**` transparently to the Cloud Run service.
  - You can also reach the Cloud Run service directly at its own URL.
- **GCS bucket** is mounted as a filesystem volume inside the Cloud Run container
  via Cloud Storage FUSE, giving the SQLite database persistent storage across
  container restarts and new deployments.

## Prerequisites

### Local machine

| Tool | Purpose | Install |
|------|---------|---------|
| `gcloud` CLI | GCP operations | [cloud.google.com/sdk](https://cloud.google.com/sdk/docs/install) |
| `firebase` CLI | Hosting deploys | `npm install -g firebase-tools` |
| Docker | Build container image | [docs.docker.com](https://docs.docker.com/get-docker/) |
| Node.js 18+ | Build frontend | [nodejs.org](https://nodejs.org) |
| `uv` | Optional, for local dev | `pip install uv` |

### Google Cloud / Firebase project

1. Create a project at [console.firebase.google.com](https://console.firebase.google.com).
2. Enable **Blaze (pay-as-you-go)** billing plan (required for Cloud Run).
3. Note your **Project ID** (shown in the console header).

## One-time setup

### 1. Authenticate

```bash
gcloud auth login
gcloud auth application-default login
firebase login
```

### 2. Set project ID

Add to `.env`:

```
FIREBASE_PROJECT_ID=your-project-id
```

Or export it in your shell:

```bash
export FIREBASE_PROJECT_ID=your-project-id
```

### 3. Configure secrets and keys

Add your secrets to `.env` (see `.env.example` for the full list):

```
# Required for cloud LLM (skip if you only want a UI + local Ollama sync)
OPENROUTER_API_KEY=sk-or-...

# Strongly recommended for any public-facing deployment
CONDENSEIT_AUTH_PASSWORD=your-strong-password

# Auto-generated on first deploy if not set; set it to avoid session resets
DIGEST_PWA_SESSION_SECRET=

```

`DIGEST_PWA_AUTH_PASSWORD` is still accepted for older deployments, but new
installs should use `CONDENSEIT_AUTH_PASSWORD`.

### 4. Copy `.firebaserc`

```bash
cp .firebaserc.example .firebaserc
# Edit .firebaserc and replace YOUR_FIREBASE_PROJECT_ID with your project ID
```

### 5. Deploy

```bash
./scripts/firebase-deploy.sh
```

The script will:

1. Enable the required GCP APIs (Cloud Run, Artifact Registry, Cloud Storage).
2. Create an Artifact Registry repository for the Docker image.
3. Create a GCS bucket for persistent data.
4. Build the frontend SPA.
5. Build and push the Docker image (`Dockerfile.cloudrun`).
6. Deploy the Cloud Run service with the GCS volume mounted at `/app/data`.
7. Deploy the SPA to Firebase Hosting.
8. Print the live URLs.

## Custom domain

1. Open **Firebase Console > Hosting > Add custom domain**.
2. Follow the DNS verification steps.
3. Firebase provisions a TLS certificate automatically.

If you use a custom domain, update `firebase.json` to match the Cloud Run
region for the rewrite (see note in `scripts/firebase-deploy.sh`).

## Deploying updates

Re-run the deploy script after changing code, feeds, or config:

```bash
./scripts/firebase-deploy.sh
```

Skip the build steps if only the Cloud Run environment variables changed:

```bash
./scripts/firebase-deploy.sh --skip-build
```

## Data persistence

The GCS bucket (`<project>-condenseit-data` by default) is mounted inside the
Cloud Run container at `/app/data` via Cloud Storage FUSE (requires the `gen2`
execution environment, which the deploy script enables automatically). The
SQLite database, digests, and config are stored there.

Note: Cloud Storage FUSE has higher latency than a local disk. For very
frequent digest runs this is acceptable; for read-heavy workloads consider
Cloud SQL (requires schema migration).

## Built-in scheduler

The deploy script enables `CONDENSEIT_SCHEDULER_ENABLED=1` by default. The
service will run digests at the UTC times in `config.schedule.times` (default
`07:00` and `18:00`). When the scheduler is enabled, the deploy script keeps
one Cloud Run instance warm so the in-process scheduler can fire on time.

To disable the scheduler:

```
CONDENSEIT_SCHEDULER_ENABLED=0  # in .env before deploying
```

## Viewing logs

```bash
gcloud run services logs read condenseit-api --region us-central1 --limit 100
```

Or stream live:

```bash
gcloud beta run services logs tail condenseit-api --region us-central1
```

## Cost estimate (as of 2026)

Cloud Run and Firebase Hosting have a generous free tier. For a personal
digest running twice a day with occasional web traffic:

| Service | Typical cost |
|---------|-------------|
| Firebase Hosting | Free (10 GB/month transfer included) |
| Cloud Run | Free tier covers most personal use |
| Artifact Registry | ~$0.10/GB/month for the image |
| GCS bucket | Negligible for SQLite (< 50 MB) |

## Tearing down

```bash
# Delete Cloud Run service
gcloud run services delete condenseit-api --region us-central1

# Delete Firebase Hosting deploy
firebase hosting:disable

# Delete GCS bucket (WARNING: deletes all digest data)
gcloud storage rm --recursive gs://YOUR_PROJECT-condenseit-data

# Delete Artifact Registry repo
gcloud artifacts repositories delete condenseit --location us-central1
```

## Troubleshooting

**Firebase Hosting deploy fails with "not logged in"**

```bash
firebase login
```

**Cloud Run deploy fails with "gcloud CLI version" error**

Update gcloud:

```bash
gcloud components update
```

**Volume mount fails on Cloud Run**

Cloud Storage FUSE requires the **2nd generation execution environment** and
the Cloud Run API v2. Make sure you ran `gcloud services enable run.googleapis.com`
and that your `gcloud` CLI is up to date.

**API returns 404 in Firebase Hosting but works on Cloud Run URL directly**

Check that `firebase.json` has the `serviceId` and `region` matching your
Cloud Run service. The region in `firebase.json` must match `CLOUD_RUN_REGION`.

**Session logs out on every redeploy**

Set a fixed `DIGEST_PWA_SESSION_SECRET` in `.env` and redeploy.
