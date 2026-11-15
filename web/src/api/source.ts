// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// Data source switch: live API or the committed fixtures/*.json (see web/README.md).
// Both paths return the same generated contract types, so the screen can't tell them apart.
import {
  getSites,
  type HorizonProfile,
  type MetricsResponse,
  postMetrics,
  type SeriesResponse,
  type SitesResponse,
} from './client'

export type DataSource = 'live' | 'fixtures'

/** `?source=fixtures|live` in the URL wins; otherwise VITE_DATA_SOURCE; otherwise live. */
export function dataSource(): DataSource {
  const fromUrl = new URLSearchParams(window.location.search).get('source')
  const chosen = fromUrl ?? import.meta.env.VITE_DATA_SOURCE ?? 'live'
  return chosen === 'fixtures' ? 'fixtures' : 'live'
}

/**
 * The C1 thin-slice response from fixtures/metrics.json. Its `scenario` is exactly the one
 * stream A serves, so live mode sends that scenario rather than a copy of its values: one
 * source, no drift. Loaded on demand (a separate build chunk).
 */
async function thinSliceFixture(): Promise<MetricsResponse> {
  return (await import('../../../fixtures/metrics.json')).default as MetricsResponse
}

/**
 * Metrics for the thin-slice scenario.
 * Fixture mode: the fixture response itself.
 * Live mode: POST /api/metrics with the fixture's scenario.
 */
export async function loadThinSliceMetrics(source: DataSource): Promise<MetricsResponse> {
  const fixture = await thinSliceFixture()
  return source === 'fixtures' ? fixture : postMetrics(fixture.scenario)
}

/**
 * Series and horizon for the sky view (C5). Fixture mode only for now (Kaitlin, 2026-11-15):
 * the live endpoints aren't merged, so live mode returns null and the screen says so.
 */
export async function loadThinSliceSky(
  source: DataSource,
): Promise<{ series: SeriesResponse; horizon: HorizonProfile } | null> {
  if (source !== 'fixtures') return null
  const [series, horizon] = await Promise.all([
    import('../../../fixtures/series.json'),
    import('../../../fixtures/horizon.json'),
  ])
  return {
    series: series.default as SeriesResponse,
    horizon: horizon.default as HorizonProfile,
  }
}

/** Curated sites for the globe (C7a): fixtures/sites.json, or GET /api/sites in live mode. */
export async function loadSites(source: DataSource): Promise<SitesResponse> {
  if (source === 'fixtures') {
    return (await import('../../../fixtures/sites.json')).default as SitesResponse
  }
  return getSites()
}
