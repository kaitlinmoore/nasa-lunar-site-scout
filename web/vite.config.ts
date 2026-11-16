// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
//
// Build-time configuration:
// - Reads the repo's .env (LSS_ENV_FILE if set, else ../.env) for CESIUM_ION_TOKEN.
//   The token is PUBLIC by design (it ships in the bundle); restrict it in Cesium ion.
//   Only CESIUM_ION_TOKEN is exposed; nothing else from .env reaches the browser.
// - VITE_API_BASE (process env) sets the API origin for deployed builds; empty = same origin.
// - The dev server proxies /api to the local API (uv run uvicorn lss.api.app:app).
// - Field descriptions from the contract (fixtures/openapi.json) are injected as
//   __FIELD_DOCS__ so the UI shows the contract's own definitions, not hand-copied ones.
// - The dev server may read ../fixtures (fixture mode, see web/README.md).
// - Cesium (C7a globe): its static runtime files (Workers, ThirdParty, Assets, Widgets) are
//   copied to /cesium/ and CESIUM_BASE_URL points there (Cesium's documented Vite setup).
//   The token is logged by length only, never printed.
// - 2D site view (C5, fixture mode until C api's GET /api/terrain/views, contract 0.13.0): the DEV
//   server serves stream A's terrain images from LSS_DATA_DIR/cache/terrain_view at
//   /dev-terrain-view/ (hillshade and slope PNGs, plus <site>/views.json listing that site's
//   view.json bodies). Not part of any build.
import { createReadStream, existsSync, readdirSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { parseEnv } from 'node:util'
import react from '@vitejs/plugin-react'
import { defineConfig, type Plugin, searchForWorkspaceRoot } from 'vite'
import { viteStaticCopy } from 'vite-plugin-static-copy'

const repoRoot = resolve(import.meta.dirname, '..')
const envFile = process.env.LSS_ENV_FILE || resolve(repoRoot, '.env')
const fileEnv: Record<string, string | undefined> = existsSync(envFile)
  ? parseEnv(readFileSync(envFile, 'utf-8'))
  : {}
const cesiumToken = process.env.CESIUM_ION_TOKEN ?? fileEnv.CESIUM_ION_TOKEN ?? ''
console.info(
  cesiumToken
    ? `Cesium ion token: set (${cesiumToken.length} chars) from ${process.env.CESIUM_ION_TOKEN ? 'process env' : envFile}`
    : `Cesium ion token: NOT set (looked in ${envFile})`,
)

const openapi = JSON.parse(readFileSync(resolve(repoRoot, 'fixtures/openapi.json'), 'utf-8'))
const contractVersion: string = openapi.info['x-contract-version']
// The longest question POST /api/nl accepts (NLRequest.text maxLength), so the box can't drift from it.
const nlMaxTextChars: number = openapi.components.schemas.NLRequest.properties.text.maxLength

// { SchemaName: { field: description } } for the models the UI explains to the user.
type JsonSchema = { properties?: Record<string, { description?: string }> }
const documented = [
  'Scenario',
  'PowerMetrics',
  'CommsMetrics',
  'Event',
  'FidelityLabel',
  'BodyTrack',
  'HorizonProfile',
  'SeriesResponse',
  'TerrainResponse',
]
const fieldDocs = Object.fromEntries(
  documented.map((name) => {
    const props = (openapi.components.schemas[name] as JsonSchema).properties ?? {}
    return [
      name,
      Object.fromEntries(
        Object.entries(props).flatMap(([k, v]) => (v.description ? [[k, v.description]] : [])),
      ),
    ]
  }),
)

// Same lookup as lss/config.py: LSS_DATA_DIR from the environment or .env, else the shared folder
// next to the worktrees.
const dataDir = process.env.LSS_DATA_DIR || fileEnv.LSS_DATA_DIR || resolve(repoRoot, '..', 'lss-data')
const terrainViewDir = resolve(dataDir, 'cache', 'terrain_view')

/** Dev only: stream A's terrain images at /dev-terrain-view/ (see the header). */
function devTerrainViews(): Plugin {
  const route = /^\/dev-terrain-view\/([a-z0-9-]+)\/(?:views\.json|([a-z0-9]+)\/(hillshade|slope)\.png)$/
  return {
    name: 'lss-dev-terrain-views',
    apply: 'serve',
    configureServer(server) {
      console.info(
        `Terrain images (2D view, dev only): ${terrainViewDir}${existsSync(terrainViewDir) ? '' : ' (missing)'}`,
      )
      server.middlewares.use('/dev-terrain-view', (req, res) => {
        const m = route.exec(`/dev-terrain-view${(req.url ?? '').split('?')[0]}`)
        const siteDir = m ? resolve(terrainViewDir, m[1]) : ''
        const notFound = () => {
          res.statusCode = 404
          res.setHeader('Content-Type', 'application/json')
          res.end(JSON.stringify({ detail: { reason: 'No terrain images for this site or view.' } }))
        }
        if (!m || !existsSync(siteDir)) return notFound()
        if (!m[2]) {
          const views = readdirSync(siteDir, { withFileTypes: true })
            .filter((d) => d.isDirectory() && existsSync(resolve(siteDir, d.name, 'view.json')))
            .map((d) => JSON.parse(readFileSync(resolve(siteDir, d.name, 'view.json'), 'utf-8')))
          res.setHeader('Content-Type', 'application/json')
          return res.end(JSON.stringify({ views }))
        }
        const file = resolve(siteDir, m[2], `${m[3]}.png`)
        if (!existsSync(file)) return notFound()
        res.setHeader('Content-Type', 'image/png')
        createReadStream(file).pipe(res)
      })
    },
  }
}

/** Where Cesium's static runtime files are served from (relative to the site root). */
const cesiumBaseUrl = 'cesium'

export default defineConfig({
  plugins: [
    react(),
    devTerrainViews(),
    viteStaticCopy({
      targets: [
        {
          src: 'node_modules/cesium/Build/Cesium/{Workers,ThirdParty,Assets,Widgets}/**/*',
          dest: cesiumBaseUrl,
          rename: { stripBase: 4 }, // drop node_modules/cesium/Build/Cesium
        },
      ],
    }),
  ],
  define: {
    CESIUM_BASE_URL: JSON.stringify(`/${cesiumBaseUrl}/`),
    __CONTRACT_VERSION__: JSON.stringify(contractVersion),
    __FIELD_DOCS__: JSON.stringify(fieldDocs),
    __NL_MAX_TEXT_CHARS__: JSON.stringify(nlMaxTextChars),
    'import.meta.env.VITE_CESIUM_ION_TOKEN': JSON.stringify(cesiumToken),
  },
  server: {
    proxy: { '/api': 'http://127.0.0.1:8000' },
    fs: { allow: [searchForWorkspaceRoot(process.cwd()), resolve(repoRoot, 'fixtures')] },
  },
})
