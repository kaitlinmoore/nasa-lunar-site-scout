// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// API error classification (4.4). No build-time values here, so it can be unit-tested in Node.
import type { components } from './schema'

type Scenario = components['schemas']['Scenario']

/** One scenario the API serves, as listed in a "not served" 422 (lss/api/app.py `served_for`). */
export type ServedOption = { scenario: Scenario; scenario_key: string; differs_in: string[] }

/**
 * Why a request failed, by kind. The API's error bodies aren't in the contract's OpenAPI yet
 * (only descriptions), so these shapes are read from lss/api/app.py and checked at runtime.
 * - not-served: 422 with `detail: {reason, scenario_key, served}`: a valid scenario this
 *   version has no precomputed result for.
 * - invalid-request: 422 with `detail: [{loc, msg, type}]`: FastAPI rejected a malformed
 *   request (a bug in this app, not the user's input).
 * - unavailable: 503 with `detail: {reason}`: no usable precomputed results are installed.
 * - http: any other non-OK answer. network: no answer at all.
 */
export type ApiProblem =
  | { kind: 'not-served'; reason: string; scenarioKey: string | null; served: ServedOption[] }
  | { kind: 'invalid-request'; issues: { where: string; message: string }[] }
  | { kind: 'unavailable'; reason: string }
  | { kind: 'http'; status: number; text: string }
  | { kind: 'network'; message: string }

export class ApiError extends Error {
  readonly path: string
  readonly problem: ApiProblem
  constructor(path: string, problem: ApiProblem) {
    super(`${path}: ${describeProblem(problem)}`)
    this.name = 'ApiError'
    this.path = path
    this.problem = problem
  }
}

function describeProblem(p: ApiProblem): string {
  switch (p.kind) {
    case 'not-served':
      return `no result for this scenario (422): ${p.reason}`
    case 'invalid-request':
      return `malformed request (422): ${p.issues.map((i) => `${i.where}: ${i.message}`).join('; ')}`
    case 'unavailable':
      return `results unavailable (503): ${p.reason}`
    case 'http':
      return `HTTP ${p.status}${p.text ? `: ${p.text}` : ''}`
    case 'network':
      return `no answer from the API (${p.message})`
  }
}

function isRecord(x: unknown): x is Record<string, unknown> {
  return typeof x === 'object' && x !== null && !Array.isArray(x)
}

/** Classify a non-OK response from its status and body. */
export function classifyError(status: number, bodyText: string): ApiProblem {
  let body: unknown = null
  try {
    body = JSON.parse(bodyText)
  } catch {
    // not JSON: falls through to a plain HTTP error
  }
  const detail = isRecord(body) ? body.detail : undefined
  if (status === 422 && Array.isArray(detail)) {
    return {
      kind: 'invalid-request',
      issues: detail.map((d) => {
        const r = isRecord(d) ? d : {}
        const loc = Array.isArray(r.loc) ? r.loc.join('.') : 'request'
        return { where: loc, message: typeof r.msg === 'string' ? r.msg : JSON.stringify(d) }
      }),
    }
  }
  if (status === 422 && isRecord(detail) && typeof detail.reason === 'string') {
    const served = Array.isArray(detail.served)
      ? detail.served.filter(
          (x): x is ServedOption =>
            isRecord(x) &&
            isRecord(x.scenario) &&
            typeof x.scenario_key === 'string' &&
            Array.isArray(x.differs_in),
        )
      : []
    return {
      kind: 'not-served',
      reason: detail.reason,
      scenarioKey: typeof detail.scenario_key === 'string' ? detail.scenario_key : null,
      served,
    }
  }
  if (status === 503 && isRecord(detail) && typeof detail.reason === 'string') {
    return { kind: 'unavailable', reason: detail.reason }
  }
  return { kind: 'http', status, text: bodyText.trim().slice(0, 300) }
}
