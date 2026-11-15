<!-- SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage". -->
# Lunar Site Scout: web

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

The header shows which source is in use. Fixture data goes through the same generated contract types as live data, and fixture files load as a separate chunk, only in fixture mode. The fixtures are placeholders (`_placeholder: true`), so the screen shows the "placeholder data, not a computed result" notice.

## Views and URLs

- `/` (plus any `?source=`): the **globe** (C7a), the start page.
- `?view=saved`: saved items and the comparison (C6).
- `?site=<id>`: that curated site's screen. Back/forward work, and other query params (like `?source=fixtures`) are kept when moving between views. No router dependency (`src/route.ts`).
- A site's screen shows results only when they're for that site's location. So far only the C1 thin-slice scenario (Site01) has results; any other site says "No computed scenario for this site yet".

## Globe (C7a)

Cesium Moon (ion asset 2684829, imagery + LOLA terrain as one 3D tileset), **display only**: no numbers come from Cesium. Its terrain sits about 2.5 km above LOLA heights, so site markers are clamped to the rendered surface, and every value comes from our API.

- **Sites:** from `/api/sites`, or `fixtures/sites.json` in fixture mode. Click a marker (or a name in the list under the globe) to open the site's screen. The list is the accessible equivalent of the canvas markers and keeps working if WebGL or the token fails.
- **Markers:** drawn without the depth test (a clamped marker is otherwise half-buried in the terrain it sits on) and hidden when they're beyond the Moon's limb from the camera.
- **Lighting:** a light that follows the camera; Cesium's own Sun and Moon are hidden, so the globe never shows illumination we didn't compute.
- **Token:** `CESIUM_ION_TOKEN` from the repo's `.env` (or `LSS_ENV_FILE`), injected at build time; the build logs only whether it's set and its length. It ships in the bundle, so it's restricted in Cesium ion (allowed URLs, the Cesium Moon asset, `assets:read`). Local dev needs a token whose allowed URLs include `http://localhost:5173`. Without a token the page says so and the site list still works. Note: changing a token's permissions in ion can generate a new token value; update `.env` when that happens.
- **Build:** Cesium's runtime files (Workers, ThirdParty, Assets, Widgets) are copied to `/cesium/` (`vite-plugin-static-copy`; `CESIUM_BASE_URL`). Cesium is a separate lazy chunk (~4.2 MB, ~1.1 MB gzipped) loaded only on the globe, so the build prints Vite's "chunks larger than 500 kB" notice for it; that's expected.
- **Credits:** Cesium's credit bar stays visible (Cesium ion logo, "Upgrade for commercial use.", and "Data attribution" → "NASA and the USGS Astrogeology Science Center", text only).

## Save and compare (C6, comparison in fixture mode only for now)

- **Saved items** (plan §3.7, F8): pinned sites and saved scenarios, kept in this browser (`localStorage`) as one portable JSON document (`format: "lunar-site-scout.saved"`, `version: 1`). **Export** downloads that document; **Import** reads one, checks every scenario against the contract's rules (unknown fields rejected, as the API does), adds what's new, and lists anything it didn't import with the reason. Nothing already saved is overwritten. If stored data can't be read, a backup copy is kept in browser storage and the page says so.
- **Making scenarios:** "Save this scenario" and "Pin site" on a site screen, or the small form on the saved page (curated site, unit height, UTC window, step) for several sites × several dates. Duplicate scenarios aren't saved twice: scenarios are compared by location, height, UTC window and step (the location name doesn't matter; `PT60M` equals `PT1H`). That id is web-side only, not the server's `scenario_key`.
- **Comparison** (plan §3.1): the saved scenarios ticked for it, side by side, one column each, with the site screen's metric rows and value rules. In fixture mode a scenario has results only if it's exactly one of the scenarios in `fixtures/compare.json`; any other says "No result in fixture mode". Nothing is borrowed from a nearby scenario. Live mode says it's fixture-only until `POST /api/compare` is available. The saved page works even when the site list can't load (saved items are local).

## Sky view (C5, fixture mode only for now)

The horizon/sky plot and timeline use `fixtures/horizon.json` and `fixtures/series.json`. In live mode the section says it's fixture-only until the live horizon and series endpoints exist.

- **Plot:** terrain horizon profile (elevation vs azimuth, deg clockwise from north) with the Sun and Earth tracks over the window. Markers show the positions at the selected sample: filled when some of the disc is visible (`visible_fraction` > 0), hollow when none is.
- **Timeline:** the slider steps through the series samples (no interpolation between them). Event marks sit at the event's own time; selecting one shows that time as the API sent it (to the second, with a "refined" badge when refined), while the plot and readout move to the nearest sample and say so. Moving the slider clears the selection. The readout shows the Sun/Earth azimuth, elevation, visible disc and clearance at that sample, plus the terrain horizon at each body's azimuth. That horizon value is interpolated linearly between the two neighbouring profile samples (periodic over 360°), as the contract specifies, so it's the same value the engine uses; the readout says so and names the two samples. It uses the profile's own azimuths, so any spacing works (the real horizon is 0.1°). This is the one interpolated number on screen; everything else is shown as sent.
- **Checks:** the horizon and series must be for the same location and unit height, or nothing is plotted. Placeholder horizon or series data gets a notice in the section and a watermark in the plot.

## Display rules

- Values are shown exactly as sent (rounded for display; hover a value to see the API's number). Nothing is derived or defaulted, except the terrain horizon at a body's azimuth, which the contract defines as a linear interpolation of the profile (see Sky view).
- `null` metrics show as "not computed", never as 0.
- Units come from the contract's field-name convention (`_h` hours, `_deg` degrees, `_fraction` shown as %, `_m` meters). Counts (`_count`) name what they count and the scenario window they cover ("2 shadow periods, in the window …").
- Metric definitions are the contract's own field descriptions, read from `fixtures/openapi.json` at build time.
- `_clipped` flags (contract 0.3.0) aren't rows of their own: each is a note under the longest-period duration it qualifies. `true` → "clipped to the window; the full period is longer"; `null` → "not computed"; `false` → no note.
- `sunset_in_window` / `earthset_in_window` (contract 0.4.0): when the flag is `false`, `time_to_sunset_h` / `time_to_earthset_h` is null because the event doesn't happen in the window, and the value shows "no sunset in this window" / "no Earthset in this window". A null time with the flag `null` (or `true`) still shows "not computed".
- A contract version mismatch between the web build and the data shows a warning.

## Code layout: style, formatting, layout

The current look is a placeholder; the layout and visual style get decided at C5. To keep that pass cheap:

- **Style:** every colour, font, text size, spacing step, radius and plot stroke is a CSS variable (token) at the top of `src/index.css`. Rules below the token block use tokens for all of those; the only literal values are hairline borders (1px) and small fine-tuning offsets.
- **Formatting:** all value and text formatting (units, precision, dates, durations, counts) is in `src/format.ts`. Metric rows, labels and flag rules (shared by the site screen and the comparison) are in `src/metricSpec.ts`; the value cell is `MetricValue` in `src/metrics.tsx`.
- **Layout:** components (`src/SiteScreen.tsx`, `src/App.tsx`, `src/sky/`) arrange values. They call `format.ts` and use CSS classes, never ad-hoc formatting. The only inline style is a data-driven position (event marks on the timeline). SVG plot geometry (plot size, margins) is in `src/sky/HorizonPlot.tsx`; its colours and line widths are tokens.
