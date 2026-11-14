// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// Typed API client. Types come from fixtures/openapi.json (npm run gen:types).
import type { components } from './schema'

export type Schemas = components['schemas']
export type HealthResponse = Schemas['HealthResponse']

export const API_BASE = (import.meta.env.VITE_API_BASE ?? '').replace(/\/$/, '')

/** Contract version the web was built against (from fixtures/openapi.json). */
export const WEB_CONTRACT_VERSION = __CONTRACT_VERSION__

export async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`)
  return (await res.json()) as T
}

export const getHealth = () => getJson<HealthResponse>('/api/health')
