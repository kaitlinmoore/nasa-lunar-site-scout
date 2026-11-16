// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// Data source switch: live API or the committed fixtures/*.json (see web/README.md).
// Both paths return the same generated contract types, so the screen can't tell them apart.
import { scenarioId } from '../scenario'
import { type ComparisonResult, mapCompareResponse } from './compare'
import {
  staticCompare,
  staticMetrics,
  staticScenarios,
  staticSeries,
  staticSites,
  staticSky,
  withStaticFallback,
} from './staticFallback'
import {
  ApiError,
  type CompareResponse,
  getScenarios,
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
  type ScenarioEntry,
  type ScenariosResponse,
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
 * The example response in fixtures/metrics.json (C api's fixture). Fixture mode's only scenario;
 * its scenario is also the saved-scenario form's default. Loaded on demand (a separate chunk).
 */
async function exampleFixture(): Promise<MetricsResponse> {
  return (await import('../../../fixtures/metrics.json')).default as MetricsResponse
}

/** The example scenario itself (from the fixture), e.g. as form defaults. Never calls the API. */
export async function thinSliceScenario(): Promise<Scenario> {
  return (await exampleFixture()).scenario
}

const FIXTURE_ONLY_EXAMPLE = 'Fixture mode has only the example scenario in fixtures/metrics.json.'

/**
 * Every precomputed scenario with its curated site (G2; GET /api/scenarios, contract 0.11.0), with
 * the static copy as fallback. Fixture mode: the example scenario, under the curated site at its
 * location. Fetched once per page load and shared by every site page.
 */
const scenarioLists = new Map<DataSource, Promise<ScenariosResponse>>()
export function loadScenarios(source: DataSource): Promise<ScenariosResponse> {
  let list = scenarioLists.get(source)
  if (!list) {
    list = source === 'fixtures' ? fixtureScenarios() : withStaticFallback(getScenarios, staticScenarios)
    // A failed load isn't cached, so the next site page tries again.
    list.catch(() => scenarioLists.delete(source))
    scenarioLists.set(source, list)
  }
  return list
}

async function fixtureScenarios(): Promise<ScenariosResponse> {
  const [example, sites] = await Promise.all([exampleFixture(), loadSites('fixtures')])
  const { location } = example.scenario
  const site = sites.sites.find((s) => s.location.lat === location.lat && s.location.lon === location.lon)
  return {
    contract_version: example.contract_version,
    _placeholder: true,
    _note: example._note,
    scenarios: [
      {
        site_id: site?.id ?? null,
        scenario_key: example.scenario_key,
        scenario: example.scenario,
        has_horizon: true,
      },
    ],
  }
}

/** Metrics for one precomputed scenario: POST /api/metrics (static copy as fallback), or the fixture. */
export async function loadMetrics(source: DataSource, entry: ScenarioEntry): Promise<MetricsResponse> {
  if (source === 'fixtures') {
    const example = await exampleFixture()
    if (scenarioId(example.scenario) !== scenarioId(entry.scenario)) throw new Error(FIXTURE_ONLY_EXAMPLE)
    return example
  }
  return withStaticFallback(
    () => postMetrics(entry.scenario),
    () => staticMetrics(entry.scenario),
  )
}

/**
 * Series and horizon for the sky view (C5; live in Phase 2 step 3.2) of one precomputed scenario.
 * `horizon` is null when the scenario's location and height have no horizon profile.
 */
export async function loadSky(
  source: DataSource,
  entry: ScenarioEntry,
): Promise<{ series: SeriesResponse; horizon: HorizonProfile | null }> {
  if (source === 'fixtures') {
    const example = await exampleFixture()
    if (scenarioId(example.scenario) !== scenarioId(entry.scenario)) throw new Error(FIXTURE_ONLY_EXAMPLE)
    const [series, horizon] = await Promise.all([
      import('../../../fixtures/series.json'),
      import('../../../fixtures/horizon.json'),
    ])
    return { series: series.default as SeriesResponse, horizon: horizon.default as HorizonProfile }
  }
  const { scenario } = entry
  if (!entry.has_horizon) {
    const series = await withStaticFallback(
      () => postSeries(scenario),
      () => staticSeries(scenario),
    )
    return { series, horizon: null }
  }
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
