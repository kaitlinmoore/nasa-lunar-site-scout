#!/usr/bin/env bash
# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
# Build the web app against the deployed API and deploy it to Firebase Hosting.
# Usage (from anywhere, Git Bash):  bash deploy/deploy-web.sh
# CESIUM_ION_TOKEN is read from .env (LSS_ENV_FILE or repo root) at build time.
set -euo pipefail
cd "$(dirname "$0")/.."
source deploy/config.sh

API_URL=$(gcloud run services describe "$API_SERVICE" --project "$GCP_PROJECT" \
  --region "$GCP_REGION" --format 'value(status.url)')
echo "Building web against API: $API_URL"

(cd web && npm ci && VITE_API_BASE="$API_URL" npm run build)

# Firebase config is generated from deploy/firebase.json with the site ID from config.sh,
# so the site ID lives in one place.
GEN=deploy/firebase.generated.json
node -e '
const fs = require("fs");
const cfg = JSON.parse(fs.readFileSync("deploy/firebase.json", "utf-8"));
cfg.hosting.site = process.argv[1];
fs.writeFileSync(process.argv[2], JSON.stringify(cfg, null, 2) + "\n");
' "$WEB_SITE" "$GEN"

npx --yes firebase-tools@15 deploy --only hosting --project "$GCP_PROJECT" \
  --config "$GEN" --non-interactive

echo "Web URL: $WEB_URL"
