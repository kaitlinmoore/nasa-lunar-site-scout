#!/usr/bin/env bash
# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
# One-time setup: store the demo's Anthropic API key in Secret Manager and let the API's Cloud Run
# service account read it. Run again to add a new key version (e.g. after rotating the key).
# Usage (Git Bash):  bash deploy/setup-nl-secret.sh
# The key is read from a hidden prompt: it is never echoed, never in shell history, never written to disk.
set -euo pipefail
cd "$(dirname "$0")/.."
source deploy/config.sh

gcloud services enable secretmanager.googleapis.com --project "$GCP_PROJECT"

if ! gcloud secrets describe "$NL_SECRET" --project "$GCP_PROJECT" >/dev/null 2>&1; then
  gcloud secrets create "$NL_SECRET" --project "$GCP_PROJECT" --replication-policy automatic
fi

read -rsp "Paste the demo Anthropic API key (input hidden): " KEY
echo
if [ -z "$KEY" ]; then
  echo "No key entered; nothing stored." >&2
  exit 1
fi
printf '%s' "$KEY" | gcloud secrets versions add "$NL_SECRET" --project "$GCP_PROJECT" --data-file=-
unset KEY

# Cloud Run runs as the project's default compute service account unless the service sets another one.
SA=$(gcloud run services describe "$API_SERVICE" --project "$GCP_PROJECT" --region "$GCP_REGION" \
  --format 'value(spec.template.spec.serviceAccountName)' 2>/dev/null || true)
if [ -z "$SA" ]; then
  NUM=$(gcloud projects describe "$GCP_PROJECT" --format 'value(projectNumber)')
  SA="${NUM}-compute@developer.gserviceaccount.com"
fi
gcloud secrets add-iam-policy-binding "$NL_SECRET" --project "$GCP_PROJECT" \
  --member "serviceAccount:${SA}" --role roles/secretmanager.secretAccessor >/dev/null
echo "Stored a new version of $NL_SECRET; $SA can read it. Next: bash deploy/deploy-api.sh"
