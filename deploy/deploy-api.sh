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
# Check them exactly as the API will load them (contract version, keys, not placeholder).
uv run python -c "from pathlib import Path; from lss.api.served import load_all; s = load_all(Path('bundle/served')); assert s, 'no served results staged'; print('Staged served results:', ', '.join(sorted(s)))"

gcloud run deploy "$API_SERVICE"   --project "$GCP_PROJECT"   --region "$GCP_REGION"   --source .   --allow-unauthenticated   --min-instances 0   --max-instances 2   --memory 1Gi   --set-env-vars "^@^LSS_CORS_ORIGINS=${WEB_ORIGINS},http://localhost:5173"   --quiet

URL=$(gcloud run services describe "$API_SERVICE" --project "$GCP_PROJECT"   --region "$GCP_REGION" --format 'value(status.url)')
echo "API URL: $URL"
curl -fsS "$URL/api/health" && echo
