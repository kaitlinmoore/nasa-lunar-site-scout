<!-- SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage". -->
# Penumbra Luna

*Lunar Landing Site Navigator*

**Live app: https://penumbra-luna.web.app** (no login).

- **Results are precomputed**, for the sites and scenarios listed under [Sites](#sites); the app offers only those.
- **Questions** typed into the question box are sent to Claude live, with a rate limit per connection and a daily
  limit for the whole demo. When the daily limit is reached, live questions pause until the next day (UTC).
- **Example questions**, listed under the question box, have saved answers: they return at once, without a model
  call, and keep working when live questions are paused or the model can't be reached.

Terrain-aware lunar landing site planner. Compare sites and dates for sunlight and direct-to-Earth communications using LOLA topography and JPL ephemerides.

> Built for the 2026 NASA Space Apps Challenge (Lunar Landing Site Navigator). Not affiliated with or endorsed by NASA.

## What it does

The decision it supports: **where to land and when.** It is built for mission planners (a rover + lander mission, where the lander needs a direct line of sight to Earth) and for the public, in the same tool: sophisticated features are easy to reach when needed, without overwhelming casual users.

- **Globe:** a 3D Moon (Cesium Moon, display only) with the curated sites as markers. Click one for its card, then open its site screen.
- **Site screen:** pick a time window and unit height (the picker offers only that site's precomputed scenarios), then see:
  - **power:** illumination, mean visible solar disc, sunlit duration, longest sunlit period, longest shadow, shadow periods, Sun elevation and azimuth, time to sunset;
  - **communications (direct to Earth):** Earth visibility, Earth full disc, longest Earth gap, Earth elevation, Earth clearance, Sun + Earth overlap, time to Earthset;
  - **sky view:** the terrain horizon with the Sun and Earth tracks over the window, and a timeline of sunrises, sunsets, Earthrises and Earthsets;
  - **terrain map (2D)**, for 17 sites (the 8 south-pole sites and the 9 Artemis III regions): the ground around the site's point, seen from above, as shaded relief with five slope classes on top. Two square views: 2 km across, from the 5 m site map (5 m pixels; at the six Artemis III regions whose point lies on no 5 m map, from the 10 m polar map with 10 m pixels), and 20 km across, from the 10 m polar map (20 m pixels) ([methodology §5.7](docs/methodology.md#57-terrain-images-for-the-2d-site-view-lssterrainviews)). "Map up" is the map grid's axis, not geographic north; an arrow shows true north. The Apollo sites, off the polar maps, have none ("No terrain images for this site yet").
- **Save and compare:** save scenarios and compare them side by side, several sites and several dates. Saved items stay in your browser, with export and import.
- **Ask in plain English:** a question box (it uses Claude) turns a question into a query, shows how it understood it, and answers from the same results. When a question can't be answered with the available data, it says so and why.

### Sites

The site list is [`lss/registry/sites.yaml`](lss/registry/sites.yaml) (served at `/api/sites`). It has **23 sites** in three groups (tables in the [glossary](docs/glossary.md#curated-sites)):

- **8 south-pole sites** from the PGDA landing-site maps: Connecting Ridge, Shackleton Rim, Peak near Shackleton, de Gerlache Rim, Nobile Rim, Leibnitz Beta Plateau, Malapert Massif and de Gerlache–Kocher Massif. Their points come from Barker et al. (2021) and Mazarico et al. (2011) ([methodology §1.4](docs/methodology.md#14-curated-sites)).
- **6 Apollo landing sites:** Apollo 11, 12, 14, 15, 16 and 17, at the position of each Lunar Module's descent stage as located in Lunar Reconnaissance Orbiter camera images (Wagner et al. 2017) ([§1.4.2](docs/methodology.md#142-apollo-landing-sites)).
- **9 Artemis III candidate regions:** Peak near Cabeus B, Haworth, Malapert Massif, Mons Mouton Plateau, Mons Mouton, Nobile Rim 1, Nobile Rim 2, de Gerlache Rim 2 and Slater Plain, the regions NASA named on 28 October 2024 ([§1.4.3](docs/methodology.md#143-artemis-iii-candidate-regions)). In February 2026 NASA made Artemis III a crewed test flight in Earth orbit and planned the first landing for Artemis IV in 2028; NASA's Artemis IV page still shows the same nine regions. NASA gives no centre for a region. Each point here is the centre of the region's 1 km navigation grid from the U.S. Geological Survey (McClernan 2024): a geometric point, not a landing site. Their names on the globe end in "region", so they stay distinct from the south-pole sites of the same name.

**Results are precomputed.** For every site: unit heights 1, 2, 5 and 10 m, over three windows: 15 May – 14 Jun 2028 and 15 – 25 Nov 2028 (results every hour), and all of 2028 (every 6 hours). That is 276 precomputed scenarios ([§6.5](docs/methodology.md#65-served-result-and-regression-fixture)). Any other request is refused with the list of what is served.

How detailed the terrain behind each result is (its [fidelity label](docs/glossary.md#fidelity-label)):

| Group | Terrain near the site | Fidelity |
|---|---|---|
| South-pole sites | the 5 m PGDA site map, then the 80 m and 240 m polar maps | high |
| Artemis III regions | Malapert Massif, Mons Mouton and Nobile Rim 1: the 5 m site maps (their centres lie on them); the other six: the 80 m and 240 m polar maps | high (3), medium (6) |
| Apollo sites | the 237 m global LOLA map only ([§3.5](docs/methodology.md#35-global-coarse-layer-horizons-off-the-polar-maps)) | low |

At the Apollo sites, "relief smaller than a few hundred metres is not in the horizon. The values describe the regional setting, not a particular spot on the ground" ([§6.5](docs/methodology.md#65-served-result-and-regression-fixture)). Their slope statistics are measured on the same 237 m map: "regional slopes, not comparable with the 5 m and 10 m values at the polar sites" ([§5.6.1](docs/methodology.md#561-slope-off-the-polar-maps-the-global-coarse-layer)).

## How it works

Full detail, with every convention, test and number: [`docs/methodology.md`](docs/methodology.md).

- **Terrain:** NASA GSFC PGDA elevation maps from LOLA: the 5 m site maps for the near field, then 80 m and 240 m maps out to 400 km. Off the polar maps (the Apollo sites), the 237 m global LOLA map `LDEM_128` is the only terrain. All are in the same Moon frame (MOON_ME, DE421) as the ephemeris, so no frame alignment is needed.
- **Sun and Earth:** JPL's DE421 ephemeris and lunar orientation through NAIF SPICE, with light time and stellar aberration. Libration is included in every Earth position.
- **Horizon:** for each 0.1° of azimuth, the highest terrain along a ray over the curved Moon, out to 400 km. Accepted horizon error: at most about 0.01°.
- **Visibility:** the Sun is a limb-darkened disc (Allen 1973, 550 nm) and the Earth a disc, each cut by the real horizon profile. "Sunlit" means any part of the Sun's disc is visible, as in Barker et al. (2021) and PGDA product 69. Rises and sets are found on a 60 s grid and refined to 0.5 s.

## Validation

From [methodology §6](docs/methodology.md#6-validation-results). Every tolerance was fixed before its run; a miss is reported as a miss.

| Check | Tolerance | Result | Verdict |
|---|---|---|---|
| Sun and Earth az/el vs JPL Horizons, 25 epochs 2024–2050 | 1″ | ≤ 0.05″ | pass |
| The same at a second site, Site06 (85.3°S, 37°E) | 1″ | ≤ 0.05″ | pass |
| Barker et al. (2021), RoI 4 average illumination (≥ 1st percentile) | −1.0 pp | 77.46% vs 69.61% | pass |
| Barker RoI 4 LCIP (≥ 1st percentile) | −2 d | 192.2 d vs 136.49 d | pass |
| Barker RoI 4 LCSP (≤ 99th percentile) | +1 d | 10.05 d vs 13.27 d | pass |
| Barker 70% contour, two-sided | 0.5 pp | inside min 70.03%, outside max 70.19% | pass |
| PGDA product 69, Earth, 5 × 5 pixels: mean \|difference\| | 5 pp | 3.3 pp | pass |
| PGDA product 69, Sun, 5 × 5 pixels: mean \|difference\| | 5 pp | 8.7 pp (no bias: mean −1.7 pp) | **miss**; inconclusive at this resolution (§6.3) |
| Product 69 rerun, stand-in terrain `LDEM_75S_60M`: Sun at 0 m / 2 m; Earth | Sun 9.6 pp; Earth 5 pp | Sun 7.28 / 17.74 pp; Earth 2.80 / 4.30 pp | Sun pass at 0 m (miss at 2 m); Earth pass |
| Barker RoI definition at Site04, 07, 11 (sampled pixels > 70%) | 0.5 pp | Site04 70.02%, Site11 70.01%; Site07 one pixel at 69.03%, enclosed by the outline | pass, pass, **miss** (§6.7) |
| Mazarico et al. (2011) Table 3, 8 sites, matched method | from 120 m shifts | all four comparisons above tolerance; at 10 m the 7 points other than rank 20 agree within 1.4 pp | **miss** (§6.7) |

- **What limits the numbers is the terrain map, not the numerics** ([§6.6](docs/methodology.md#66-accuracy-of-the-served-numbers-at-site01)). At Connecting Ridge, a ±0.2° near-field horizon error (about Barker's median height error at 100 m) gives an illumination fraction of 64.8–74.1% over the 30-day window (served 69.8%).
- **The same measure at every south-pole site** ([§6.6.1](docs/methodology.md#661-every-pgda-site-1-m-2028)), over 2028 at 1 m:
  - Sun: "A ±0.2° near-field shift moves the 2028 illumination by under 1 pp (Site11, Site42) to about 4 pp (Site23)."
  - Earth: "Its metrics are insensitive to near-field terrain only at Site01 and Site11." At the other six sites: "The same shift moves Earth visibility by about ±1 pp and the longest Earth gap by about ±6 h there."
  - "±0.2° is a lower bound where terrain is closer than 100 m." "So at 1–2 m the Mazarico points and Site04 depend on terrain within tens of metres, for the Sun and the Earth, and the uniform shift understates their uncertainty."
- **The other curated sites** ([§6.7](docs/methodology.md#67-the-other-curated-sites-against-published-numbers)):
  - Against the RoI averages read from Barker et al. (2021)'s supplementary figures (an approximate check, with no tolerance): "Average illumination agrees to within 0.6 pp at 9 of the 10 RoIs (Site04 RoI 3: +1.2 pp). LCSP agrees to within 0.5 d at all 10, and LCIP to within 3.5 d at 9 (Site04 RoI 3: +15.5 d)." Site04 RoI 3 at every pixel: "74.73%, 104.7 d and 11.59 d, against the figure's 74.5%, 104.8 d and 11.68 d. The sampled outlier was sampling scatter."
  - Against Mazarico et al. (2011) Table 3: "At 10 m the other seven points agree closely: average illumination within 1.4 pp and visibility within 0.4 pp with the matched setting." "At the surface the differences remain (ours lower by 6–8 pp on average, up to 17 pp, with the matched setting)."
  - The four sites at Mazarico's published coordinates: "So at 1–2 m none of the four represents the well-lit ground Table 3 describes; Site06, 23 and 42 reach Table 3's level at 5–10 m, Site20 at no height."
  - Site20 (Leibnitz Beta Plateau): "On Mazarico's 2010 map both points of the cluster were above 80% at the surface; on ours neither is, and nothing within 720 m is."

## Natural-language questions: evaluation

The question box is scored on a labelled eval set (`tests/nl/eval_set.yaml`, 26 items, with a dev and a holdout split) for (a) the structured query and (b) the reason given when it refuses or answers in part.

**Latest scored run: run 8** (2026-11-16): prompt **`p10-draft`**, schema `nl-output-6`, `claude-opus-5-5` at effort low, refusal fallback off, dev split only. Scores are copied from the harness output, [run 8](tests/nl/results/2026-11-16T101718Z_claude_claude-opus-5-5_p10-draft.json); run 7 ([harness output](tests/nl/results/2026-11-16T081500Z_claude_claude-opus-5-5_p9-draft.json)) is the previous result.

| Score (dev split) | Run 8, `p10-draft` (latest) | Run 7, `p9-draft` (previous) |
|---|---|---|
| (a) structured query | 13 / 15 (of which clarification 1 / 1) | 13 / 15 (of which clarification 1 / 1) |
| (b) refusal / partial reason | 8 / 13 | 8 / 13 |
| valid output | 21 / 21 | 21 / 21 |

- Both runs covered 21 of the 26 items, all from the dev split. **The holdout split has not been run.**
- Run 8 scores every item as run 7 did: no item changed, so there are no regressions.
- **The live site runs `p10-draft`** ([`lss/nl/prompt.py`](lss/nl/prompt.py)), the prompt scored in run 8. Eval runs turn the refusal fallback off, so every score is the chosen model's own answer; the live question box has it on (a request the model declines on safety grounds is re-run on another model).

## Data, references and glossary

- **Data used:** every number comes from NASA data, listed with every planned dataset in the dataset registry [`lss/registry/datasets.yaml`](lss/registry/datasets.yaml) (served at `/api/datasets`):
  - Terrain: NASA GSFC PGDA LOLA elevation maps. The 5 m site maps (product 78; Barker et al. 2021) give the near field; the large-area south-pole maps (product 90; Barker et al. 2023) give the far field. Off the polar maps, the global LOLA map `LDEM_128` (PDS). Slope statistics use the 5 m site maps within 1 km and product 90's 10 m map within 10 km (the 10 m map at both radii where a point has no 5 m map; `LDEM_128` at the Apollo sites).
  - Sun and Earth geometry: JPL's DE421 ephemeris and lunar orientation, through NAIF SPICE.
  - Validation: Barker et al. (2021) and its supplementary figures, PGDA product 69, Mazarico et al. (2011) Table 3, JPL Horizons and the PDS LOLA 60 m polar map. The limb-darkening law is from Allen's *Astrophysical Quantities* (3rd ed., 1973, §81).
  - Apollo site positions: the Lunar Module descent stages located in LRO camera images (Wagner et al. 2017), as listed by NASA's NSSDCA.
  - Artemis III regions: named by NASA (release 24-136, October 2024); each point is the centre of the region's 1 km navigation grid, a U.S. Geological Survey data release (McClernan 2024).
- **Globe:** Cesium Moon, display only (no number comes from it). Data provided by: NASA and the USGS Astrogeology Science Center.
- **Software:** open source, listed with licenses: Python (FastAPI, NumPy, Numba, rasterio, SpiceyPy, Pydantic, …) and web (React, CesiumJS, OpenLayers, proj4, Vite, TypeScript).
- **[References](docs/references.md):** every dataset, paper, book, service and package, with citations, links and terms.
- **[Glossary](docs/glossary.md):** every term on the screen and in the methodology, each with a plain-language sentence first, then the precise definition. Key ideas:
  - the **terrain horizon** decides when the Sun and Earth are really visible;
  - **sunlit** means any part of the Sun's disc is visible;
  - the **mean visible disc fraction** measures how much of the Sun's light gets through;
  - **Earth clearance** is how far Earth sits above the terrain.

## AI usage

**About the term "SI":** the 2026 NASA Space Apps Challenge Project Submission Guide calls AI tools such as machine learning, chatbots, image generation and large language models "Super Intelligence (SI)", and requires that SI generation of code and data be acknowledged in descriptive text and metadata. This project follows that convention, so "SI-assisted" in file headers means "AI-assisted".

This project was built with SI (AI) assistance from Claude (Anthropic). **The concept and features are the author's.**

**Models and what each was used for:**
- **Claude Opus 5.5:** all development sessions (Claude Code: engine, API and natural-language layer, web, docs) and the research, planning and orchestration chats. It is also the model the live question box calls (`claude-opus-5-5`) and the model scored in the eval above.
- **Claude Fable 5.2:** an independent correctness review of the horizon, frames and metric definitions (signed off 2026-11-15). Its findings were applied in the engine. A second Fable 5.2 review (2026-11-16) covered the validation of the other curated sites; its findings were also applied in the engine (methodology §6.6.1 and §6.7, among others).

**What Claude generated:** the code and tests; drafts of the methodology, references, glossary and this README; data research (finding and checking datasets and papers); architecture and build-plan recommendations; drafts of visitor-facing texts.

**What the author decided:** the concept, the features and their scope; the validation design; the metric definitions; the served sites, heights and windows, and the rule for each site's point; the limb-darkening law; the layout and design. Approved and edited visitor-facing text, authored all commits.

**Labels:** source and data files written with Claude carry a header saying so. In the app, the question box says that a language model turns the question into a query and that the numbers come from the precomputed results, not from the model; the model is Claude Opus 5.5 (above).

## Run it locally

- **Web:** see [`web/README.md`](web/README.md) (`npm ci`, `npm run dev`). It can run on the committed example responses (`?source=fixtures`) without the API.
- **API:** `uv run uvicorn lss.api.app:app --reload` from the repo root. Data files are fetched by `scripts/fetch_data.py` into `LSS_DATA_DIR`; the API serves precomputed results (see [`deploy/README.md`](deploy/README.md)).
- **Deploy:** [`deploy/README.md`](deploy/README.md) (Cloud Run for the API, Firebase Hosting for the web).

## License

Apache-2.0. See [LICENSE](LICENSE).
