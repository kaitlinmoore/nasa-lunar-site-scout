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
- **Formatting:** all value and text formatting (units, precision, dates, durations, counts) is in `src/format.ts`.
- **Layout:** components (`src/SiteScreen.tsx`, `src/App.tsx`, `src/sky/`) arrange values. They call `format.ts` and use CSS classes, never ad-hoc formatting. The only inline style is a data-driven position (event marks on the timeline). SVG plot geometry (plot size, margins) is in `src/sky/HorizonPlot.tsx`; its colours and line widths are tokens.
