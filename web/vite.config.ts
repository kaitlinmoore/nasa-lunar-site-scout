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
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { parseEnv } from 'node:util'
import react from '@vitejs/plugin-react'
import { defineConfig, searchForWorkspaceRoot } from 'vite'

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

// { SchemaName: { field: description } } for the models the UI explains to the user.
type JsonSchema = { properties?: Record<string, { description?: string }> }
const documented = ['Scenario', 'PowerMetrics', 'CommsMetrics', 'Event', 'FidelityLabel']
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

export default defineConfig({
  plugins: [react()],
  define: {
    __CONTRACT_VERSION__: JSON.stringify(contractVersion),
    __FIELD_DOCS__: JSON.stringify(fieldDocs),
    'import.meta.env.VITE_CESIUM_ION_TOKEN': JSON.stringify(cesiumToken),
  },
  server: {
    proxy: { '/api': 'http://127.0.0.1:8000' },
    fs: { allow: [searchForWorkspaceRoot(process.cwd()), resolve(repoRoot, 'fixtures')] },
  },
})
