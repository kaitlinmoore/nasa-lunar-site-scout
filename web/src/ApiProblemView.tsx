// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// How a failed API request is shown (4.4). Each kind says what happened in plain words; no values
// are shown for a failed request. "Not served" lists the scenarios this version does serve.
import { ApiError } from './api/client'
import { formatExactRange, formatScenarioSummary, SCENARIO_FIELD_LABELS } from './format'

function NotServedList({ served }: { served: ApiError['problem'] & { kind: 'not-served' } }) {
  if (served.served.length === 0) return null
  return (
    <>
      <div>This version serves:</div>
      <ul>
        {served.served.map((s) => (
          <li key={s.scenario_key}>
            <span className="value">{formatScenarioSummary(s.scenario)}</span>
            <div className="definition value">
              {formatExactRange(s.scenario.window_start, s.scenario.window_end)}
            </div>
            {s.differs_in.length > 0 && (
              <span className="muted">
                {' '}
                (your request differs in: {s.differs_in.map((f) => SCENARIO_FIELD_LABELS[f] ?? f).join(', ')})
              </span>
            )}
          </li>
        ))}
      </ul>
    </>
  )
}

/** A failed load: the API's own reason when it gave one, else the error text. */
export default function ApiProblemView({ what, error }: { what: string; error: unknown }) {
  if (!(error instanceof ApiError)) {
    return (
      <div className="banner error" role="alert">
        <strong>Could not load {what}.</strong> No values are shown.
        <div className="mono">{error instanceof Error ? error.message : String(error)}</div>
      </div>
    )
  }
  const p = error.problem
  switch (p.kind) {
    case 'not-served':
      return (
        <div className="banner notice" role="status">
          <strong>No result for this scenario yet.</strong> {p.reason}
          <NotServedList served={p} />
        </div>
      )
    case 'unavailable':
      return (
        <div className="banner error" role="alert">
          <strong>Results aren't available right now.</strong> No values are shown.
          <div className="mono">{p.reason}</div>
        </div>
      )
    case 'invalid-request':
      return (
        <div className="banner error" role="alert">
          <strong>The API rejected the request for {what} as malformed.</strong> That's a bug in this app, not
          something you entered. No values are shown.
          <ul className="mono">
            {p.issues.map((i, k) => (
              <li key={k}>
                {i.where}: {i.message}
              </li>
            ))}
          </ul>
        </div>
      )
    case 'network':
      return (
        <div className="banner error" role="alert">
          <strong>Couldn't reach the API for {what}.</strong> No values are shown.
          <div className="mono">{p.message}</div>
        </div>
      )
    case 'http':
      return (
        <div className="banner error" role="alert">
          <strong>Could not load {what}</strong> (the API answered HTTP {p.status}). No values are shown.
          {p.text && <div className="mono">{p.text}</div>}
        </div>
      )
  }
}
