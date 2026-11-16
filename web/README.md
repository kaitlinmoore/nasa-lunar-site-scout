<!-- SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage". -->
# Penumbra Luna (Lunar Landing Site Navigator): web

Vite + React + TypeScript. Owner: stream B (web). See the repo README for the project.

## Commands (from `web/`)

| Command | What it does |
|---|---|
| `npm ci` | Install (once, and after `package-lock.json` changes) |
| `npm run dev` | Dev server on http://localhost:5173; proxies `/api` to http://127.0.0.1:8000 |
| `npm run build` | Typecheck + production build to `dist/` |
| `npm run typecheck` / `npm run lint` | Checks |
| `npm run gen:types` | Regenerate `src/api/schema.d.ts` from `../fixtures/openapi.json` (after any contract change) |

Local API (from the repo root): `uv run uvicorn lss.api.app:app --reload`.

## Data source: live API or fixtures

The app can run against the committed example responses in `../fixtures/*.json` instead of the API.

- **URL switch (wins):** add `?source=fixtures` to the URL, e.g. http://localhost:5173/?source=fixtures. `?source=live` forces the API.
- **Build/dev default:** the env variable `VITE_DATA_SOURCE=fixtures` makes fixtures the default when the URL has no `?source=`. Unset (the default) = live API.

**Live mode (4.4):** the site screen sends the thin-slice scenario (the `scenario` in `fixtures/metrics.json`, which is exactly the one the API serves) to `POST /api/metrics`. The API serves precomputed results only, matched exactly on the scenario. Failures are shown as errors, never as empty values:

- **422, scenario not served** (`detail: {reason, served}`): "No result for this scenario yet", the API's reason, and the scenarios it does serve with what differs.
- **422, malformed request** (FastAPI's `detail: [{loc, msg}]`): flagged as a bug in this app, with the field and message.
- **503** (`detail: {reason}`): results aren't available (none installed), with the reason.
- Any other HTTP error, or no answer at all, gets its own message.

The error bodies are contract models (0.6.0), typed from `fixtures/openapi.json`: `src/api/errors.ts` only tells a 422 "not served" (`detail` object) from a malformed request (`detail` list), as the contract says, and knows which route it called (a 422 from `/api/compare` means none of the scenarios is served). A 503's `detail.technical` (for developers) shows in dev builds only. Anything that doesn't fit is reported as a plain HTTP error. The horizon/sky view is live too (Phase 2 step 3.2): the thin-slice scenario's `POST /api/series` and the horizon for its location and unit height from `POST /api/horizon`; a horizon that isn't served shows the API's 422 like the metrics do.

**Static fallback** (plan §4.7): when the live API gives no usable answer (no connection, 503, any 5xx), the site list, the site screen's metrics and the comparison come from the static copy published with the web at `/static-api/` (`index.json` = contract `StaticIndex`, built at deploy from the same served results), and a notice says "The live server isn't answering right now, so you're seeing the saved copy…". A 422 is a real answer and never falls back. Firebase answers a missing file with the web page (status 200), so every static file's content type must be JSON or it counts as missing; if the copy can't help, the live failure is shown. Local test: `uv run python -m lss.api.static_export web/dist/static-api` after `npm run build`, then `npx vite preview`.

The header shows which source is in use. Fixture data goes through the same generated contract types as live data, and fixture files load as a separate chunk, only in fixture mode. The fixtures are placeholders (`_placeholder: true`), so the screen shows the "placeholder data, not a computed result" notice.

## Views and URLs

- `/` (plus any `?source=`): the **globe** (C7a), the start page.
- `?view=saved`: saved scenarios and the comparison (C6). The menu item, "Saved scenarios (n)", appears only once a scenario is saved (or while on that page); after "Save this scenario" on a site's screen, a "Compare saved scenarios →" link appears next to the button.
- `?site=<id>`: the globe with that site's screen open in a side panel (the globe zooms toward the site). Back/forward work, and other query params (like `?source=fixtures`) are kept when moving between views. No router dependency (`src/route.ts`).
- **Choosing a site** (Kaitlin, 2026-11-15, layout "card, then panel"): clicking a marker or a site in the list shows a card next to the marker (name, the start of the description, "See details", ✕; Escape or a click elsewhere closes it; a list click turns the globe to the site if it's out of view). "See details" opens the side panel beside the globe with the full site screen, and the globe zooms toward the site; closing the panel returns to the whole Moon. The globe stays mounted throughout. On narrow screens the panel stacks under the globe. Without a globe (no token, no WebGL) a list click opens the panel directly, or the card shows under the error.
- **Pinned sites** live on the globe (Kaitlin, 2026-11-15): a pinned site's marker has an accent ring and "★" before its name, the card has a Pin / Unpin button (as does the site screen), and the site list shows a "★ Pinned" group first. Pins are kept in the saved-items document, so export/import carry them, but the saved page shows only scenarios and the comparison.
- A site's screen shows results only when they're for that site's location. So far only the C1 thin-slice scenario (Site01) has results; any other site says "No computed scenario for this site yet".

## Globe (C7a)

Cesium Moon (ion asset 2684829, imagery + LOLA terrain as one 3D tileset), **display only**: no numbers come from Cesium. Its terrain sits about 2.5 km above LOLA heights, so site markers are clamped to the rendered surface, and every value comes from our API.

- **Sites:** from `/api/sites`, or `fixtures/sites.json` in fixture mode. Click a marker (or a name in the list under the globe) to open the site's screen. The list is the accessible equivalent of the canvas markers and keeps working if WebGL or the token fails.
- **Start view:** the whole Moon fitted to the canvas (narrower field of view, 12 % margin), seen from above 60° S on the first curated site's meridian, north up, so the south pole and Site01 sit in the lower part of the disc. A "South pole" label marks 90° S (it moves with the Moon and can't be selected), and a note "You're looking at the Moon's south pole (north is up)" shows until the first drag, wheel, pinch or zoom button, and again after Reset.
- **Zoom:** wheel ≈ 13 % per notch (`zoomFactor` 2; Cesium's default 5 was far too fast); limits 20 km to 12,000 km above the Moon ellipsoid. On-screen + / − / reset buttons (bottom right): ± move a fraction of the current height within the same limits; reset flies back to the start view.
- **Caption:** a plain sentence for visitors, with the expert detail (Cesium's terrain ~2.5 km above LOLA, markers on the rendered surface, no values from Cesium) behind a "Details" toggle.
- **Labels and crowded sites** (Kaitlin, 2026-11-15, after the crowded-sites readiness test): site labels show only when the camera is within 300 km of the site (`SITE_LABEL_MAX_DISTANCE_M`); a click that hits several site markers opens a chooser listing them (`scene.drillPick`, ±10 px). Dev-only test list: `?source=fixtures&testSites=crowded` (`web/test-data/sites-crowded.json`, made-up sites).
- **Markers:** drawn without the depth test (a clamped marker is otherwise half-buried in the terrain it sits on) and hidden when they're beyond the Moon's limb from the camera.
- **Lighting:** a light that follows the camera; Cesium's own Sun and Moon are hidden, so the globe never shows illumination we didn't compute.
- **Token:** `CESIUM_ION_TOKEN` from the repo's `.env` (or `LSS_ENV_FILE`), injected at build time; the build logs only whether it's set and its length. It ships in the bundle, so it's restricted in Cesium ion (allowed URLs, the Cesium Moon asset, `assets:read`). Local dev needs a token whose allowed URLs include `http://localhost:5173`. Without a token the page says so and the site list still works. Note: changing a token's permissions in ion can generate a new token value; update `.env` when that happens.
- **Build:** Cesium's runtime files (Workers, ThirdParty, Assets, Widgets) are copied to `/cesium/` (`vite-plugin-static-copy`; `CESIUM_BASE_URL`). Cesium is a separate lazy chunk (~4.2 MB, ~1.1 MB gzipped) loaded only on the globe, so the build prints Vite's "chunks larger than 500 kB" notice for it; that's expected.
- **Credits:** Cesium's credit bar stays visible (Cesium ion logo, "Upgrade for commercial use.", and "Data attribution" → "NASA and the USGS Astrogeology Science Center", text only).

## Save and compare (C6)

- **Saved items** (plan §3.7, F8): pinned sites and saved scenarios, kept in this browser (`localStorage`) as one portable JSON document (`format: "lunar-site-scout.saved"`, `version: 1`). **Export** downloads that document; **Import** reads one, checks every scenario against the contract's rules (unknown fields rejected, as the API does), adds what's new, and lists anything it didn't import with the reason. Nothing already saved is overwritten. If stored data can't be read, a backup copy is kept in browser storage and the page says so.
- **Making scenarios:** "Save this scenario" and "Pin site" on a site screen, or the small form on the saved page (curated site, unit height, UTC window, step) for several sites × several dates. Duplicate scenarios aren't saved twice: scenarios are compared by location, height, UTC window and step (the location name doesn't matter; `PT60M` equals `PT1H`). That id is web-side only, not the server's `scenario_key`.
- **Comparison** (plan §3.1): the saved scenarios ticked for it, side by side, one column each, with the site screen's metric rows and value rules. In fixture mode a scenario has results only if it's exactly one of the scenarios in `fixtures/compare.json`; any other says "No result in fixture mode". Nothing is borrowed from a nearby scenario. Live mode uses `POST /api/compare` (Phase 2 step 3.3): served scenarios show their results, the others show the API's reason in their column, and if none is served a notice says so. Each result must be exactly its column's scenario, or the comparison shows an error instead of values. The saved page works even when the site list can't load (saved items are local).

## Sky view (C5; live in Phase 2 step 3.2)

The horizon/sky plot and timeline use `fixtures/horizon.json` and `fixtures/series.json` in fixture mode, and `POST /api/series` + `POST /api/horizon` live (with the static copy as fallback). Live horizons are A's full-resolution profiles (0.1°, 3600 samples).

- **Plot:** terrain horizon profile (elevation vs azimuth, deg clockwise from north) with the Sun and Earth tracks over the window. Markers show the positions at the selected sample: filled when some of the disc is visible (`visible_fraction` > 0), hollow when none is.
- **Timeline:** the slider steps through the series samples (no interpolation between them). Event marks sit at the event's own time; selecting one shows that time as the API sent it (to the second, with a "refined" badge when refined), while the plot and readout move to the nearest sample and say so. Moving the slider clears the selection. The readout shows the Sun/Earth azimuth, elevation, visible disc and clearance at that sample, plus the terrain horizon at each body's azimuth. That horizon value is interpolated linearly between the two neighbouring profile samples (periodic over 360°), as the contract specifies, so it's the same value the engine uses; the readout says so and names the two samples. It uses the profile's own azimuths, so any spacing works (the real horizon is 0.1°). This is the one interpolated number on screen; everything else is shown as sent.
- **Checks:** the horizon and series must be for the same location and unit height, or nothing is plotted. Placeholder horizon or series data gets a notice in the section and a watermark in the plot.

## Questions (C7b, the NL box)

Below the dashboard on the site screen (Kaitlin, 2026-11-16), one box per site. A question goes to `POST /api/nl` (contract 0.8.0) with the site's id and, when the site has a computed scenario, that scenario. The language model only turns the question into one of the API's queries; the numbers come from the API's results and are shown with the site screen's own views (`src/nl/NlBox.tsx`; `src/nl/response.ts` tells the three answers apart and checks a result's fields before showing it).

- **Answer** (`NLAnswer`): "Understood as" (the echo), "Assumed" (`assumptions`), "Not answered" (`limitations`, with the data considered), then the result: metrics as the site screen, compare as the saved comparison table, sites as links, locate as its terrain stack; series and horizon get a short summary (no plot on their own yet). Any other operation, or a result missing fields this page reads, says it can't be shown and shows no values. The structured query is under "Query sent to the API".
- **Can't answer** (`NLUnsupported`) and **needs more information** (`NLClarification`): the API's reason or question, with the echo.
- **Errors:** 429 shows the API's reason and `retry_after_s`, and the Ask button stays off that long; 503 (paused at the daily cap, or the model can't be reached) shows the API's reason; no answer or a 404 says live questions aren't available (there's no saved copy of live answers, so no static fallback). The question length limit (`NLRequest.text` maxLength, 1000) comes from `fixtures/openapi.json` at build time (`__NL_MAX_TEXT_CHARS__`).
- **Fixture mode** doesn't send the question: a selector picks one of C api's example answers (`fixtures/nl_*.json`), shown as placeholder data.
- Live questions work on the deployed site once C api deploys `/api/nl`.

## Display rules

- Values are shown exactly as sent (rounded for display; hover a value to see the API's number). Nothing is derived or defaulted, except the terrain horizon at a body's azimuth, which the contract defines as a linear interpolation of the profile (see Sky view).
- `null` metrics show as "not computed", never as 0.
- Units come from the contract's field-name convention (`_h` hours, `_deg` degrees, `_fraction` shown as %, `_m` meters). Counts (`_count`) name what they count and the scenario window they cover ("2 shadow periods, in the window …").
- Metric definitions are the contract's own field descriptions, read from `fixtures/openapi.json` at build time.
- `_clipped` flags (contract 0.3.0) aren't rows of their own: each is a note under the longest-period duration it qualifies. `true` → "clipped to the window; the full period is longer"; `null` → "not computed"; `false` → no note.
- `sunset_in_window` / `earthset_in_window` (contract 0.4.0): when the flag is `false`, `time_to_sunset_h` / `time_to_earthset_h` is null because the event doesn't happen in the window, and the value shows "no sunset in this window" / "no Earthset in this window". A null time with the flag `null` (or `true`) still shows "not computed".
- A contract version mismatch between the web build and the data shows a warning, in every build.
- **Developer info** (data source, web/data contract versions) shows only in dev builds (`npm run dev`); production builds hide it. Placeholder notices and the mismatch warning always show.
- **Time window** (not "window"): shown as the range first, then the exact UTC times, e.g. "15 May – 14 Jun 2028 · 30 days · results every hour" and "from 15 May 2028 00:00 UTC to 14 Jun 2028 00:00 UTC". The length is plain arithmetic on the two times the API sent (allowed by Kaitlin). The step is in plain words ("results every hour"); the technical details (step as ISO 8601, scenario key, coordinates and their frame) sit in a collapsed "Advanced" area.
- **Times** are UTC and written explicitly ("2028-05-15 00:00 UTC"). The scenario form takes "YYYY-MM-DD HH:MM" in UTC (text fields with a visible "UTC"; the browser's date pickers would show local formats like "12:00 AM").
- **Site description:** a site's screen opens with its name and its `description` from /api/sites; an empty description is left out.

## Code layout: style, formatting, layout

The current look is a placeholder; the layout and visual style get decided at C5. To keep that pass cheap:

- **Style:** every colour, font, text size, spacing step, radius and plot stroke is a CSS variable (token) at the top of `src/index.css`. Rules below the token block use tokens for all of those; the only literal values are hairline borders (1px) and small fine-tuning offsets.
- **Formatting:** all value and text formatting (units, precision, dates, durations, counts) is in `src/format.ts`. Metric rows, labels and flag rules (shared by the site screen and the comparison) are in `src/metricSpec.ts`; the value cell is `MetricValue` in `src/metrics.tsx`.
- **Layout:** components (`src/SiteScreen.tsx`, `src/App.tsx`, `src/sky/`) arrange values. They call `format.ts` and use CSS classes, never ad-hoc formatting. The only inline styles are data-driven positions (event marks on the timeline, the globe's site chooser at the click point). SVG plot geometry (plot size, margins) is in `src/sky/HorizonPlot.tsx`; its colours and line widths are tokens.
