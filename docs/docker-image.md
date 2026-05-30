# Pre-built Docker image

CondenseIt publishes a **web UI only** image on each GitHub release. The
container serves the digest reader and admin panel on port **8899**. Digest
runs and Ollama stay on the host (same as the local Docker setup in
[deploy-local.md](deploy-local.md)).

## Quick start (pull image)

No Node.js or Python build is required on the host for the UI.

```bash
git clone https://github.com/wildlifechorus/condenseit
cd condenseit
cp config.example.yaml config.yaml
cp .env.example .env
# Edit config.yaml and .env as needed.

docker compose pull
docker compose up -d
```

Open [http://localhost:8899](http://localhost:8899).

Run a digest on the host (uses Metal GPU when Ollama is local):

```bash
./scripts/run-with-ollama.sh
# or: condenseit run   (requires a native install for the CLI)
```

Stop the container:

```bash
docker compose down
```

## Image registries

Both registries receive the same tags on each release (`2.7.5`, `2.7`,
`latest` for stable releases):

| Registry | Image |
|----------|-------|
| GitHub Container Registry | `ghcr.io/wildlifechorus/condenseit` |
| Docker Hub | `docker.io/wildlifechorus/condenseit` |

Pull a specific version:

```bash
docker pull ghcr.io/wildlifechorus/condenseit:2.7.5
docker pull docker.io/wildlifechorus/condenseit:2.7.5
```

## Compose environment variables

[`docker-compose.yml`](../docker-compose.yml) defaults to GHCR `latest`:

```yaml
image: ${CONDENSEIT_IMAGE:-ghcr.io/wildlifechorus/condenseit:${CONDENSEIT_IMAGE_TAG:-latest}}
```

Examples:

```bash
# Pin a version on GHCR (default registry)
export CONDENSEIT_IMAGE_TAG=2.7.5
docker compose pull && docker compose up -d

# Use Docker Hub instead
export CONDENSEIT_IMAGE=docker.io/wildlifechorus/condenseit:latest
docker compose pull && docker compose up -d
```

When both `image` and `build` are set, `docker compose up --build` still
builds locally and tags the result with the configured image name (useful for
contributors).

## What the image includes

- Python backend and built Preact frontend (multi-stage
  [`Dockerfile`](../Dockerfile))
- System deps: `ffmpeg`, `libxml2`, `libxslt1.1`

You still mount from the host:

- `config.yaml`, feeds, LLM provider, schedule
- `./data/`, SQLite database and rendered digests

## Maintainer setup (one-time)

Before the first publish, complete these steps in the GitHub repo and
registries.

### 1. Docker Hub

1. Create the repository `wildlifechorus/condenseit` on Docker Hub (if it does
   not exist).
2. Create a Docker Hub **access token** (Account Settings → Security).
3. Add GitHub repository secrets:
   - `DOCKERHUB_USERNAME`, your Docker Hub username
   - `DOCKERHUB_TOKEN`, the access token (not your account password)

### 2. GitHub Container Registry

GHCR login uses the workflow `GITHUB_TOKEN` (`packages: write` permission).
No extra secret is required.

After the **first successful workflow run**:

1. Open the repo on GitHub → **Packages**.
2. Select the `condenseit` container package.
3. **Package settings** → change visibility to **Public** so anonymous
   `docker pull` works.

### 3. Publish workflow

Images are built by
[`.github/workflows/docker-publish.yml`](../.github/workflows/docker-publish.yml):

- **Automatic:** runs when a GitHub **release is published** (tag `vX.Y.Z`).
- **Manual backfill:** Actions → *Publish Docker image* → *Run workflow* with
  tag `vX.Y.Z` and optional `push_latest`.

Platforms: `linux/amd64`, `linux/arm64`.

Tags per stable release: `X.Y.Z`, `X.Y`, and `latest`. Prereleases get version
tags only (no `latest`).
