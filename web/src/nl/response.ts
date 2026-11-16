// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// Answers from POST /api/nl (C7b UI, contract 0.8.0). Pure, so it can be unit-tested in Node.
//
// A 200 is one of three contract models: NLAnswer (has `structured_query`), NLUnsupported (has
// `unsupported`) or NLClarification (has `question`). An answer's `result` is "the operation's
// response body, as the endpoint returns it"; it is read here as that endpoint's own response type,
// after a check that the fields this page shows are there, so the box can reuse the site screen's
// views. Nothing here computes a value.
import type { components } from '../api/schema'

type S = components['schemas']

export type NLAnswer = S['NLAnswer']
export type NLUnsupported = S['NLUnsupported']
export type NLClarification = S['NLClarification']

export type NlOutcome =
  | { kind: 'answer'; body: NLAnswer }
  | { kind: 'unsupported'; body: NLUnsupported }
  | { kind: 'clarification'; body: NLClarification }

function isRecord(x: unknown): x is Record<string, unknown> {
  return typeof x === 'object' && x !== null && !Array.isArray(x)
}

/** Tell the three kinds of 200 apart; throws for anything else (then nothing is shown). */
export function classifyNl(body: unknown): NlOutcome {
  if (!isRecord(body)) throw new Error('/api/nl: the answer is not a JSON object; not shown')
  if (isRecord(body.structured_query) && typeof body.interpretation === 'string') {
    return { kind: 'answer', body: body as NLAnswer }
  }
  if (isRecord(body.unsupported) && typeof body.unsupported.reason === 'string') {
    return { kind: 'unsupported', body: body as NLUnsupported }
  }
  if (typeof body.question === 'string' && typeof body.interpretation === 'string') {
    return { kind: 'clarification', body: body as NLClarification }
  }
  throw new Error("/api/nl: an answer of a kind this page doesn't know; not shown")
}

export type NlResult =
  /** Nothing was run, or the query wasn't served (then `limitations` says why). */
  | { op: 'none' }
  | { op: 'metrics'; result: S['MetricsResponse'] }
  | { op: 'compare'; scenarios: S['Scenario'][]; result: S['CompareResponse'] }
  | { op: 'series'; result: S['SeriesResponse'] }
  | { op: 'horizon'; result: S['HorizonProfile'] }
  | { op: 'sites'; result: S['SitesResponse'] }
  | { op: 'locate'; result: S['LocateResponse'] }
  | { op: 'terrain'; result: S['TerrainResponse'] }
  | { op: 'site_summary'; result: S['SiteSummaryResponse'] }
  /** A result this page can't show (an operation without a view, or fields missing). */
  | { op: 'unreadable'; operation: string; why: string }

/** The fields each operation's view reads (the endpoint's required fields that are shown). */
const REQUIRED: Record<string, string[]> = {
  metrics: ['scenario', 'scenario_key', 'power', 'comms'],
  compare: ['items'],
  series: ['scenario', 'scenario_key', 'time', 'sun', 'earth'],
  horizon: ['location', 'unit_height_m', 'azimuth_deg', 'elevation_deg'],
  sites: ['sites'],
  locate: ['location', 'terrain_stack', 'fidelity'],
  terrain: ['location', 'radius_m'],
  site_summary: ['location', 'radius_m'],
}

/** An answer's result as its operation's response type, or why it can't be shown. */
export function readResult(answer: NLAnswer): NlResult {
  const { operation, params } = answer.structured_query
  const result: unknown = answer.result
  if (result == null) return { op: 'none' }
  const unreadable = (why: string): NlResult => ({ op: 'unreadable', operation, why })
  const required = REQUIRED[operation]
  if (!required) return unreadable(`this page has no view for the "${operation}" operation yet`)
  if (!isRecord(result)) return unreadable('the result is not a JSON object')
  const missing = required.filter((k) => !(k in result))
  if (missing.length > 0) return unreadable(`the result has no ${missing.join(', ')}`)
  switch (operation) {
    case 'metrics':
      return { op: 'metrics', result: result as S['MetricsResponse'] }
    case 'compare': {
      const scenarios = isRecord(params) && Array.isArray(params.scenarios) ? params.scenarios : null
      if (!scenarios) return unreadable('the query has no list of scenarios to put the results under')
      return {
        op: 'compare',
        scenarios: scenarios as S['Scenario'][],
        result: result as S['CompareResponse'],
      }
    }
    case 'series':
      return { op: 'series', result: result as S['SeriesResponse'] }
    case 'horizon':
      return { op: 'horizon', result: result as S['HorizonProfile'] }
    case 'sites':
      return { op: 'sites', result: result as S['SitesResponse'] }
    case 'locate':
      return { op: 'locate', result: result as S['LocateResponse'] }
    case 'terrain':
      return { op: 'terrain', result: result as S['TerrainResponse'] }
    case 'site_summary':
      return { op: 'site_summary', result: result as S['SiteSummaryResponse'] }
  }
  return unreadable(`this page has no view for the "${operation}" operation yet`)
}

/** The contract versions in an NL answer: the answer's own, and its result's when there is one. */
export function nlContractVersions(outcome: NlOutcome): string[] {
  const versions = [outcome.body.contract_version]
  if (outcome.kind === 'answer' && isRecord(outcome.body.result)) {
    const v = outcome.body.result.contract_version
    if (typeof v === 'string') versions.push(v)
  }
  return [...new Set(versions.filter((v): v is string => typeof v === 'string'))]
}

/** Whether the answer, or its result, is placeholder data (fixtures). */
export function nlIsPlaceholder(outcome: NlOutcome): boolean {
  if (outcome.body._placeholder) return true
  return (
    outcome.kind === 'answer' && isRecord(outcome.body.result) && outcome.body.result._placeholder === true
  )
}
