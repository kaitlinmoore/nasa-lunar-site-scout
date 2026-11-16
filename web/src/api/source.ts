// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// Data source switch: live API or the committed fixtures/*.json (see web/README.md).
// Both paths return the same generated contract types, so the screen can't tell them apart.
import { scenarioId } from '../scenario'
import { type ComparisonResult, mapCompareResponse } from './compare'
import { staticCompare, staticMetrics, staticSites, staticSky, withStaticFallback } from './staticFallback'
import {
  ApiError,
  type CompareResponse,
  getSites,
  type HorizonProfile,
  type MetricsResponse,
  type NLRequest,
  postCompare,
  postHorizon,
  postMetrics,
  postNl,
  postSeries,
  type Scenario,
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

/** The thin-slice scenario itself (from the fixture), e.g. as form defaults. Never calls the API. */
export async function thinSliceScenario(): Promise<Scenario> {
  return (await thinSliceFixture()).scenario
}

/**
 * Metrics for the thin-slice scenario.
 * Fixture mode: the fixture response itself.
 * Live mode: POST /api/metrics with the fixture's scenario.
 */
export async function loadThinSliceMetrics(source: DataSource): Promise<MetricsResponse> {
  const fixture = await thinSliceFixture()
  if (source === 'fixtures') return fixture
  return withStaticFallback(
    () => postMetrics(fixture.scenario),
    () => staticMetrics(fixture.scenario),
  )
}

/**
 * Series and horizon for the sky view (C5). Fixture mode only for now (Kaitlin, 2026-11-15):
 * the live endpoints aren't merged, so live mode returns null and the screen says so.
 */
export async function loadThinSliceSky(
  source: DataSource,
): Promise<{ series: SeriesResponse; horizon: HorizonProfile }> {
  if (source !== 'fixtures') {
    // Live (Phase 2 step 3.2): the thin-slice series and the horizon for its location + height.
    const { scenario } = await thinSliceFixture()
    return withStaticFallback(
      async () => {
        const [series, horizon] = await Promise.all([
          postSeries(scenario),
          postHorizon(scenario.location, scenario.unit_height_m),
        ])
        return { series, horizon }
      },
      () => staticSky(scenario),
    )
  }
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
  // Dev-only readiness test (Phase 2 step 3.5): `?source=fixtures&testSites=crowded` loads a
  // made-up list of 31 sites (27 crowded near the south pole) from web/test-data. Production
  // builds drop this branch (import.meta.env.DEV is false there).
  if (
    import.meta.env.DEV &&
    source === 'fixtures' &&
    new URLSearchParams(window.location.search).get('testSites') === 'crowded'
  ) {
    return (await import('../../test-data/sites-crowded.json')).default as SitesResponse
  }
  if (source === 'fixtures') {
    return (await import('../../../fixtures/sites.json')).default as SitesResponse
  }
  return withStaticFallback(getSites, staticSites)
}

export type { ComparisonResult } from './compare'

const FIXTURE_NO_RESULT = 'No result in fixture mode: only the scenarios in fixtures/compare.json have one.'

/**
 * Live calls fall back to the static copy (/static-api/) when the API gives no usable answer
 * (staticFallback.ts); the page then shows a notice.
 *
 * Compare (C6; live in Phase 2 step 3.3): metrics for each requested scenario, in request order.
 * - Fixtures: fixtures/compare.json answers a scenario only if it is exactly one of its items.
 * - Live: POST /api/compare. `items` holds the served scenarios in request order and `not_served`
 *   the others by request index (contract 0.6.0). Each item is checked to be exactly the scenario
 *   of its column; any mismatch is an error, never a result under the wrong column. A 422
 *   "none served" becomes a result with every column's reason.
 */
export async function loadCompare(source: DataSource, scenarios: Scenario[]): Promise<ComparisonResult> {
  if (source === 'fixtures') {
    const response = (await import('../../../fixtures/compare.json')).default as CompareResponse
    const byId = new Map(response.items.map((item) => [scenarioId(item.scenario), item]))
    const items = scenarios.map((s) => byId.get(scenarioId(s)) ?? null)
    return {
      meta: response,
      items,
      reasons: items.map((item) => (item ? null : FIXTURE_NO_RESULT)),
      noneReason: null,
    }
  }

  return withStaticFallback(
    () => liveCompare(scenarios),
    () => staticCompare(scenarios),
  )
}

async function liveCompare(scenarios: Scenario[]): Promise<ComparisonResult> {
  let response: CompareResponse
  try {
    response = await postCompare(scenarios)
  } catch (e) {
    if (e instanceof ApiError && e.problem.kind === 'compare-not-served') {
      const { detail } = e.problem
      const reasons = scenarios.map(
        (_, i) => detail.not_served.find((n) => n.index === i)?.reason ?? detail.reason,
      )
      return { meta: null, items: scenarios.map(() => null), reasons, noneReason: detail.reason }
    }
    throw e
  }
  return mapCompareResponse(scenarios, response)
}

/** Which committed example answer fixture mode shows (C api's fixtures/nl_*.json). */
export type NlExample = 'answer' | 'unsupported' | 'clarification'

/**
 * Ask a question (C7b). Live: POST /api/nl. There's no saved copy of live answers, so no static
 * fallback. Fixtures: the question isn't sent anywhere; the chosen example answer is returned.
 */
export async function askNl(source: DataSource, request: NLRequest, example: NlExample): Promise<unknown> {
  if (source !== 'fixtures') return postNl(request)
  const mod =
    example === 'answer'
      ? await import('../../../fixtures/nl_answer.json')
      : example === 'unsupported'
        ? await import('../../../fixtures/nl_unsupported.json')
        : await import('../../../fixtures/nl_clarification.json')
  return mod.default
}
