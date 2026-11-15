<!-- SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage". -->
# Deploy

API on **Google Cloud Run**, web on **Firebase Hosting**, both in one Google Cloud project.
Settings live in `deploy/config.sh`.

## Deploy commands (Git Bash, from the repo root)

```bash
bash deploy/deploy-api.sh   # build ./Dockerfile with Cloud Build, deploy to Cloud Run, print URL, hit /api/health
bash deploy/deploy-web.sh   # build web/ against the deployed API URL, deploy to Firebase Hosting
```

Deploy the API first: the web build reads the API URL from Cloud Run.

## Current deployment

| What | URL |
|---|---|
| Web (Firebase Hosting, site `penumbra-luna`) | https://penumbra-luna.web.app |
| API (Cloud Run `lss-api`, us-east1, project `lunar-site-scout`) | https://lss-api-vdrbt264rq-ue.a.run.app |

## Precomputed results in the API image

The API serves precomputed results only (plan 4.6; C1 serves one scenario). They live in the shared
data folder (`LSS_DATA_DIR/cache/served/*.json`, written by `scripts/precompute_c1.py`), outside the
repo. `deploy-api.sh` copies them into `bundle/served/` (gitignored), checks them with the same loader
the API uses (contract version, scenario keys, not placeholder), and the `Dockerfile` copies them to
`/data/cache/served`. Rerun the precompute after any contract version bump, then redeploy.

## How the scripts stay off other accounts

Every gcloud call runs with `CLOUDSDK_ACTIVE_CONFIG_NAME=lss`. That is a dedicated gcloud
configuration holding this project's account and project, so the machine's default gcloud
configuration is never used or changed. Override with `LSS_GCLOUD_CONFIG`,
`LSS_GCP_PROJECT` or `LSS_GCP_REGION` if needed.

## One-time setup (already done in C0; repeat only on a new machine)

```bash
gcloud config configurations create lss --no-activate
gcloud auth login --configuration=lss          # project owner's Google account
gcloud config set project lunar-site-scout --configuration=lss
npx --yes firebase-tools@15 login               # same Google account
```

The project needs billing linked and these APIs enabled: Cloud Run, Cloud Build,
Artifact Registry. Firebase must be added to the project (in C0 this needed the Firebase
console, because the CLI returned 403 until the account accepted the Firebase terms).

Firebase no longer auto-creates a default Hosting site (since 2026-10-15), so create it
explicitly. Its ID is `WEB_SITE` in `deploy/config.sh`; the web URL and the API CORS
origins derive from it:

```bash
npx --yes firebase-tools@15 hosting:sites:create penumbra-luna --project lunar-site-scout
```

## Secrets and the Cesium token

- `.env` is never uploaded: `.gcloudignore` and `.dockerignore` exclude it.
- `CESIUM_ION_TOKEN` is read from `.env` at **web build time** and ships in the bundle.
  It is public by design and restricted in Cesium ion to the Moon Terrain asset and the
  deployed web domains.
- The API's CORS allow-list is set at deploy time from the Firebase Hosting domains
  (`LSS_CORS_ORIGINS`).
