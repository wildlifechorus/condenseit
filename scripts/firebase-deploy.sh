#!/usr/bin/env bash
# =============================================================
# firebase-deploy.sh - Deploy CondenseIt to Firebase Hosting + Cloud Run
#
# Architecture:
#   Firebase Hosting  → serves the Preact SPA (frontend/dist) via CDN
#   Cloud Run         → runs the FastAPI backend (condenseit-api)
#   Hosting rewrites  → /api/** proxied to Cloud Run
#   GCS bucket        → persists SQLite DB and digest data across restarts
#
# Prerequisites (local machine):
#   - gcloud CLI authenticated:  gcloud auth login
#   - Application Default Creds: gcloud auth application-default login
#   - Firebase CLI:               npm install -g firebase-tools && firebase login
#   - Docker (to build the image)
#   - Node.js 18+ (to build the frontend)
#
# Required env vars (set in .env or shell):
#   FIREBASE_PROJECT_ID   - Your GCP / Firebase project ID
#
# Optional env vars:
#   CLOUD_RUN_REGION           - Region for Cloud Run (default: us-central1)
#   CLOUD_RUN_SERVICE          - Service name (default: condenseit-api)
#   GCS_DATA_BUCKET            - Bucket for data (default: <project>-condenseit-data)
#   OPENROUTER_API_KEY         - OpenRouter key (if using cloud LLM)
#   CONDENSEIT_AUTH_PASSWORD   - Password for the web UI (recommended)
#   DIGEST_PWA_SESSION_SECRET  - Fixed session secret (auto-generated if absent)
#   CONDENSEIT_SCHEDULER_ENABLED - 1 to enable built-in scheduler (default: 1)
#   CLOUD_RUN_MIN_INSTANCES    - Minimum warm instances (default: 1 if
#                                scheduler is enabled, otherwise 0)
#
# Usage:
#   ./scripts/firebase-deploy.sh              # full build + deploy
#   ./scripts/firebase-deploy.sh --skip-build # re-deploy without rebuilding
# =============================================================

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [[ -f "$ROOT/.env" ]]; then
  set -o allexport
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +o allexport
fi

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info() { echo -e "${GREEN}[firebase-deploy]${NC} $*"; }
warn() { echo -e "${YELLOW}[firebase-deploy]${NC} $*"; }
die()  { echo -e "${RED}[firebase-deploy] ERROR:${NC} $*" >&2; exit 1; }

SKIP_BUILD=false
for arg in "$@"; do
  case "$arg" in
    --skip-build) SKIP_BUILD=true ;;
    --help|-h)
      sed -n '3,30p' "$0" | sed 's/^# //'
      exit 0
      ;;
    *) die "Unknown option: $arg" ;;
  esac
done

# ---------------------------------------------------------------------------
# Validate prerequisites
# ---------------------------------------------------------------------------
command -v gcloud &>/dev/null \
  || die "gcloud not found. See https://cloud.google.com/sdk/docs/install"
command -v firebase &>/dev/null \
  || die "firebase CLI not found. Install: npm install -g firebase-tools"
command -v docker &>/dev/null \
  || die "docker not found. See https://docs.docker.com/get-docker/"
command -v node &>/dev/null \
  || die "node not found. Required for the frontend build."

# ---------------------------------------------------------------------------
# Resolve config
# ---------------------------------------------------------------------------
PROJECT_ID="${FIREBASE_PROJECT_ID:-}"
[[ -n "$PROJECT_ID" ]] \
  || die "FIREBASE_PROJECT_ID is not set. Add it to .env or environment."

REGION="${CLOUD_RUN_REGION:-us-central1}"
SERVICE_NAME="${CLOUD_RUN_SERVICE:-condenseit-api}"
GCS_BUCKET="${GCS_DATA_BUCKET:-${PROJECT_ID}-condenseit-data}"
ARTIFACT_REPO="${CLOUD_RUN_ARTIFACT_REPO:-condenseit}"
IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/$ARTIFACT_REPO/$SERVICE_NAME"

info "Project:      $PROJECT_ID"
info "Region:       $REGION"
info "CR service:   $SERVICE_NAME"
info "Image:        $IMAGE"
info "Data bucket:  gs://$GCS_BUCKET"

gcloud config set project "$PROJECT_ID" --quiet

# ---------------------------------------------------------------------------
# Enable required GCP APIs
# ---------------------------------------------------------------------------
info "Enabling GCP APIs..."
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  storage.googleapis.com \
  --quiet

# ---------------------------------------------------------------------------
# Ensure Artifact Registry repository exists
# ---------------------------------------------------------------------------
if ! gcloud artifacts repositories describe "$ARTIFACT_REPO" \
    --location="$REGION" --quiet &>/dev/null 2>&1; then
  info "Creating Artifact Registry repository '$ARTIFACT_REPO' in $REGION..."
  gcloud artifacts repositories create "$ARTIFACT_REPO" \
    --repository-format=docker \
    --location="$REGION" \
    --quiet
fi

# ---------------------------------------------------------------------------
# Ensure GCS data bucket exists
# ---------------------------------------------------------------------------
if ! gcloud storage buckets describe "gs://$GCS_BUCKET" --quiet &>/dev/null 2>&1; then
  info "Creating GCS bucket gs://$GCS_BUCKET..."
  gcloud storage buckets create "gs://$GCS_BUCKET" \
    --location="$REGION" \
    --uniform-bucket-level-access \
    --quiet
fi

# ---------------------------------------------------------------------------
# Build frontend
# ---------------------------------------------------------------------------
if [[ "$SKIP_BUILD" == false ]]; then
  info "Building frontend SPA..."
  (cd "$ROOT/frontend" && npm ci --silent && npm run build) \
    || die "Frontend build failed."
fi

[[ -d "$ROOT/frontend/dist" ]] \
  || die "frontend/dist not found. The frontend must be built before deploying."

# ---------------------------------------------------------------------------
# Build and push Docker image for Cloud Run
# ---------------------------------------------------------------------------
if [[ "$SKIP_BUILD" == false ]]; then
  info "Authenticating Docker with Artifact Registry..."
  gcloud auth configure-docker "$REGION-docker.pkg.dev" --quiet

  info "Building Cloud Run image (Dockerfile.cloudrun)..."
  docker build \
    -f "$ROOT/Dockerfile.cloudrun" \
    -t "$IMAGE:latest" \
    "$ROOT" \
    || die "Docker build failed."

  info "Pushing image to Artifact Registry..."
  docker push "$IMAGE:latest" \
    || die "Docker push failed."
fi

# ---------------------------------------------------------------------------
# Prepare environment variables for Cloud Run
# ---------------------------------------------------------------------------
SESSION_SECRET="${DIGEST_PWA_SESSION_SECRET:-}"
if [[ -z "$SESSION_SECRET" ]]; then
  SESSION_SECRET="$(openssl rand -hex 32 2>/dev/null \
    || LC_ALL=C tr -dc 'a-f0-9' </dev/urandom | head -c 64)"
  warn "Generated session secret. Persist it in .env:"
  warn "  DIGEST_PWA_SESSION_SECRET=$SESSION_SECRET"
fi

OR_KEY="${OPENROUTER_API_KEY:-}"
AUTH_PW="${CONDENSEIT_AUTH_PASSWORD:-${DIGEST_PWA_AUTH_PASSWORD:-}}"
SCHEDULER_ENABLED="${CONDENSEIT_SCHEDULER_ENABLED:-1}"
if [[ -n "${CLOUD_RUN_MIN_INSTANCES:-}" ]]; then
  MIN_INSTANCES="$CLOUD_RUN_MIN_INSTANCES"
elif [[ "$SCHEDULER_ENABLED" == "1" ]]; then
  MIN_INSTANCES=1
else
  MIN_INSTANCES=0
fi

ENV_VARS="CONDENSEIT_DATA_DIR=/app/data"
ENV_VARS="${ENV_VARS},CONDENSEIT_SCHEDULER_ENABLED=${SCHEDULER_ENABLED}"
ENV_VARS="${ENV_VARS},DIGEST_PWA_SESSION_SECRET=${SESSION_SECRET}"
ENV_VARS="${ENV_VARS},CONDENSEIT_HTTPS_ONLY=1"
[[ -n "$OR_KEY" ]]    && ENV_VARS="${ENV_VARS},OPENROUTER_API_KEY=${OR_KEY}"
[[ -n "$AUTH_PW" ]]   && ENV_VARS="${ENV_VARS},CONDENSEIT_AUTH_PASSWORD=${AUTH_PW},DIGEST_PWA_AUTH_PASSWORD=${AUTH_PW}"

# ---------------------------------------------------------------------------
# Deploy Cloud Run service with GCS volume for data persistence
# ---------------------------------------------------------------------------
info "Deploying Cloud Run service '$SERVICE_NAME'..."
gcloud run deploy "$SERVICE_NAME" \
  --image "$IMAGE:latest" \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --port 8080 \
  --memory 512Mi \
  --cpu 1 \
  --min-instances "$MIN_INSTANCES" \
  --max-instances 3 \
  --timeout 300 \
  --execution-environment gen2 \
  --set-env-vars "$ENV_VARS" \
  --add-volume "name=condenseit-data,type=cloud-storage,bucket=$GCS_BUCKET" \
  --add-volume-mount "volume=condenseit-data,mount-path=/app/data" \
  --quiet \
  || die "Cloud Run deployment failed. Check gcloud CLI version (need >= 455)."

info "Cloud Run service deployed."

# ---------------------------------------------------------------------------
# Ensure .firebaserc is configured
# ---------------------------------------------------------------------------
if [[ ! -f "$ROOT/.firebaserc" ]]; then
  warn ".firebaserc not found - generating from .firebaserc.example..."
  if [[ -f "$ROOT/.firebaserc.example" ]]; then
    sed "s/YOUR_FIREBASE_PROJECT_ID/$PROJECT_ID/" \
      "$ROOT/.firebaserc.example" > "$ROOT/.firebaserc"
  else
    printf '{"projects":{"default":"%s"}}\n' "$PROJECT_ID" > "$ROOT/.firebaserc"
  fi
  info "Created .firebaserc for project $PROJECT_ID"
fi

# Warn if the region in firebase.json does not match
if [[ "$REGION" != "us-central1" ]]; then
  if grep -q '"region": "us-central1"' "$ROOT/firebase.json" 2>/dev/null; then
    warn "CLOUD_RUN_REGION is '$REGION' but firebase.json still has 'us-central1'."
    warn "Edit firebase.json and set: \"region\": \"$REGION\""
  fi
fi

# ---------------------------------------------------------------------------
# Deploy Firebase Hosting (SPA)
# ---------------------------------------------------------------------------
info "Deploying SPA to Firebase Hosting..."
(cd "$ROOT" && firebase deploy --only hosting --project "$PROJECT_ID") \
  || die "Firebase Hosting deploy failed. Ensure you are logged in: firebase login"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
CR_URL="$(gcloud run services describe "$SERVICE_NAME" --region "$REGION" \
  --format 'value(status.url)' 2>/dev/null || echo 'check GCP Console')"
HOSTING_URL="https://${PROJECT_ID}.web.app"

echo ""
info "Deployment complete."
echo ""
echo "  Hosting (SPA):   $HOSTING_URL"
echo "  API (Cloud Run): $CR_URL"
echo ""
echo "  Quick smoke check:"
echo "    curl $HOSTING_URL/api/health"
echo ""
echo "  View Cloud Run logs:"
echo "    gcloud run services logs read $SERVICE_NAME --region $REGION --limit 50"
echo ""
echo "  Custom domain:"
echo "    Firebase Console > Hosting > Add custom domain"
echo ""
echo "  Re-deploy after code changes:"
echo "    ./scripts/firebase-deploy.sh"
echo ""
echo "  Re-deploy without rebuilding:"
echo "    ./scripts/firebase-deploy.sh --skip-build"
