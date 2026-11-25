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

The API serves precomputed results only. They live in the shared
data folder (`LSS_DATA_DIR/cache/served/*.json`, written by `scripts/precompute_c1.py` and `scripts/precompute_c3.py`), outside the
repo. `deploy-api.sh` copies them into `bundle/served/` (gitignored), checks them with the same loader
the API uses (contract version, scenario keys, not placeholder), and the `Dockerfile` copies them to
`/data/cache/served`. A file made with an older contract version is still served if that version is in
`COMPATIBLE_VERSIONS` (`lss/api/served.py`, kept by the contract owner); otherwise rerun the precompute
after the contract bump, then redeploy.

## Static JSON fallback

`deploy-web.sh` also publishes the precomputed results as static files on the web host, at
`https://penumbra-luna.web.app/static-api/`, so the demo still works when the API is down:
`index.json` (a `StaticIndex`: every served scenario and the paths of its files), `sites.json`,
`datasets.json`, `metrics/<scenario_key>.json`, `series/<scenario_key>.json`, and
`horizon/<horizon_key>.json` where a served file has a horizon. They are written by
`uv run python -m lss.api.static_export` from `bundle/served/`, the files `deploy-api.sh` staged into the
API image, with the API's own loader, so they are the API's bodies. The deploy stops if any file is not at
the current contract version, or if the deployed API reports another version or returns different
metrics. So **deploy the API first**. `/static-api/**` is sent with `Cache-Control: no-cache`.
Firebase's catch-all rewrite answers a missing file with `index.html` (status 200), so clients must check
the content type or parse the JSON.

## Natural-language questions (`POST /api/nl`)

**The API key** is the demo's own Anthropic key, kept in **Secret Manager** (secret `lss-anthropic-demo-key`,
`NL_SECRET` in `config.sh`) and given to Cloud Run with `--set-secrets ANTHROPIC_API_KEY=…:latest`. It is
never a plain env var, never in the image, never in `.env` on the server. One-time setup, and again to rotate
the key (the script reads it from a hidden prompt and grants the service account read access):

```bash
bash deploy/setup-nl-secret.sh
bash deploy/deploy-api.sh      # stops if the secret doesn't exist
```

The eval harness uses a separate key (`.env`, local only), so demo traffic can't use up the eval budget.

**Limits are soft.** The rate limit (5 questions a minute and 30 a UTC day per client IP) and the spend cap
($2 a UTC day, estimated from token counts at list prices) are counted **in memory, per instance**:

- they **do not survive restarts**: Cloud Run stops idle instances (`--min-instances 0`), and a new instance
  starts from zero;
- they **are not shared across instances**: with `--max-instances 2`, one client can get up to twice the
  limits while two instances run.

So they bound ordinary use, not a determined client. **The hard limit is the monthly spend limit on the demo
key in the Anthropic Console** (set by the project owner). Values can be changed per deployment with
`LSS_NL_RATE_PER_MINUTE`, `LSS_NL_RATE_PER_DAY`, `LSS_NL_DAILY_SPEND_USD`. Cached showcase answers
(`/data/cache/nl/*.json`) cost nothing and are not limited.

**Client IP.** The rate limit keys on the **last** `X-Forwarded-For` entry, on the assumption that Cloud
Run's front end appends the real client address to whatever the client sent. **Verified on the deployed API,
2026-11-16:** `used_for_rate_limit` was the same with and without a made-up header, and the made-up
`203.0.113.9` came first in `x_forwarded_for` without being used. To repeat the check (e.g. after putting a
load balancer or custom domain in front):

```bash
LSS_DEBUG_CLIENT_IP=1 bash deploy/deploy-api.sh       # turns on GET /api/_debug/client
URL=https://lss-api-vdrbt264rq-ue.a.run.app
curl -s "$URL/api/_debug/client"; echo
curl -s -H "X-Forwarded-For: 203.0.113.9" "$URL/api/_debug/client"; echo
bash deploy/deploy-api.sh                             # deploy again without it
```

Expected: both calls show the same `used_for_rate_limit` (your own address), and in the second the made-up
`203.0.113.9` appears first in `x_forwarded_for`, not as the value used. If not, `client_address` in
`lss/api/nl.py` must change before the limits mean anything.

**TLS.** The anthropic SDK's HTTP client (httpx2) verifies against the OS CA store on Linux; the `Dockerfile`
fails the build if the image has no CA certificates (`lss.api.nl.ca_certificates_available`).

## Terrain images for the 2D site view (contract 0.13.0)

`scripts/terrain_views.py` writes them to `LSS_DATA_DIR/cache/terrain_view/<site id>/<view>/` (`view.json`, `hillshade.png`,
`slope.png`; views `2km` and `20km`; about 5.6 MB for the 8 PGDA sites). `deploy-api.sh` stages the folder into
`bundle/terrain_view/` and checks it with the API's loader (8-bit greyscale PNGs of the stated size, no
colour-profile chunks, centre within one pixel of the site's served point); the `Dockerfile` copies it to
`/data/cache/terrain_view`. `deploy-web.sh` publishes the same files in the static copy
(`terrain_view/…`, `terrain_views.json`) and checks the list against the deployed API.

## IAU feature names for the globe labels (contract 0.14.0)

`scripts/fetch_iau_names.py` writes `LSS_DATA_DIR/cache/features/iau_names.json` (9,087 IAU-adopted
names, 465 KB). `deploy-api.sh` stages it into `bundle/features/` and checks it with the API's loader; the
`Dockerfile` copies it to `/data/cache/features`. `GET /api/features/labels` filters it (type, minimum diameter,
satellite features, box, limit; gzip over 1 KB). `deploy-web.sh` publishes every name as `feature_labels.json`
in the static copy (about 200 KB gzipped) and checks it against the deployed API.

## Cached showcase answers

The project owner chooses the showcase questions.
Each becomes one file in `LSS_DATA_DIR/cache/nl/`, then goes live with the usual two deploys:

```bash
# a question from a saved eval run: replays its saved model output, no LLM call, no cost
uv run python -m lss.api.nl_cache add-from-run tests/nl/results/<run>.json <item id>
# a new question: one live call through the demo's pipeline (with the project owner's okay)
uv run python -m lss.api.nl_cache add "How steep is the terrain?" --site pgda-site01 --live
uv run python -m lss.api.nl_cache list          # what is cached; `remove <name>` drops one
bash deploy/deploy-api.sh                       # stages cache/nl into the image (checked as the API loads it)
bash deploy/deploy-web.sh                       # publishes them in the static copy, checked against the API
```

A cached answer is returned for exactly its question (case, spacing and final punctuation ignored), selected
site and selected scenario. It costs nothing, isn't rate limited, and still works after the daily cap or when
the model can't be reached. It is fixed when recorded (default windows keep that date), and it is refused at
deploy if made with an incompatible contract version, so record it again after such a bump.

## How the scripts stay off other accounts

Every gcloud call runs with `CLOUDSDK_ACTIVE_CONFIG_NAME=lss`. That is a dedicated gcloud
configuration holding this project's account and project, so the machine's default gcloud
configuration is never used or changed. Override with `LSS_GCLOUD_CONFIG`,
`LSS_GCP_PROJECT` or `LSS_GCP_REGION` if needed.

## One-time setup (already done; repeat only on a new machine)

```bash
gcloud config configurations create lss --no-activate
gcloud auth login --configuration=lss          # project owner's Google account
gcloud config set project lunar-site-scout --configuration=lss
npx --yes firebase-tools@15 login               # same Google account
```

The project needs billing linked and these APIs enabled: Cloud Run, Cloud Build,
Artifact Registry. Firebase must be added to the project (the first time, this needed the Firebase
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
