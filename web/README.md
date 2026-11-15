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

## Display rules

- Values are shown exactly as sent (rounded for display; hover a value to see the API's number). Nothing is derived or defaulted.
- `null` metrics show as "not computed", never as 0.
- Units come from the contract's field-name convention (`_h` hours, `_deg` degrees, `_fraction` shown as %, `_m` meters). Counts (`_count`) name what they count and the scenario window they cover ("2 shadow periods, in the window …").
- Metric definitions are the contract's own field descriptions, read from `fixtures/openapi.json` at build time.
- A contract version mismatch between the web build and the data shows a warning.

## Code layout: style, formatting, layout

The current look is a placeholder; the layout and visual style get decided at C5. To keep that pass cheap:

- **Style:** every colour, size, spacing and radius is a CSS variable (token) at the top of `src/index.css`. Rules below the token block only reference tokens.
- **Formatting:** all value and text formatting (units, precision, dates, durations, counts) is in `src/format.ts`.
- **Layout:** components (`src/SiteScreen.tsx`, `src/App.tsx`) arrange values. They call `format.ts` and use CSS classes, never inline styles or ad-hoc formatting.
