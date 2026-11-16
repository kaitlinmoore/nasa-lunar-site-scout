// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// Saved items and comparison (C6). Minimal layout on purpose (Kaitlin judges it later).
// - Saved scenarios (browser storage), export/import as portable JSON. Pinned sites are kept in
//   the same document (so export/import carry them) but shown on the globe, not here (Kaitlin,
//   2026-11-15: the globe is for "where", this page for "where + when").
// - A small form makes scenarios for several sites × several dates.
// - The comparison is the saved scenarios ticked for it, side by side.
import { type FormEvent, type ReactNode, useEffect, useRef, useState } from 'react'
import { type Scenario, type Site, WEB_CONTRACT_VERSION } from '../api/client'
import { type ComparisonResult, type DataSource, loadCompare } from '../api/source'
import ApiProblemView from '../ApiProblemView'
import { formatExactRange, formatScenarioSummary, formatUtcInput, parseUtcInput } from '../format'
import { navigate, routeHref } from '../route'
import { validateScenario } from '../scenario'
import CompareTable from './CompareTable'
import { exportJson, type ImportReport, useSaved } from './store'

function SiteLink({ siteId, children }: { siteId: string; children: ReactNode }) {
  const route = { view: 'site', siteId } as const
  return (
    <a
      href={routeHref(route)}
      onClick={(e) => {
        e.preventDefault()
        navigate(route)
      }}
    >
      {children}
    </a>
  )
}

function ScenarioForm({ sites, defaults }: { sites: Site[]; defaults: Scenario | null }) {
  const saved = useSaved()
  const [siteId, setSiteId] = useState(sites[0]?.id ?? '')
  const [height, setHeight] = useState(defaults ? String(defaults.unit_height_m) : '')
  // Times are typed and shown explicitly in UTC ("YYYY-MM-DD HH:MM"), never in the browser's
  // local format (Kaitlin, 2026-11-15).
  const [start, setStart] = useState(defaults ? formatUtcInput(defaults.window_start) : '')
  const [end, setEnd] = useState(defaults ? formatUtcInput(defaults.window_end) : '')
  const [step, setStep] = useState(defaults?.step ?? 'PT1H')
  const [message, setMessage] = useState<{ kind: 'ok' | 'error'; text: string } | null>(null)

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const site = sites.find((s) => s.id === siteId)
    if (!site) {
      setMessage({ kind: 'error', text: 'Pick a site.' })
      return
    }
    const startIso = parseUtcInput(start)
    const endIso = parseUtcInput(end)
    if (!startIso || !endIso) {
      setMessage({
        kind: 'error',
        text: 'Write the times as YYYY-MM-DD HH:MM in UTC, e.g. 2028-05-15 00:00.',
      })
      return
    }
    if (Date.parse(endIso) <= Date.parse(startIso)) {
      setMessage({ kind: 'error', text: 'The time window must end after it starts.' })
      return
    }
    const v = validateScenario({
      location: site.location,
      unit_height_m: height.trim() === '' ? NaN : Number(height),
      window_start: startIso,
      window_end: endIso,
      step: step.trim(),
    })
    if ('error' in v) {
      setMessage({ kind: 'error', text: v.error })
      return
    }
    const r = saved.saveScenario(v.ok, site.name, site.id)
    setMessage(r.saved ? { kind: 'ok', text: 'Saved.' } : { kind: 'error', text: `Not saved: ${r.reason}.` })
  }

  return (
    <form className="scenario-form" onSubmit={submit}>
      <label>
        Site
        <select value={siteId} onChange={(e) => setSiteId(e.target.value)}>
          {sites.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        Unit height (m)
        <input
          type="number"
          min="0"
          step="any"
          value={height}
          onChange={(e) => setHeight(e.target.value)}
          required
        />
      </label>
      <label>
        Time window start
        <span className="utc-field">
          <input
            type="text"
            inputMode="numeric"
            placeholder="YYYY-MM-DD HH:MM"
            value={start}
            onChange={(e) => setStart(e.target.value)}
            size={16}
            required
          />{' '}
          UTC
        </span>
      </label>
      <label>
        Time window end
        <span className="utc-field">
          <input
            type="text"
            inputMode="numeric"
            placeholder="YYYY-MM-DD HH:MM"
            value={end}
            onChange={(e) => setEnd(e.target.value)}
            size={16}
            required
          />{' '}
          UTC
        </span>
      </label>
      <label>
        Step (ISO 8601)
        <input type="text" value={step} onChange={(e) => setStep(e.target.value)} size={8} required />
      </label>
      <button type="submit">Save scenario</button>
      {message && (
        <p
          className={message.kind === 'error' ? 'error' : 'muted'}
          role={message.kind === 'error' ? 'alert' : 'status'}
        >
          {message.text}
        </p>
      )}
    </form>
  )
}

function ImportExport() {
  const saved = useSaved()
  const fileInput = useRef<HTMLInputElement>(null)
  const [report, setReport] = useState<ImportReport | { error: string } | null>(null)

  const doExport = () => {
    const blob = new Blob([exportJson(saved.doc)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `lunar-site-scout-saved-${new Date().toISOString().slice(0, 10)}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const doImport = async (file: File) => {
    setReport(saved.importText(await file.text()))
    if (fileInput.current) fileInput.current.value = ''
  }

  return (
    <div className="import-export">
      <button type="button" onClick={doExport}>
        Export saved items (JSON)
      </button>
      <label className="file-button">
        Import…
        <input
          ref={fileInput}
          type="file"
          accept="application/json,.json"
          onChange={(e) => e.target.files?.[0] && void doImport(e.target.files[0])}
        />
      </label>
      {report &&
        ('error' in report ? (
          <p className="error" role="alert">
            Import failed: {report.error}. Nothing was changed.
          </p>
        ) : (
          <div role="status">
            <p className="muted">
              Imported: {report.added} new scenario(s), {report.alreadySaved} already saved,{' '}
              {report.pinsAdded} new pinned site(s).
            </p>
            {report.rejected.length > 0 && (
              <div className="banner error">
                <strong>Not imported ({report.rejected.length}):</strong>
                <ul>
                  {report.rejected.map((r, i) => (
                    <li key={i}>
                      {r.what}: {r.reason}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ))}
    </div>
  )
}

/** Results are tagged with the selection they answer (`forKey`), so a changed selection never
 * shows another selection's numbers, even for a moment. */
type CompareState =
  | { kind: 'idle' }
  | { kind: 'ok'; forKey: string; result: ComparisonResult }
  | { kind: 'error'; forKey: string; error: unknown }

function Comparison({ source }: { source: DataSource }) {
  const saved = useSaved()
  const selected = saved.doc.compare_ids
    .map((id) => saved.doc.scenarios.find((s) => s.id === id))
    .filter((s) => s !== undefined)
  // The selection as a stable value: the effect reloads exactly when it changes.
  const key = JSON.stringify(selected.map((s) => s.scenario))
  const [state, setState] = useState<CompareState>({ kind: 'idle' })

  useEffect(() => {
    if (key === '[]') return
    let cancelled = false
    loadCompare(source, JSON.parse(key) as Scenario[])
      .then((result) => {
        if (!cancelled) setState({ kind: 'ok', forKey: key, result })
      })
      .catch((e: unknown) => {
        if (!cancelled) setState({ kind: 'error', forKey: key, error: e })
      })
    return () => {
      cancelled = true
    }
  }, [key, source])

  if (selected.length === 0)
    return <p className="muted">Tick saved scenarios above to compare them side by side.</p>
  if (state.kind === 'idle' || state.forKey !== key) return <p className="muted">Loading comparison…</p>
  if (state.kind === 'error') return <ApiProblemView what="the comparison" error={state.error} />

  const { meta, items, reasons, noneReason } = state.result
  const anyPlaceholder = !!meta?._placeholder || items.some((i) => i?._placeholder)
  const versions = [
    ...new Set([
      ...(meta ? [meta.contract_version] : []),
      ...items.flatMap((i) => (i ? [i.contract_version] : [])),
    ]),
  ]
  const mismatched = versions.filter((v) => v !== WEB_CONTRACT_VERSION)
  return (
    <>
      {mismatched.length > 0 && (
        <p className="banner error" role="alert">
          Contract version mismatch: the web was built for {WEB_CONTRACT_VERSION}, the data is{' '}
          {mismatched.join(', ')}. Values may be misread.
        </p>
      )}
      {anyPlaceholder && (
        <div className="banner placeholder" role="note">
          <strong>Placeholder data, not a computed result.</strong>
          {meta?._note && <div className="muted">{meta._note}</div>}
        </div>
      )}
      {noneReason && (
        <div className="banner notice" role="status">
          <strong>None of these scenarios has a result yet.</strong> {noneReason}
        </div>
      )}
      <CompareTable entries={selected.map((s, i) => ({ saved: s, result: items[i], reason: reasons[i] }))} />
    </>
  )
}

export default function SavedView({
  sites,
  sitesProblem,
  source,
  defaults,
}: {
  sites: Site[]
  /** why sites aren't available (loading or failed), or null */
  sitesProblem: string | null
  source: DataSource
  defaults: Scenario | null
}) {
  const saved = useSaved()
  const { doc } = saved
  const toggleCompare = (id: string, on: boolean) => {
    const ids = doc.compare_ids.filter((x) => x !== id)
    saved.setCompareIds(on ? [...ids, id] : ids)
  }

  return (
    <>
      {saved.storageError && (
        <div className="banner error" role="alert">
          {saved.storageError}
        </div>
      )}

      <section className="card">
        <h2>Saved items</h2>
        <p className="definition">
          Your saved scenarios and pinned sites are kept in this browser. Export them as a JSON file to keep a
          copy or move them to another browser.
        </p>
        <ImportExport />
      </section>

      <section className="card">
        <h2>Add a scenario</h2>
        {sitesProblem ? (
          <p className="muted" role="status">
            {sitesProblem}
          </p>
        ) : sites.length === 0 ? (
          <p className="muted">No curated sites to choose from.</p>
        ) : (
          // Remount when the defaults arrive so the fields start from them.
          <ScenarioForm key={defaults ? 'with-defaults' : 'no-defaults'} sites={sites} defaults={defaults} />
        )}
      </section>

      <section className="card">
        <h2>Saved scenarios</h2>
        {doc.scenarios.length === 0 ? (
          <p className="muted">No saved scenarios yet. Add one above or save one from a site screen.</p>
        ) : (
          <ul className="saved-list">
            {doc.scenarios.map((s) => {
              const sc = s.scenario
              const inCompare = doc.compare_ids.includes(s.id)
              return (
                <li key={s.id}>
                  <label>
                    <input
                      type="checkbox"
                      checked={inCompare}
                      onChange={(e) => toggleCompare(s.id, e.target.checked)}
                    />{' '}
                    Compare
                  </label>{' '}
                  {s.site_id ? <SiteLink siteId={s.site_id}>{s.label}</SiteLink> : <span>{s.label}</span>}{' '}
                  <span className="muted value" title={formatExactRange(sc.window_start, sc.window_end)}>
                    {formatScenarioSummary(sc)}
                  </span>{' '}
                  <button type="button" className="link-button" onClick={() => saved.removeScenario(s.id)}>
                    Delete
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </section>

      <section className="card">
        <h2>Comparison</h2>
        <Comparison source={source} />
      </section>
    </>
  )
}
