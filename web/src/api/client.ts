// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// Typed API client. Types come from fixtures/openapi.json (npm run gen:types).
import type { components } from './schema'

export type Schemas = components['schemas']
export type HealthResponse = Schemas['HealthResponse']
export type SitesResponse = Schemas['SitesResponse']
export type Site = Schemas['Site']
export type SiteLocation = Schemas['Location']
export type Scenario = Schemas['Scenario']
export type MetricsResponse = Schemas['MetricsResponse']
export type PowerMetrics = Schemas['PowerMetrics']
export type CommsMetrics = Schemas['CommsMetrics']
export type Stat = Schemas['Stat']
export type MetricEvent = Schemas['Event']
export type FidelityLabel = Schemas['FidelityLabel']
export type SeriesResponse = Schemas['SeriesResponse']
export type BodyTrack = Schemas['BodyTrack']
export type HorizonProfile = Schemas['HorizonProfile']
export type TerrainLayer = Schemas['TerrainLayer']

export const API_BASE = (import.meta.env.VITE_API_BASE ?? '').replace(/\/$/, '')

/** Contract version the web was built against (from fixtures/openapi.json). */
export const WEB_CONTRACT_VERSION = __CONTRACT_VERSION__

async function readJson<T>(path: string, res: Response): Promise<T> {
  if (!res.ok) {
    let detail = ''
    try {
      const body = (await res.text()).trim().slice(0, 300)
      if (body) detail = `: ${body}`
    } catch {
      // body unreadable; the status alone is reported
    }
    throw new Error(`${path}: HTTP ${res.status}${detail}`)
  }
  return (await res.json()) as T
}

export async function getJson<T>(path: string): Promise<T> {
  return readJson<T>(path, await fetch(`${API_BASE}${path}`))
}

export async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return readJson<T>(path, res)
}

export const getHealth = () => getJson<HealthResponse>('/api/health')
export const getSites = () => getJson<SitesResponse>('/api/sites')
export const postMetrics = (scenario: Scenario) =>
  postJson<MetricsResponse>('/api/metrics', { scenario })
