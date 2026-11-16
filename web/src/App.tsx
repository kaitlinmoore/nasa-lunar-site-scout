// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// App shell: header (data source, contract versions), the current view, footer.
// Views (src/route.ts): the globe (default, C7a), a site's screen (`?site=<id>`) and the saved
// items + comparison (`?view=saved`, C6).
import { useEffect, useState } from 'react'
import {
  API_BASE,
  type MetricsResponse,
  type Scenario,
  type Site,
  type SiteLocation,
  type SitesResponse,
  WEB_CONTRACT_VERSION,
} from './api/client'
import {
  type DataSource,
  dataSource,
  loadSites,
  loadThinSliceMetrics,
  loadThinSliceSky,
  thinSliceScenario,
} from './api/source'
import ApiProblemView from './ApiProblemView'
import { formatLatLon, formatSavedLabel } from './format'
import GlobeView from './globe/GlobeView'
import { navigate, type Route, routeHref, useRoute } from './route'
import { useUsingStaticCopy } from './api/staticFallback'
import SavedView from './saved/SavedView'
import NlBox from './nl/NlBox'
import { useSaved } from './saved/store'
import SiteScreen from './SiteScreen'
import SkyView from './sky/SkyView'

/** An error's message, for short inline text. */
function errorText(e: unknown): string {
  return e instanceof Error ? e.message : String(e)
}

type Load<T> = { kind: 'loading' } | { kind: 'ok'; data: T } | { kind: 'error'; error: unknown }

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
        if (!cancelled) setState({ kind: 'error', error: e })
      })
    return () => {
      cancelled = true
    }
  }, [load, source])
  return state
}

/**
 * Developer info (data source, contract versions): shown in dev builds only. It means nothing to
 * public visitors (Kaitlin, 2026-11-15). The contract-mismatch warning is shown in every build.
 */
const SHOW_DEV_INFO = import.meta.env.DEV

/**
 * Shown while any part of the page comes from the static copy because the live API isn't
 * answering (Kaitlin, 2026-11-15: switch-over with a visible notice). Wording: SI draft.
 */
function StaticCopyNotice() {
  if (!useUsingStaticCopy()) return null
  return (
    <div className="banner notice" role="status">
      <strong>The live server isn't answering right now,</strong> so you're seeing the saved copy of our
      precomputed results that's published with this site.
    </div>
  )
}

/** Contract versions of the responses on screen; flags any that differ from the web build's. */
function ContractCheck({ responses }: { responses: ({ contract_version: string } | null | undefined)[] }) {
  const versions = [...new Set(responses.filter((r) => r != null).map((r) => r.contract_version))]
  const mismatched = versions.filter((v) => v !== WEB_CONTRACT_VERSION)
  return (
    <>
      {SHOW_DEV_INFO && versions.length > 0 && (
        <p className="muted source">Data contract {versions.join(', ')}</p>
      )}
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

function NavLink({ to, current, children }: { to: Route; current: Route; children: string }) {
  const active = to.view === current.view
  return (
    <a
      href={routeHref(to)}
      aria-current={active ? 'page' : undefined}
      onClick={(e) => {
        e.preventDefault()
        navigate(to)
      }}
    >
      {children}
    </a>
  )
}

/**
 * Main menu. "Saved scenarios" appears only once a scenario is saved (Kaitlin, 2026-11-15): a new
 * visitor doesn't see a link to an empty list before they know saving exists. It also shows while
 * you're on that page. Pinned sites live on the globe, so they don't count here.
 */
function Nav({ route }: { route: Route }) {
  const { doc } = useSaved()
  const anythingSaved = doc.scenarios.length > 0
  return (
    <nav className="nav">
      <NavLink to={{ view: 'globe' }} current={route}>
        Moon
      </NavLink>
      {(anythingSaved || route.view === 'saved') && (
        <NavLink to={{ view: 'saved' }} current={route}>
          {formatSavedLabel(doc.scenarios.length)}
        </NavLink>
      )}
    </nav>
  )
}

/**
 * What and where the site is, from its `description` in /api/sites (stream A writes these).
 * An empty or missing description is simply left out.
 */
function SiteIntro({ site }: { site: Site }) {
  const description = site.description?.trim()
  return (
    <section className="site-intro">
      <h2>{site.name}</h2>
      {description && <p>{description}</p>}
    </section>
  )
}

/** Pin the site; save the displayed scenario (C6). */
function SiteActions({ site, scenario }: { site: Site; scenario: Scenario | null }) {
  const saved = useSaved()
  const pinned = saved.isPinned(site.id)
  const isSaved = scenario !== null && saved.isSaved(scenario)
  const [error, setError] = useState<string | null>(null)
  return (
    <div className="site-actions">
      <button type="button" onClick={() => (pinned ? saved.unpinSite(site.id) : saved.pinSite(site))}>
        {pinned ? 'Unpin site' : 'Pin site'}
      </button>
      {scenario && (
        <button
          type="button"
          disabled={isSaved}
          onClick={() => {
            const r = saved.saveScenario(scenario, site.name, site.id)
            setError(r.saved ? null : (r.reason ?? 'not saved'))
          }}
        >
          {isSaved ? 'Scenario saved' : 'Save this scenario'}
        </button>
      )}
      {/* Where saving happens is where the saved list gets introduced (Kaitlin, 2026-11-15). */}
      {isSaved && (
        <a
          href={routeHref({ view: 'saved' })}
          onClick={(e) => {
            e.preventDefault()
            navigate({ view: 'saved' })
          }}
        >
          Compare saved scenarios →
        </a>
      )}
      {error && (
        <span className="error" role="alert">
          {' '}
          Not saved: {error}.
        </span>
      )}
    </div>
  )
}

const loadDefaults = () => thinSliceScenario()

/** The site screen for one curated site. Shows results only if they are for this site's location. */
function SitePage({ site, source }: { site: Site; source: DataSource }) {
  const metrics = useLoad<MetricsResponse>(loadThinSliceMetrics, source)
  const sky = useLoad(loadThinSliceSky, source)
  const data = metrics.kind === 'ok' ? metrics.data : null
  const skyData = sky.kind === 'ok' ? sky.data : null

  // The only computed scenario so far is the C1 thin slice. Never show it under another site.
  const metricsForSite = data !== null && sameLocation(data.scenario.location, site.location)
  const skyForSite = skyData != null && sameLocation(skyData.series.scenario.location, site.location)

  // Horizon and sky: fixtures, or live /api/series + /api/horizon (Phase 2 step 3.2).
  const skySection =
    sky.kind === 'loading' ? (
      <p className="muted">Loading horizon and series…</p>
    ) : sky.kind === 'error' ? (
      <ApiProblemView what="the horizon and series" error={sky.error} />
    ) : skyForSite && skyData ? (
      <SkyView horizon={skyData.horizon} series={skyData.series} />
    ) : null

  return (
    <>
      <SiteIntro site={site} />
      <SiteActions site={site} scenario={metricsForSite && data ? data.scenario : null} />
      <ContractCheck
        responses={[
          metricsForSite ? data : null,
          skyForSite ? skyData?.series : null,
          skyForSite ? skyData?.horizon : null,
        ]}
      />
      {metrics.kind === 'loading' && <p className="muted">Loading metrics…</p>}
      {metrics.kind === 'error' && <ApiProblemView what="metrics" error={metrics.error} />}
      {data && !metricsForSite && (
        <section className="card">
          <p className="muted">
            No computed scenario for this site yet. So far only the C1 thin-slice scenario has results.
          </p>
          <p className="muted value">{formatLatLon(site.location.lat, site.location.lon)}</p>
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
      {/* Questions (C7b), below the dashboard; a fresh box per site. */}
      <NlBox
        key={site.id}
        site={site}
        scenario={metricsForSite && data ? data.scenario : null}
        source={source}
      />
    </>
  )
}

export default function App() {
  const source = dataSource()
  const route = useRoute()
  const sites = useLoad<SitesResponse>(loadSites, source)
  const siteList = sites.kind === 'ok' ? sites.data : null
  const defaults = useLoad<Scenario>(loadDefaults, source)

  let body
  // Saved items live in this browser, so their page works even when the site list can't load.
  if (route.view === 'saved') {
    body = (
      <SavedView
        sites={sites.kind === 'ok' ? sites.data.sites : []}
        sitesProblem={
          sites.kind === 'loading'
            ? 'Loading sites…'
            : sites.kind === 'error'
              ? `Could not load the curated sites (${errorText(sites.error)}), so new scenarios can't be added.`
              : null
        }
        source={source}
        defaults={defaults.kind === 'ok' ? defaults.data : null}
      />
    )
  } else if (sites.kind === 'loading') body = <p className="muted">Loading sites…</p>
  else if (sites.kind === 'error') body = <ApiProblemView what="the curated sites" error={sites.error} />
  else {
    // Globe and site share one layout (Kaitlin, 2026-11-15, layout (c)): the globe stays mounted,
    // and a site's screen opens in a side panel beside it, so you keep your place on the Moon.
    const siteId = route.view === 'site' ? route.siteId : null
    const site = siteId ? sites.data.sites.find((s) => s.id === siteId) : undefined
    body = (
      <div className={`globe-layout${siteId ? ' with-panel' : ''}`}>
        <GlobeView data={sites.data} focusSiteId={site ? site.id : null} />
        {siteId && (
          <aside className="site-panel" aria-label="Site details">
            <button
              type="button"
              className="site-panel-close"
              aria-label="Close site details"
              title="Close (back to the whole Moon)"
              onClick={() => navigate({ view: 'globe' })}
            >
              ✕
            </button>
            {site ? (
              <SitePage key={site.id} site={site} source={source} />
            ) : (
              <div className="banner error" role="alert">
                <strong>Unknown site:</strong> <span className="mono">{siteId}</span>
              </div>
            )}
          </aside>
        )}
      </div>
    )
  }

  return (
    <main className={route.view === 'site' ? 'wide' : undefined}>
      <header>
        <h1>Penumbra Luna</h1>
        <p className="subtitle">Lunar Landing Site Navigator</p>
        {SHOW_DEV_INFO && (
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
        )}
        {route.view === 'globe' && <ContractCheck responses={[siteList]} />}
        <Nav route={route} />
      </header>
      <StaticCopyNotice />

      {body}

      <footer className="muted">Not affiliated with or endorsed by NASA.</footer>
    </main>
  )
}
