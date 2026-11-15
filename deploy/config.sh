# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
# Shared, non-secret deploy settings. Sourced by deploy-api.sh and deploy-web.sh.

# Dedicated gcloud configuration for this project, so deploys never touch another
# account's default configuration. Created once (see deploy/README.md).
export CLOUDSDK_ACTIVE_CONFIG_NAME="${LSS_GCLOUD_CONFIG:-lss}"

GCP_PROJECT="${LSS_GCP_PROJECT:-lunar-site-scout}"
GCP_REGION="${LSS_GCP_REGION:-us-east1}"
API_SERVICE="lss-api"
# Firebase Hosting site ID (created explicitly with `firebase hosting:sites:create`;
# Firebase stopped auto-creating a default site on 2026-10-15). The web URL and the
# API's CORS origins derive from this, not from the project ID.
WEB_SITE="${LSS_WEB_SITE:-penumbra-luna}"
WEB_URL="https://${WEB_SITE}.web.app"
WEB_ORIGINS="${WEB_URL},https://${WEB_SITE}.firebaseapp.com"

# Precomputed served results (plan 4.6) live in the shared data folder, outside the repo.
# deploy-api.sh stages them into bundle/served/ (gitignored) so Cloud Build can copy them
# into the image at /data/cache/served (LSS_DATA_DIR=/data in the container).
LSS_DATA_DIR_POSIX="$(cygpath -u "${LSS_DATA_DIR:-C:\\dev\\GitHub\\lss-data}" 2>/dev/null || echo "${LSS_DATA_DIR:-/c/dev/GitHub/lss-data}")"
SERVED_SRC="${LSS_DATA_DIR_POSIX}/cache/served"
