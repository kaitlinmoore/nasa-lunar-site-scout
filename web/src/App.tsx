// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
import { useEffect, useState } from 'react'
import { API_BASE, type MetricsResponse, WEB_CONTRACT_VERSION } from './api/client'
import { type DataSource, dataSource, loadThinSliceMetrics, loadThinSliceSky } from './api/source'
import SiteScreen from './SiteScreen'
import SkyView from './sky/SkyView'

type Load<T> = { kind: 'loading' } | { kind: 'ok'; data: T } | { kind: 'error'; message: string }

/**
 * Load data for `source` with a stable, module-level loader; errors become an error state,
 * never empty data. The source comes from the URL, so it's fixed for the page's lifetime.
 */
function useLoad<T>(load: (source: DataSource) => Promise<T>, source: DataSource): Load<T> {
  const [state, setState] = useState<Load<T>>({ kind: 'loading' })
  useEffect(() => {
    let cancelled = false
    load(source)
      .then((data) => !cancelled && setState({ kind: 'ok', data }))
      .catch((e: unknown) => {
        if (!cancelled) setState({ kind: 'error', message: e instanceof Error ? e.message : String(e) })
      })
    return () => {
      cancelled = true
    }
  }, [load, source])
  return state
}

function LoadError({ what, message }: { what: string; message: string }) {
  return (
    <div className="banner error" role="alert">
      <strong>Could not load {what}.</strong> No values are shown.
      <div className="mono">{message}</div>
    </div>
  )
}

export default function App() {
  const source = dataSource()
  const metrics = useLoad<MetricsResponse>(loadThinSliceMetrics, source)
  const sky = useLoad(loadThinSliceSky, source)

  const data = metrics.kind === 'ok' ? metrics.data : null
  const skyData = sky.kind === 'ok' ? sky.data : null

  // Contract versions of every response on screen; any that differs from the web's is flagged.
  const versions = [
    ...new Set(
      [data, skyData?.series, skyData?.horizon]
        .filter((r) => r != null)
        .map((r) => r.contract_version),
    ),
  ]
  const mismatched = versions.filter((v) => v !== WEB_CONTRACT_VERSION)

  const skySection =
    source !== 'fixtures' ? (
      <section className="card">
        <h2>Horizon and sky</h2>
        <p className="muted">
          Fixture mode only for now: the live horizon and series endpoints aren't available yet. Open
          this page with <span className="mono">?source=fixtures</span> to see it with placeholder data.
        </p>
      </section>
    ) : sky.kind === 'loading' ? (
      <p className="muted">Loading horizon and series…</p>
    ) : sky.kind === 'error' ? (
      <LoadError what="the horizon and series" message={sky.message} />
    ) : (
      sky.data && <SkyView horizon={sky.data.horizon} series={sky.data.series} />
    )

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
          {versions.length > 0 && <> · data contract {versions.join(', ')}</>}
        </p>
      </header>

      {mismatched.length > 0 && (
        <p className="banner error" role="alert">
          Contract version mismatch: the web was built for {WEB_CONTRACT_VERSION}, the data is{' '}
          {mismatched.join(', ')}. Values may be misread.
        </p>
      )}
      {data?._placeholder && (
        <div className="banner placeholder" role="note">
          <strong>Placeholder data, not a computed result.</strong>
          {data._note && <div className="muted">{data._note}</div>}
        </div>
      )}

      {metrics.kind === 'loading' && <p className="muted">Loading metrics…</p>}
      {metrics.kind === 'error' && <LoadError what="metrics" message={metrics.message} />}
      {data ? <SiteScreen data={data}>{skySection}</SiteScreen> : skySection}

      <footer className="muted">Not affiliated with or endorsed by NASA.</footer>
    </main>
  )
}
