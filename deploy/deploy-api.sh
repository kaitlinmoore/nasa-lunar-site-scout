#!/usr/bin/env bash
# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
# Deploy the API to Google Cloud Run (built from ./Dockerfile by Cloud Build).
# Usage (from anywhere, Git Bash):  bash deploy/deploy-api.sh
set -euo pipefail
cd "$(dirname "$0")/.."
source deploy/config.sh

gcloud run deploy "$API_SERVICE"   --project "$GCP_PROJECT"   --region "$GCP_REGION"   --source .   --allow-unauthenticated   --min-instances 0   --max-instances 2   --memory 1Gi   --set-env-vars "^@^LSS_CORS_ORIGINS=${WEB_ORIGINS},http://localhost:5173"   --quiet

URL=$(gcloud run services describe "$API_SERVICE" --project "$GCP_PROJECT"   --region "$GCP_REGION" --format 'value(status.url)')
echo "API URL: $URL"
curl -fsS "$URL/api/health" && echo
