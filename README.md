<!-- SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage". -->
# Penumbra Luna

*Lunar Landing Site Navigator*

**Live app: https://penumbra-luna.web.app** (no login).

Terrain-aware lunar south pole landing site planner. Compare sites and dates for sunlight and direct-to-Earth communications using LOLA topography and JPL ephemerides.

> Built for the 2026 NASA Space Apps Challenge (Lunar Landing Site Navigator). Not affiliated with or endorsed by NASA.

## What it does

The decision it supports: **where to land and when.** It is built for mission planners (a rover + lander mission, where the lander needs a direct line of sight to Earth) and for the public, in the same tool: sophisticated features are easy to reach when needed, without overwhelming casual users.

- **Globe:** a 3D Moon (Cesium Moon, display only) with the curated sites as markers. Click one for its card, then open its site screen.
- **Site screen:** pick a time window and unit height (the picker offers only that site's precomputed scenarios), then see:
  - **power:** illumination, mean visible solar disc, sunlit duration, shadow periods, longest shadow, Sun elevation and azimuth, time to sunset;
  - **communications (direct to Earth):** Earth visibility, Earth full disc, longest Earth gap, Earth elevation, Earth clearance, Sun + Earth overlap, time to Earthset;
  - **sky view:** the terrain horizon with the Sun and Earth tracks over the window, and a timeline of sunrises, sunsets, Earthrises and Earthsets.
- **Save and compare:** save scenarios and compare them side by side, several sites and several dates. Saved items stay in your browser, with export and import.
- **Ask in plain English:** a question box (it uses Claude) turns a question into a query, shows how it understood it, and answers from the same results. When a question can't be answered with the available data, it says so and why.

### Sites

The site list is [`lss/registry/sites.yaml`](lss/registry/sites.yaml) (served at `/api/sites`). It currently has **8 south-pole sites**: Connecting Ridge, Shackleton Rim, Peak near Shackleton, de Gerlache Rim, Nobile Rim, Leibnitz Beta Plateau, Malapert Massif and de Gerlache–Kocher Massif. Their points come from Barker et al. (2021) and Mazarico et al. (2011); see the [glossary](docs/glossary.md#curated-sites) for the table and [methodology §1.4](docs/methodology.md#14-curated-sites-c3) for the rule.

**Results are precomputed.** For each site: unit heights 1, 2, 5 and 10 m, over two windows: 15 May – 14 Jun 2028 (results every hour) and all of 2028 (every 6 hours). Any other request is refused with the list of what is served.

## How it works

Full detail, with every convention, test and number: [`docs/methodology.md`](docs/methodology.md).

- **Terrain:** NASA GSFC PGDA elevation maps from LOLA: the 5 m site maps for the near field, then 80 m and 240 m maps out to 400 km. All are in the same Moon frame (MOON_ME, DE421) as the ephemeris, so no frame alignment is needed.
- **Sun and Earth:** JPL's DE421 ephemeris and lunar orientation through NAIF SPICE, with light time and stellar aberration. Libration is included in every Earth position.
- **Horizon:** for each 0.1° of azimuth, the highest terrain along a ray over the curved Moon, out to 400 km. Accepted horizon error: at most about 0.01°.
- **Visibility:** the Sun is a limb-darkened disc (Allen 1973, 550 nm) and the Earth a disc, each cut by the real horizon profile. "Sunlit" means any part of the Sun's disc is visible, as in Barker et al. (2021) and PGDA product 69. Rises and sets are found on a 60 s grid and refined to 0.5 s.

## Validation

From [methodology §6](docs/methodology.md#6-validation-results-step-47). Every tolerance was fixed before its run; a miss is reported as a miss.

| Check | Tolerance | Result | Verdict |
|---|---|---|---|
| Sun and Earth az/el vs JPL Horizons, 25 epochs 2024–2050 | 1″ | ≤ 0.05″ | pass |
| Barker et al. (2021), RoI 4 average illumination (≥ 1st percentile) | −1.0 pp | 77.46% vs 69.61% | pass |
| Barker RoI 4 LCIP (≥ 1st percentile) | −2 d | 192.2 d vs 136.49 d | pass |
| Barker RoI 4 LCSP (≤ 99th percentile) | +1 d | 10.05 d vs 13.27 d | pass |
| Barker 70% contour, two-sided | 0.5 pp | inside min 70.03%, outside max 70.19% | pass |
| PGDA product 69, Earth, 5 × 5 pixels: mean \|difference\| | 5 pp | 3.3 pp | pass |
| PGDA product 69, Sun, 5 × 5 pixels: mean \|difference\| | 5 pp | 8.7 pp (no bias: mean −1.7 pp) | **miss**; inconclusive at this resolution (§6.3) |
| Product 69 rerun, stand-in terrain `LDEM_75S_60M`: Sun at 0 m / 2 m; Earth | Sun 9.6 pp; Earth 5 pp | Sun 7.28 / 17.74 pp; Earth 2.80 / 4.30 pp | Sun pass at 0 m (miss at 2 m); Earth pass |

- **What limits the numbers is the terrain map, not the numerics** ([§6.6](docs/methodology.md#66-accuracy-of-the-served-numbers)). At Connecting Ridge, a ±0.2° near-field horizon error (about Barker's median height error at 100 m) gives an illumination fraction of 64.8–74.1% (served 69.8%). The Earth metrics are far less affected.
- **Other sites:** `VERIFY:` methodology §6.7 (validation at the other curated sites) is still being written; its headline numbers go here.

## Natural-language questions: evaluation

The question box is scored on a labelled eval set (`tests/nl/eval_set.yaml`, 26 items, with a dev and a holdout split) for (a) the structured query and (b) the reason given when it refuses or answers in part.

Latest run, **run 5** (2026-11-16, `claude-opus-5-5`, effort low, prompt `p6-draft`), copied from the harness output [`tests/nl/results/2026-11-16T042950Z_claude_claude-opus-5-5_p6-draft.json`](tests/nl/results/2026-11-16T042950Z_claude_claude-opus-5-5_p6-draft.json):

| Score (dev split) | Correct | Total |
|---|---|---|
| (a) structured query | 11 | 13 |
| (b) refusal / partial reason | 6 | 11 |
| valid output | 19 | 19 |

Run 5 covered 19 of the 26 items, all from the dev split. **The holdout split was not run.** Items k6 and k7 have been labelled since run 5 and have not been run live yet.

## Data, references and glossary

- **Data used:** all NASA, listed with every planned dataset in the dataset registry [`lss/registry/datasets.yaml`](lss/registry/datasets.yaml) (served at `/api/datasets`):
  - Terrain: NASA GSFC PGDA LOLA elevation maps. The 5 m site maps (product 78; Barker et al. 2021) give the near field; the large-area south-pole maps (product 90; Barker et al. 2023) give the far field. Slope statistics use the 5 m site maps within 1 km and product 90's 10 m map within 10 km.
  - Sun and Earth geometry: JPL's DE421 ephemeris and lunar orientation, through NAIF SPICE.
  - Validation: Barker et al. (2021), PGDA product 69 (Mazarico et al. 2011), JPL Horizons and the PDS LOLA 60 m polar map. The limb-darkening law is from Allen's *Astrophysical Quantities* (3rd ed., 1973, §81).
- **Globe:** Cesium Moon, display only (no number comes from it). Data provided by: NASA and the USGS Astrogeology Science Center.
- **Software:** open source, listed with licenses: Python (FastAPI, NumPy, Numba, rasterio, SpiceyPy, Pydantic, …) and web (React, CesiumJS, Vite, TypeScript).
- **[References](docs/references.md):** every dataset, paper, book, service and package, with citations, links and terms.
- **[Glossary](docs/glossary.md):** every term on the screen and in the methodology, each with a plain-language sentence first, then the precise definition. Key ideas:
  - the **terrain horizon** decides when the Sun and Earth are really visible;
  - **sunlit** means any part of the Sun's disc is visible;
  - the **mean visible disc fraction** measures how much of the Sun's light gets through;
  - **Earth clearance** is how far Earth sits above the terrain.

## AI usage

This project was built with SI (AI) assistance from Claude (Anthropic). **The concept and features are the author's.**

**Models and what each was used for:**
- **Claude Opus 5.5:** all development sessions (Claude Code: engine, API and natural-language layer, web, docs) and the research, planning and orchestration chats. It is also the model the live question box calls (`claude-opus-5-5`) and the model scored in the eval above.
- **Claude Fable 5.2:** an independent correctness review of the horizon, frames and metric definitions at the G1 checkpoint. Its findings were applied by the engine stream. A second review is planned at G2.

**What Claude generated:** the code and tests; drafts of the methodology, references, glossary and this README; data research (finding and checking datasets and papers); the architecture and build-plan recommendations; drafts of the visitor-facing texts. The list of candidate metrics was supplied by Claude at the author's request, and she chose the metrics from it.

**What the author decided:** the concept, the features and their scope; the validation design (one check against Barker et al. 2021 and one against PGDA product 69); the metric definitions; the served sites, heights and windows, and the rule for each site's point; the limb-darkening law; the layout and design. She approved every visitor-facing text and edited some of them, and she authored every commit.

**Labels:** source and data files written with Claude carry a header saying so. In the app, the question box says that a language model turns the question into a query and that the numbers come from the precomputed results, not from the model; the model is Claude Opus 5.5 (above).

## Run it locally

- **Web:** see [`web/README.md`](web/README.md) (`npm ci`, `npm run dev`). It can run on the committed example responses (`?source=fixtures`) without the API.
- **API:** `uv run uvicorn lss.api.app:app --reload` from the repo root. Data files are fetched by `scripts/fetch_data.py` into `LSS_DATA_DIR`; the API serves precomputed results (see [`deploy/README.md`](deploy/README.md)).
- **Deploy:** [`deploy/README.md`](deploy/README.md) (Cloud Run for the API, Firebase Hosting for the web).

## License

Apache-2.0. See [LICENSE](LICENSE).
