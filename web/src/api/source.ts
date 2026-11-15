// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// Data source switch: live API or the committed fixtures/*.json (see web/README.md).
// Both paths return the same generated contract types, so the screen can't tell them apart.
import { getSites, type MetricsResponse, postMetrics, type Scenario } from './client'

export type DataSource = 'live' | 'fixtures'

/** `?source=fixtures|live` in the URL wins; otherwise VITE_DATA_SOURCE; otherwise live. */
export function dataSource(): DataSource {
  const fromUrl = new URLSearchParams(window.location.search).get('source')
  const chosen = fromUrl ?? import.meta.env.VITE_DATA_SOURCE ?? 'live'
  return chosen === 'fixtures' ? 'fixtures' : 'live'
}

/** The C1 thin-slice site. */
export const THIN_SLICE_SITE_ID = 'pgda-site01'

/**
 * Thin-slice scenario for live mode (Kaitlin, 2026-11-14): Site01, 1 m, 2028-11-15 to
 * 2028-12-15 UTC. The step is NOT confirmed yet: stream A will set it (web-progress 4.4).
 */
export const THIN_SLICE_SCENARIO: Omit<Scenario, 'location'> = {
  unit_height_m: 1.0,
  window_start: '2028-11-15T00:00:00Z',
  window_end: '2028-12-15T00:00:00Z',
  step: 'PT6H', // UNCONFIRMED placeholder until stream A confirms the step
}

/**
 * Metrics for the thin-slice scenario (Site01).
 * Fixture mode: fixtures/metrics.json, loaded on demand (a separate chunk in the build).
 * Live mode: Site01 from GET /api/sites, then POST /api/metrics.
 */
export async function loadThinSliceMetrics(source: DataSource): Promise<MetricsResponse> {
  if (source === 'fixtures') {
    return (await import('../../../fixtures/metrics.json')).default as MetricsResponse
  }
  const { sites } = await getSites()
  const site = sites.find((s) => s.id === THIN_SLICE_SITE_ID)
  if (!site) throw new Error(`/api/sites: site ${THIN_SLICE_SITE_ID} not found`)
  return postMetrics({ location: site.location, ...THIN_SLICE_SCENARIO })
}
