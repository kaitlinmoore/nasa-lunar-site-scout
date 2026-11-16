// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// API error classification (4.4; typed from contract 0.6.0 in Phase 2 step 3.4). No build-time
// values here, so it can be unit-tested in Node.
//
// The error bodies are contract models (lss/contract/models.py). A 422 from /api/metrics,
// /api/series or /api/horizon is `UnprocessableError` = NotServedError | InvalidRequestError, and
// from /api/compare `CompareUnprocessableError` = CompareNotServedError | InvalidRequestError; the
// contract says to tell them apart by `detail`: an object vs a list. A 503 is `UnavailableError`.
// Only that discrimination (and a check that the object has its `reason`) is done at runtime; the
// rest is the generated types. Anything else is reported as a plain HTTP error.
import type { components } from './schema'

type S = components['schemas']

export type ServedOption = S['ServedScenario']

export type ApiProblem =
  /** 422: a valid scenario with no precomputed result; `detail.served` lists what is served. */
  | { kind: 'not-served'; detail: S['NotServedDetail'] }
  /** 422 from /api/compare: none of the compared scenarios is served. */
  | { kind: 'compare-not-served'; detail: S['CompareNotServedDetail'] }
  /** 422: FastAPI rejected a malformed request (a bug in this app, not the user's input). */
  | { kind: 'invalid-request'; issues: S['ValidationIssue'][] }
  /** 503: no usable precomputed results are installed. `detail.technical` is for developers. */
  | { kind: 'unavailable'; detail: S['UnavailableDetail'] }
  /** Any other non-OK answer. */
  | { kind: 'http'; status: number; text: string }
  /** No answer at all. */
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
      return `no result for this scenario (422): ${p.detail.reason}`
    case 'compare-not-served':
      return `none of the compared scenarios has a result (422): ${p.detail.reason}`
    case 'invalid-request':
      return `malformed request (422): ${p.issues.map((i) => `${i.loc.join('.')}: ${i.msg}`).join('; ')}`
    case 'unavailable':
      return `results unavailable (503): ${p.detail.reason}`
    case 'http':
      return `HTTP ${p.status}${p.text ? `: ${p.text}` : ''}`
    case 'network':
      return `no answer from the API (${p.message})`
  }
}

function isRecord(x: unknown): x is Record<string, unknown> {
  return typeof x === 'object' && x !== null && !Array.isArray(x)
}

/** Classify a non-OK response from the route, its status and body. */
export function classifyError(path: string, status: number, bodyText: string): ApiProblem {
  let body: unknown = null
  try {
    body = JSON.parse(bodyText)
  } catch {
    // not JSON: a plain HTTP error
  }
  const detail = isRecord(body) ? body.detail : undefined
  if (status === 422 && Array.isArray(detail)) {
    return { kind: 'invalid-request', issues: (body as S['InvalidRequestError']).detail }
  }
  if (status === 422 && isRecord(detail) && typeof detail.reason === 'string') {
    if (path.startsWith('/api/compare')) {
      return { kind: 'compare-not-served', detail: (body as S['CompareNotServedError']).detail }
    }
    return { kind: 'not-served', detail: (body as S['NotServedError']).detail }
  }
  if (status === 503 && isRecord(detail) && typeof detail.reason === 'string') {
    return { kind: 'unavailable', detail: (body as S['UnavailableError']).detail }
  }
  return { kind: 'http', status, text: bodyText.trim().slice(0, 300) }
}
