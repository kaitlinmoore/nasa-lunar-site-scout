// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// Live comparison mapping, and the keyed mapping for comparisons with filters, a rank
// or a site template (NL answers). Pure, no build-time values, so it can be unit-tested.
import { scenarioId } from '../scenario'
import type { components } from './schema'

type S = components['schemas']
type Scenario = S['Scenario']
type MetricsResponse = S['MetricsResponse']
type CompareResponse = S['CompareResponse']

/** A comparison's answer, one entry per requested scenario (request order). */
export type ComparisonResult = {
  /** Version / placeholder flag / note of the answer as a whole; null if no scenario was served. */
  meta: { contract_version: string; _placeholder: boolean; _note?: string | null } | null
  /** Metrics per scenario, or null where there is none. */
  items: (MetricsResponse | null)[]
  /** Why a scenario has no result (null where it has one). */
  reasons: (string | null)[]
  /** When none of the scenarios has a result: the overall reason. */
  noneReason: string | null
}

/** Place a live CompareResponse's items under their request columns, checking every match. */
export function mapCompareResponse(scenarios: Scenario[], response: CompareResponse): ComparisonResult {
  const notServed = new Map((response.not_served ?? []).map((n) => [n.index, n.reason]))
  for (const index of notServed.keys()) {
    if (!(index >= 0 && index < scenarios.length)) {
      throw new Error(
        `/api/compare: not_served index ${index} is outside the ${scenarios.length} requested scenarios`,
      )
    }
  }
  const servedColumns = scenarios.map((_, i) => i).filter((i) => !notServed.has(i))
  if (response.items.length !== servedColumns.length) {
    throw new Error(
      `/api/compare: ${response.items.length} results for ${servedColumns.length} served scenarios; not shown`,
    )
  }
  const items: (MetricsResponse | null)[] = scenarios.map(() => null)
  response.items.forEach((item, k) => {
    const column = servedColumns[k]
    if (scenarioId(item.scenario) !== scenarioId(scenarios[column])) {
      throw new Error(`/api/compare: result ${k + 1} is not the scenario of column ${column + 1}; not shown`)
    }
    items[column] = item
  })
  return {
    meta: response,
    items,
    reasons: scenarios.map((_, i) => notServed.get(i) ?? null),
    noneReason: null,
  }
}

type CompareRank = S['CompareRank']
type MetricFilter = S['MetricFilter']
type EvaluatedValue = S['EvaluatedValue']

/** What happened to one compared scenario. */
export type ColumnOutcome =
  /** It has a result; `rank` is its place in the ranking (1-based), null when nothing was ranked. */
  | { kind: 'result'; rank: number | null; tiedWith: string[] }
  | { kind: 'not_served'; reason: string }
  /** Removed by a filter (`failed`), or with no value for a filter or the rank (`notComputed`). */
  | { kind: 'filtered_out'; failed: string[]; notComputed: string[] }
  /** Passed the filters but was cut by the rank's limit. */
  | { kind: 'beyond_limit'; limit: number }

export type ComparisonColumn = {
  scenario: Scenario
  /** The server's scenario key for this column (`compared_keys`, contract 0.13.0). */
  key: string
  result: MetricsResponse | null
  outcome: ColumnOutcome
  /** The values the filters and the rank used for this scenario, as sent. */
  evaluated: EvaluatedValue[]
}

export type KeyedComparison = {
  meta: { contract_version: string; _placeholder: boolean; _note?: string | null }
  /** In the compared order, or in rank order (then cut, then filtered out, then not precomputed) when ranked. */
  columns: ComparisonColumn[]
  /** Metric labels the filters and the rank used, in the order they were given. */
  evaluatedMetrics: string[]
}

/** The label the API uses for a filter or rank metric (SunElevationBand.label(); `:g` formatting). */
export function compareMetricLabel(metric: MetricFilter['metric']): string {
  if (typeof metric === 'string') return metric
  const g = (x: number) => String(Number(x.toPrecision(6)))
  return `sun_elevation_band_fraction[${g(metric.min_deg)},${g(metric.max_deg)}]`
}

/**
 * A comparison answered with filters, a rank or an `across` template (contract 0.10.0+), one column
 * per compared scenario (`response.compared`), keyed by `response.compared_keys` (same order; contract
 * 0.13.0). Items are matched to columns by scenario key; every index and key in the response must
 * fit, or this throws and nothing is shown.
 */
export function mapComparison(
  response: CompareResponse,
  query: { filters: MetricFilter[]; rank: CompareRank | null },
): KeyedComparison {
  const where = '/api/compare'
  const compared = response.compared ?? []
  const keys = response.compared_keys ?? []
  if (compared.length === 0 || keys.length !== compared.length) {
    throw new Error(`${where}: the answer doesn't list the compared scenarios with their keys; not shown`)
  }
  if (new Set(keys).size !== keys.length) throw new Error(`${where}: a scenario is compared twice; not shown`)
  const column = new Map(keys.map((k, i) => [k, i]))
  const checkIndex = (index: number, key: string, list: string) => {
    if (!(index >= 0 && index < compared.length) || keys[index] !== key) {
      throw new Error(`${where}: ${list} entry ${index} doesn't match the compared scenario there; not shown`)
    }
  }
  const outcomes: (ColumnOutcome | null)[] = compared.map(() => null)
  const results: (MetricsResponse | null)[] = compared.map(() => null)
  for (const n of response.not_served ?? []) {
    checkIndex(n.index, n.scenario_key, 'not_served')
    outcomes[n.index] = { kind: 'not_served', reason: n.reason }
  }
  for (const f of response.filtered_out ?? []) {
    checkIndex(f.index, f.scenario_key, 'filtered_out')
    if (outcomes[f.index]) throw new Error(`${where}: scenario ${f.index + 1} is listed twice; not shown`)
    outcomes[f.index] = { kind: 'filtered_out', failed: f.failed ?? [], notComputed: f.not_computed ?? [] }
  }
  const ties = response.rank_ties ?? []
  const rankOrder: number[] = []
  for (const item of response.items) {
    const i = column.get(item.scenario_key)
    if (i === undefined) throw new Error(`${where}: a result is for no compared scenario; not shown`)
    if (scenarioId(item.scenario) !== scenarioId(compared[i])) {
      throw new Error(`${where}: result ${item.scenario_key} is not the scenario it claims; not shown`)
    }
    if (outcomes[i])
      throw new Error(`${where}: scenario ${i + 1} has a result and is also listed as without one`)
    rankOrder.push(i)
    results[i] = item
    const group = ties.find((g) => g.includes(item.scenario_key)) ?? []
    outcomes[i] = {
      kind: 'result',
      rank: query.rank ? rankOrder.length : null,
      tiedWith: group.filter((k) => k !== item.scenario_key),
    }
  }
  // Whatever is left passed the filters and was cut by the rank's limit; the count must agree.
  const cut = outcomes.flatMap((o, i) => (o ? [] : [i]))
  const beyond = response.beyond_limit ?? 0
  if (cut.length !== beyond || (beyond > 0 && query.rank?.limit == null)) {
    throw new Error(
      `${where}: ${cut.length} scenarios are unaccounted for, but ${beyond} were cut by a limit; not shown`,
    )
  }
  for (const i of cut) outcomes[i] = { kind: 'beyond_limit', limit: query.rank?.limit ?? 0 }
  for (const e of response.evaluated ?? []) {
    if (!column.has(e.scenario_key))
      throw new Error(`${where}: a value used by a filter is for no compared scenario`)
  }

  const order = compared.map((_, i) => i)
  if (query.rank) {
    const kindRank = { result: 0, beyond_limit: 1, filtered_out: 2, not_served: 3 } as const
    const pos = (i: number) => {
      const r = rankOrder.indexOf(i)
      return r >= 0 ? r : Infinity
    }
    order.sort(
      (a, b) =>
        kindRank[(outcomes[a] as ColumnOutcome).kind] - kindRank[(outcomes[b] as ColumnOutcome).kind] ||
        pos(a) - pos(b) ||
        a - b,
    )
  }
  const metrics = [
    ...query.filters.map((f) => compareMetricLabel(f.metric)),
    ...(query.rank ? [compareMetricLabel(query.rank.metric)] : []),
  ]
  return {
    meta: response,
    columns: order.map((i) => ({
      scenario: compared[i],
      key: keys[i],
      result: results[i],
      outcome: outcomes[i] as ColumnOutcome,
      evaluated: (response.evaluated ?? []).filter((e) => e.scenario_key === keys[i]),
    })),
    evaluatedMetrics: [...new Set(metrics)],
  }
}
