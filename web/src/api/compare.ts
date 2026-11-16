// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// Live comparison mapping (Phase 2 step 3.3). Pure, no build-time values, so it can be unit-tested.
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
