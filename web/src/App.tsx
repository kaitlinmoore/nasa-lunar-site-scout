// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
import { useEffect, useState } from 'react'
import { API_BASE, type MetricsResponse, WEB_CONTRACT_VERSION } from './api/client'
import { dataSource, loadThinSliceMetrics } from './api/source'
import SiteScreen from './SiteScreen'

type State =
  | { kind: 'loading' }
  | { kind: 'ok'; data: MetricsResponse }
  | { kind: 'error'; message: string }

export default function App() {
  const source = dataSource()
  const [state, setState] = useState<State>({ kind: 'loading' })

  useEffect(() => {
    let cancelled = false
    loadThinSliceMetrics(source)
      .then((data) => !cancelled && setState({ kind: 'ok', data }))
      .catch((e: unknown) => {
        if (!cancelled) setState({ kind: 'error', message: e instanceof Error ? e.message : String(e) })
      })
    return () => {
      cancelled = true
    }
  }, [source])

  const data = state.kind === 'ok' ? state.data : null
  const mismatch = data !== null && data.contract_version !== WEB_CONTRACT_VERSION

  return (
    <main>
      <header>
        <h1>Lunar Site Scout</h1>
        <p className="muted source">
          Data source:{' '}
          {source === 'fixtures' ? (
            <strong>fixtures</strong>
          ) : (
            <>
              <strong>live API</strong> {API_BASE || '(same origin)'}
            </>
          )}
          {' · '}web contract {WEB_CONTRACT_VERSION}
          {data && <> · data contract {data.contract_version}</>}
        </p>
      </header>

      {mismatch && (
        <p className="banner error" role="alert">
          Contract version mismatch: the web was built for {WEB_CONTRACT_VERSION}, the data is{' '}
          {data.contract_version}. Values may be misread.
        </p>
      )}
      {data?._placeholder && (
        <div className="banner placeholder" role="note">
          <strong>Placeholder data, not a computed result.</strong>
          {data._note && <div className="muted">{data._note}</div>}
        </div>
      )}

      {state.kind === 'loading' && <p className="muted">Loading metrics…</p>}
      {state.kind === 'error' && (
        <div className="banner error" role="alert">
          <strong>Could not load metrics.</strong> No values are shown.
          <div className="mono">{state.message}</div>
        </div>
      )}
      {data && <SiteScreen data={data} />}

      <footer className="muted">Not affiliated with or endorsed by NASA.</footer>
    </main>
  )
}
