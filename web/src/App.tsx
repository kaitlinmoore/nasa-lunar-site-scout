// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// App shell: header (data source, contract versions), the current view, footer.
// Views (src/route.ts): the globe (default, C7a) and a site's screen (`?site=<id>`).
import { useEffect, useState } from 'react'
import {
  API_BASE,
  type MetricsResponse,
  type Site,
  type SiteLocation,
  type SitesResponse,
  WEB_CONTRACT_VERSION,
} from './api/client'
import { type DataSource, dataSource, loadSites, loadThinSliceMetrics, loadThinSliceSky } from './api/source'
import GlobeView from './globe/GlobeView'
import { navigate, routeHref, useRoute } from './route'
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

/** Contract versions of the responses on screen; flags any that differ from the web build's. */
function ContractCheck({ responses }: { responses: ({ contract_version: string } | null | undefined)[] }) {
  const versions = [...new Set(responses.filter((r) => r != null).map((r) => r.contract_version))]
  const mismatched = versions.filter((v) => v !== WEB_CONTRACT_VERSION)
  return (
    <>
      {versions.length > 0 && <p className="muted source">Data contract {versions.join(', ')}</p>}
      {mismatched.length > 0 && (
        <p className="banner error" role="alert">
          Contract version mismatch: the web was built for {WEB_CONTRACT_VERSION}, the data is{' '}
          {mismatched.join(', ')}. Values may be misread.
        </p>
      )}
    </>
  )
}

function sameLocation(a: SiteLocation, b: SiteLocation): boolean {
  return a.lat === b.lat && a.lon === b.lon
}

function BackToGlobe() {
  const route = { view: 'globe' } as const
  return (
    <p className="back-link">
      <a
        href={routeHref(route)}
        onClick={(e) => {
          e.preventDefault()
          navigate(route)
        }}
      >
        ← Moon
      </a>
    </p>
  )
}

/** The site screen for one curated site. Shows results only if they are for this site's location. */
function SitePage({ site, source }: { site: Site; source: DataSource }) {
  const metrics = useLoad<MetricsResponse>(loadThinSliceMetrics, source)
  const sky = useLoad(loadThinSliceSky, source)
  const data = metrics.kind === 'ok' ? metrics.data : null
  const skyData = sky.kind === 'ok' ? sky.data : null

  // The only computed scenario so far is the C1 thin slice. Never show it under another site.
  const metricsForSite = data !== null && sameLocation(data.scenario.location, site.location)
  const skyForSite = skyData != null && sameLocation(skyData.series.scenario.location, site.location)

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
    ) : skyForSite && skyData ? (
      <SkyView horizon={skyData.horizon} series={skyData.series} />
    ) : null

  return (
    <>
      <BackToGlobe />
      <ContractCheck
        responses={[metricsForSite ? data : null, skyForSite ? skyData?.series : null, skyForSite ? skyData?.horizon : null]}
      />
      {metrics.kind === 'loading' && <p className="muted">Loading metrics…</p>}
      {metrics.kind === 'error' && <LoadError what="metrics" message={metrics.message} />}
      {data && !metricsForSite && (
        <section className="card">
          <h2>{site.name}</h2>
          <p className="muted">
            No computed scenario for this site yet. So far only the C1 thin-slice scenario has results.
          </p>
        </section>
      )}
      {data && metricsForSite && (
        <>
          {data._placeholder && (
            <div className="banner placeholder" role="note">
              <strong>Placeholder data, not a computed result.</strong>
              {data._note && <div className="muted">{data._note}</div>}
            </div>
          )}
          <SiteScreen data={data}>{skySection}</SiteScreen>
        </>
      )}
    </>
  )
}

export default function App() {
  const source = dataSource()
  const route = useRoute()
  const sites = useLoad<SitesResponse>(loadSites, source)
  const siteList = sites.kind === 'ok' ? sites.data : null

  let body
  if (sites.kind === 'loading') body = <p className="muted">Loading sites…</p>
  else if (sites.kind === 'error') body = <LoadError what="the curated sites" message={sites.message} />
  else if (route.view === 'globe') {
    body = <GlobeView data={sites.data} />
  } else {
    const site = sites.data.sites.find((s) => s.id === route.siteId)
    body = site ? (
      <SitePage key={site.id} site={site} source={source} />
    ) : (
      <>
        <BackToGlobe />
        <div className="banner error" role="alert">
          <strong>Unknown site:</strong> <span className="mono">{route.siteId}</span>
        </div>
      </>
    )
  }

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
        </p>
        {route.view === 'globe' && <ContractCheck responses={[siteList]} />}
      </header>

      {body}

      <footer className="muted">Not affiliated with or endorsed by NASA.</footer>
    </main>
  )
}
