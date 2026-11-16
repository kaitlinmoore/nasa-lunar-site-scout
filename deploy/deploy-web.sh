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

# Static JSON fallback (plan 4.7): the precomputed results the API image was built with (bundle/served,
# staged by deploy-api.sh), as static files at /static-api/. Fails unless every file is at the current
# contract version and the deployed API reports that version and returns the same metrics.
if ! ls bundle/served/*.json >/dev/null 2>&1; then
  echo "No bundle/served/: run bash deploy/deploy-api.sh first (it stages the served results)." >&2
  exit 1
fi
uv run python -m lss.api.static_export web/dist/static-api --served-dir bundle/served \
  --terrain-dir bundle/terrain --check-api "$API_URL"

# Firebase config is generated (gitignored) from deploy/firebase.json with the site ID from config.sh,
# so the site ID lives in one place.
GEN=firebase.generated.json  # at repo root: Firebase requires "public" inside the config's directory
node -e '
const fs = require("fs");
const cfg = JSON.parse(fs.readFileSync("deploy/firebase.json", "utf-8"));
cfg.hosting.site = process.argv[1];
fs.writeFileSync(process.argv[2], JSON.stringify(cfg, null, 2) + "\n");
' "$WEB_SITE" "$GEN"

npx --yes firebase-tools@15 deploy --only hosting --project "$GCP_PROJECT" \
  --config "$GEN" --non-interactive

echo "Web URL: $WEB_URL"
