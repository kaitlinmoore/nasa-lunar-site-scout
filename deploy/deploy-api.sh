#!/usr/bin/env bash
# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
# Deploy the API to Google Cloud Run (built from ./Dockerfile by Cloud Build).
# Usage (from anywhere, Git Bash):  bash deploy/deploy-api.sh
set -euo pipefail
cd "$(dirname "$0")/.."
source deploy/config.sh

# Stage the precomputed served results into the build context (bundle/ is gitignored).
# Named bundle/served, not .../cache or .../data, because .gcloudignore excludes those names.
rm -rf bundle/served
mkdir -p bundle/served
cp "$SERVED_SRC"/*.json bundle/served/
# Precomputed slope statistics (stream A's cache/terrain/), staged the same way.
rm -rf bundle/terrain
mkdir -p bundle/terrain
cp "$TERRAIN_SRC"/*.json bundle/terrain/
# Cached showcase NL answers (C8), staged the same way; none is fine (the .keep keeps the folder in the
# build context, so the Dockerfile's COPY always has a source).
rm -rf bundle/nl
mkdir -p bundle/nl
touch bundle/nl/.keep
if ls "$NL_CACHE_SRC"/*.json >/dev/null 2>&1; then cp "$NL_CACHE_SRC"/*.json bundle/nl/; fi
# Check everything exactly as the API will load it (contract version, keys, not placeholder).
uv run python -c "from pathlib import Path; from lss.api.served import load_all, load_terrain; from lss.api.nl import load_cache_entries; s = load_all(Path('bundle/served')); t = load_terrain(Path('bundle/terrain')); n = load_cache_entries(Path('bundle/nl')); assert s, 'no served results staged'; assert t, 'no slope statistics staged'; print(f'Staged {len(s)} served results, {len(t)} slope statistics and {len(n)} cached NL answers')"

# The NL key comes from Secret Manager (never a plain env var or a file in the image).
if ! gcloud secrets describe "$NL_SECRET" --project "$GCP_PROJECT" >/dev/null 2>&1; then
  echo "Secret $NL_SECRET not found: run bash deploy/setup-nl-secret.sh once first." >&2
  exit 1
fi

# LSS_DEBUG_CLIENT_IP=1 bash deploy/deploy-api.sh turns on GET /api/_debug/client, for checking the
# client-IP header once (deploy/README.md); deploy again without it afterwards.
gcloud run deploy "$API_SERVICE" \
  --project "$GCP_PROJECT" \
  --region "$GCP_REGION" \
  --source . \
  --allow-unauthenticated \
  --min-instances 0 \
  --max-instances 2 \
  --memory 1Gi \
  --set-env-vars "^@^LSS_CORS_ORIGINS=${WEB_ORIGINS},http://localhost:5173@LSS_DEBUG_CLIENT_IP=${LSS_DEBUG_CLIENT_IP:-0}" \
  --set-secrets "ANTHROPIC_API_KEY=${NL_SECRET}:latest" \
  --quiet

URL=$(gcloud run services describe "$API_SERVICE" --project "$GCP_PROJECT"   --region "$GCP_REGION" --format 'value(status.url)')
echo "API URL: $URL"
curl -fsS "$URL/api/health" && echo
