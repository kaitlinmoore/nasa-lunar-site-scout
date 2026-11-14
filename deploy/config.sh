# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
# Shared, non-secret deploy settings. Sourced by deploy-api.sh and deploy-web.sh.

# Dedicated gcloud configuration for this project, so deploys never touch another
# account's default configuration. Created once (see deploy/README.md).
export CLOUDSDK_ACTIVE_CONFIG_NAME="${LSS_GCLOUD_CONFIG:-lss}"

GCP_PROJECT="${LSS_GCP_PROJECT:-lunar-site-scout}"
GCP_REGION="${LSS_GCP_REGION:-us-east1}"
API_SERVICE="lss-api"
# Firebase Hosting default site = project id -> https://<project>.web.app
WEB_ORIGINS="https://${GCP_PROJECT}.web.app,https://${GCP_PROJECT}.firebaseapp.com"
