// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// The question box (C7b UI, Phase 2 step 3.7 / G3), below the dashboard on the site screen.
//
// A question goes to POST /api/nl with the selected site (and its computed scenario, if it has one).
// The language model only turns the question into one of the API's queries; the numbers in an answer
// are the API's own results, shown with the site screen's views. Every answer echoes how the question
// was understood, the values that were assumed, and what couldn't be answered and why.
import { type FormEvent, useEffect, useRef, useState } from 'react'
import {
  ApiError,
  type NLRequest,
  type Scenario,
  type Site,
  type StaticNLEntry,
  WEB_CONTRACT_VERSION,
} from '../api/client'
import { askNl, askNlExample, type DataSource, loadNlExamples, type NlExample } from '../api/source'
import ApiProblemView from '../ApiProblemView'
import { formatExactRange, formatHeight, formatLatLon, formatScenarioSummary } from '../format'
import { displayName, placeLabel, useSiteNames } from '../siteNames'
import { routeHref } from '../route'
import CompareAnswer from './CompareAnswer'
import { Value } from '../metrics'
import SiteScreen from '../SiteScreen'
import {
  classifyNl,
  type NlOutcome,
  type NLAnswer,
  nlContractVersions,
  nlIsPlaceholder,
  type NlResult,
  readResult,
} from './response'
import { SiteSummaryView, TerrainView } from './TerrainViews'
import Section from '../Section'
import { DashboardScenario } from './dashboardScenario'

const MAX_CHARS = __NL_MAX_TEXT_CHARS__

const EXAMPLES: { value: NlExample; label: string }[] = [
  { value: 'answer', label: 'An answer (metrics)' },
  { value: 'unsupported', label: "Can't answer" },
  { value: 'clarification', label: 'Needs more information' },
]

type State =
  | { kind: 'idle' }
  | { kind: 'asking'; question: string; about: string | null }
  | { kind: 'done'; question: string; about: string | null; outcome: NlOutcome }
  | { kind: 'error'; question: string; about: string | null; error: unknown }

function PlaceholderNote({ note }: { note?: string | null }) {
  return (
    <div className="banner placeholder" role="note">
      <strong>Placeholder data, not a computed result.</strong>
      {note && <div className="muted">{note}</div>}
    </div>
  )
}

function Unreadable({ why }: { why: string }) {
  return (
    <div className="banner error" role="alert">
      <strong>This page can't show the result.</strong> {why[0].toUpperCase() + why.slice(1)}. No values are
      shown.
    </div>
  )
}

/** The answer's result, in the same views as the rest of the site. */
function ResultView({ result }: { result: NlResult }) {
  const names = useSiteNames()
  switch (result.op) {
    case 'none':
      return null
    case 'unreadable':
      return <Unreadable why={result.why} />
    case 'metrics':
      return (
        <div className="nl-result">
          <SiteScreen data={result.result} />
        </div>
      )
    case 'compare':
      return <CompareAnswer comparison={result.comparison} filters={result.filters} rank={result.rank} />
    case 'series': {
      const r = result.result
      return (
        <div className="nl-result">
          <dl>
            <dt>Sun and Earth positions</dt>
            <dd>
              <span className="value">{formatScenarioSummary(r.scenario)}</span>
              <div className="definition value">
                {formatExactRange(r.scenario.window_start, r.scenario.window_end)} · {r.time.length} samples
              </div>
            </dd>
          </dl>
          <p className="muted">This box doesn't plot a series on its own yet.</p>
        </div>
      )
    }
    case 'horizon': {
      const r = result.result
      return (
        <div className="nl-result">
          <dl>
            <dt>Terrain horizon</dt>
            <dd>
              <span className="value">
                {placeLabel(names, r.location)} · {formatHeight(r.unit_height_m)}
              </span>
              <div className="definition value">{r.azimuth_deg.length} azimuth samples</div>
            </dd>
            {r.fidelity && (
              <>
                <dt>Fidelity</dt>
                <dd>{r.fidelity.summary}</dd>
              </>
            )}
          </dl>
          <p className="muted">This box doesn't plot a horizon on its own yet.</p>
        </div>
      )
    }
    case 'sites':
      return (
        <div className="nl-result">
          {result.result.sites.length === 0 ? (
            <p className="muted">No sites matched.</p>
          ) : (
            <ul>
              {result.result.sites.map((s) => (
                <li key={s.id}>
                  <a href={routeHref({ view: 'site', siteId: s.id })}>{names.byId(s.id) ?? displayName(s)}</a>{' '}
                  <span className="muted value">{formatLatLon(s.location.lat, s.location.lon)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )
    case 'terrain':
      return (
        <div className="nl-result">
          <TerrainView terrain={result.result} />
        </div>
      )
    case 'site_summary':
      return (
        <div className="nl-result">
          <SiteSummaryView summary={result.result} />
        </div>
      )
    case 'locate': {
      const r = result.result
      return (
        <div className="nl-result">
          <dl>
            <dt>Location</dt>
            <dd className="value">{formatLatLon(r.location.lat, r.location.lon)}</dd>
            <dt>Fidelity</dt>
            <dd>
              {r.fidelity.summary} <span className="muted">({r.fidelity.tier})</span>
            </dd>
            <dt>Terrain data</dt>
            <dd>
              <ul>
                {r.terrain_stack.map((t) => (
                  <li key={`${t.role}-${t.dataset_id}`}>
                    <span className="value">{t.dataset_id}</span>{' '}
                    <span className="muted">
                      ({t.role === 'near_field' ? 'near field' : 'far field'},{' '}
                      <Value value={t.resolution_m} field="resolution_m" />)
                    </span>
                  </li>
                ))}
              </ul>
            </dd>
          </dl>
        </div>
      )
    }
  }
}

function AnswerView({ body }: { body: NLAnswer }) {
  const result = readResult(body)
  const limitations = body.limitations ?? []
  const assumptions = body.assumptions ?? []
  return (
    <>
      <p>
        <span className="muted">Understood as:</span> {body.interpretation}
      </p>
      {assumptions.length > 0 && (
        <div className="nl-assumptions">
          <span className="muted">Assumed:</span>
          <ul>
            {assumptions.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
        </div>
      )}
      {limitations.length > 0 && (
        <div className="banner notice" role="status">
          <strong>Not answered{result.op === 'none' ? '' : ' in full'}:</strong>
          <ul>
            {limitations.map((l, i) => (
              <li key={i}>
                {l.reason}
                {l.datasets_considered && l.datasets_considered.length > 0 && (
                  <div className="definition">
                    Data considered: <span className="value">{l.datasets_considered.join(', ')}</span>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
      {result.op === 'none' && limitations.length === 0 && <p className="muted">No result was returned.</p>}
      <ResultView result={result} />
      <details className="advanced">
        <summary>Query sent to the API</summary>
        <dl>
          <dt>Operation</dt>
          <dd className="value">{body.structured_query.operation}</dd>
          <dt>Parameters</dt>
          <dd>
            <pre className="mono nl-params">
              {JSON.stringify(body.structured_query.params ?? {}, null, 2)}
            </pre>
          </dd>
        </dl>
      </details>
    </>
  )
}

function OutcomeView({ outcome }: { outcome: NlOutcome }) {
  const mismatched = nlContractVersions(outcome).filter((v) => v !== WEB_CONTRACT_VERSION)
  return (
    <>
      {mismatched.length > 0 && (
        <p className="banner error" role="alert">
          Contract version mismatch: the web was built for {WEB_CONTRACT_VERSION}, the answer is{' '}
          {mismatched.join(', ')}. Values may be misread.
        </p>
      )}
      {nlIsPlaceholder(outcome) && <PlaceholderNote note={outcome.body._note} />}
      {outcome.kind === 'answer' && <AnswerView body={outcome.body} />}
      {outcome.kind === 'unsupported' && (
        <>
          {outcome.body.interpretation && (
            <p>
              <span className="muted">Understood as:</span> {outcome.body.interpretation}
            </p>
          )}
          <div className="banner notice" role="status">
            <strong>Can't answer this:</strong> {outcome.body.unsupported.reason}
            {outcome.body.unsupported.datasets_considered &&
              outcome.body.unsupported.datasets_considered.length > 0 && (
                <div className="definition">
                  Data considered:{' '}
                  <span className="value">{outcome.body.unsupported.datasets_considered.join(', ')}</span>
                </div>
              )}
          </div>
        </>
      )}
      {outcome.kind === 'clarification' && (
        <>
          <p>
            <span className="muted">Understood as:</span> {outcome.body.interpretation}
          </p>
          <div className="banner notice" role="status">
            <strong>More information needed:</strong> {outcome.body.question}
          </div>
        </>
      )}
    </>
  )
}

/** A failed question: the API's own reason where it gave one. */
function ProblemView({ error }: { error: unknown }) {
  if (error instanceof ApiError) {
    const p = error.problem
    if (p.kind === 'rate-limited') {
      return (
        <div className="banner notice" role="status">
          {p.detail.reason} You can ask again in {p.detail.retry_after_s} s.
        </div>
      )
    }
    if (p.kind === 'unavailable') {
      return (
        <div className="banner notice" role="status">
          {p.detail.reason}
          {import.meta.env.DEV && p.detail.technical && <div className="mono">{p.detail.technical}</div>}
        </div>
      )
    }
    if (p.kind === 'network' || (p.kind === 'http' && (p.status === 404 || p.status === 405))) {
      return (
        <div className="banner notice" role="status">
          Live questions aren't available right now: the server{' '}
          {p.kind === 'network' ? "isn't answering" : "doesn't offer them yet"}. There's no saved copy of live
          answers.
        </div>
      )
    }
  }
  return <ApiProblemView what="the answer" error={error} />
}

export default function NlBox({
  site,
  scenario,
  source,
}: {
  site: Site
  /** The site's computed scenario, sent as the selected scenario; null when it has none. */
  scenario: Scenario | null
  source: DataSource
}) {
  const [text, setText] = useState('')
  const [example, setExample] = useState<NlExample>('answer')
  const [state, setState] = useState<State>({ kind: 'idle' })
  const [waitUntil, setWaitUntil] = useState<number | null>(null)
  const latest = useRef(0)

  // After a 429, the Ask button stays off for the API's retry_after_s.
  useEffect(() => {
    if (waitUntil === null) return
    const t = window.setTimeout(() => setWaitUntil(null), Math.max(0, waitUntil - Date.now()))
    return () => window.clearTimeout(t)
  }, [waitUntil])

  // The cached example questions (C8), from the static copy; none in fixture mode.
  const [examples, setExamples] = useState<StaticNLEntry[]>([])
  useEffect(() => {
    let cancelled = false
    loadNlExamples(source).then((list) => !cancelled && setExamples(list))
    return () => {
      cancelled = true
    }
  }, [source])
  const names = useSiteNames()

  const question = text.trim()
  const asking = state.kind === 'asking'

  /** Send one request; `about` names the site an example's recorded request is about, if any. */
  const run = (asked: string, about: string | null, send: () => Promise<unknown>) => {
    const id = ++latest.current
    setState({ kind: 'asking', question: asked, about })
    send()
      .then((body) => {
        if (id === latest.current)
          setState({ kind: 'done', question: asked, about, outcome: classifyNl(body) })
      })
      .catch((error: unknown) => {
        if (id !== latest.current) return
        if (error instanceof ApiError && error.problem.kind === 'rate-limited') {
          setWaitUntil(Date.now() + error.problem.detail.retry_after_s * 1000)
        }
        setState({ kind: 'error', question: asked, about, error })
      })
  }

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!question || asking || waitUntil !== null) return
    const request: NLRequest = {
      text: question,
      selected_site_id: site.id,
      selected_scenario: scenario ?? undefined,
    }
    run(question, null, () => askNl(source, request, example))
  }

  // An example sends its exact recorded request (its question, and its site and scenario if it has
  // them), which is what the API's cache matches. Cached answers aren't rate limited, so examples
  // stay available while Ask waits after a 429.
  const askExample = (entry: StaticNLEntry) => {
    if (asking) return
    setText(entry.request.text)
    const siteId = entry.request.selected_site_id
    run(entry.request.text, siteId ? (names.byId(siteId) ?? siteId) : null, () => askNlExample(entry))
  }

  return (
    // The dashboard above is for `scenario`: answers needn't repeat it (TerrainViews.tsx).
    <DashboardScenario.Provider value={scenario}>
      <Section id="questions" title="Ask about this site" className="nl-box">
        <p className="muted">
          Ask in plain words. A language model turns the question into one of this tool's queries; the numbers
          come from our precomputed results, not from the model.
        </p>
        {source === 'fixtures' && (
          <div className="banner placeholder" role="note">
            <strong>Fixture mode:</strong> your question isn't sent anywhere. The box shows one of the example
            answers in <span className="mono">fixtures/</span>:{' '}
            <select
              aria-label="Example answer"
              value={example}
              onChange={(e) => setExample(e.target.value as NlExample)}
            >
              {EXAMPLES.map((x) => (
                <option key={x.value} value={x.value}>
                  {x.label}
                </option>
              ))}
            </select>
          </div>
        )}
        <form className="nl-form" onSubmit={submit}>
          <textarea
            aria-label="Your question"
            rows={3}
            maxLength={MAX_CHARS}
            value={text}
            placeholder={`For example: how long is the longest shadow at ${displayName(site)}?`}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) submit(e)
            }}
          />
          <div className="nl-form-row">
            <span className="muted">
              {text.length} / {MAX_CHARS} characters
            </span>
            <button type="submit" disabled={!question || asking || waitUntil !== null}>
              {asking ? 'Asking…' : 'Ask'}
            </button>
          </div>
        </form>
        {examples.length > 0 && (
          <div className="nl-examples">
            <span className="muted">Example questions (answers recorded in advance):</span>
            <ul>
              {examples.map((x) => {
                const siteId = x.request.selected_site_id
                return (
                  <li key={x.path}>
                    <button
                      type="button"
                      className="link-button"
                      disabled={asking}
                      onClick={() => askExample(x)}
                    >
                      {x.request.text}
                    </button>
                    {siteId && <span className="muted"> (about {names.byId(siteId) ?? siteId})</span>}
                  </li>
                )
              })}
            </ul>
          </div>
        )}
        {state.kind !== 'idle' && (
          <div className="nl-answer" aria-live="polite">
            <p className="nl-question">
              <span className="muted">You asked:</span> “{state.question}”
              {state.about && <span className="muted"> (about {state.about})</span>}
            </p>
            {state.kind === 'asking' && <p className="muted">Working on it…</p>}
            {state.kind === 'done' && <OutcomeView outcome={state.outcome} />}
            {state.kind === 'error' && <ProblemView error={state.error} />}
          </div>
        )}
      </Section>
    </DashboardScenario.Provider>
  )
}
