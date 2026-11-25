// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// App shell: header (data source, contract versions), the current view, footer.
// Views (src/route.ts): the globe (default), a site's screen (`?site=<id>`) and the saved
// items + comparison (`?view=saved`).
import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import {
  API_BASE,
  type Scenario,
  type ScenarioEntry,
  type Site,
  type SiteLocation,
  type SitesResponse,
  WEB_CONTRACT_VERSION,
} from './api/client'
import {
  type DataSource,
  dataSource,
  loadSites,
  loadMetrics,
  loadScenarios,
  loadSky,
  thinSliceScenario,
} from './api/source'
import ApiProblemView from './ApiProblemView'
import { formatLatLon, formatSavedLabel } from './format'
import GlobeView from './globe/GlobeView'
import { navigate, type Route, routeHref, useRoute } from './route'
import { useUsingStaticCopy } from './api/staticFallback'
import SavedView from './saved/SavedView'
import Section from './Section'
import { CollapsibleSections } from './sections'
import NlBox from './nl/NlBox'

// 2D site view: OpenLayers + proj4 load as their own chunk, only where the map is shown.
const TerrainSection = lazy(() => import('./terrain/TerrainSection'))
import { displayName, SiteNamesContext, siteNames, subtitleOf } from './siteNames'
import { useSaved } from './saved/store'
import SiteScreen from './SiteScreen'
import SkyView from './sky/SkyView'
import ScenarioPicker from './ScenarioPicker'
import { type Choice, resolveChoice, siteWindows } from './scenarioChoice'

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
 * public visitors (the project author, 2026-11-15). The contract-mismatch warning is shown in every build.
 */
const SHOW_DEV_INFO = import.meta.env.DEV

/**
 * Shown while any part of the page comes from the static copy because the live API isn't
 * answering (the project author, 2026-11-15: switch-over with a visible notice). Wording: Claude-drafted.
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
 * Main menu. "Saved scenarios" appears only once a scenario is saved (the project author, 2026-11-15): a new
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

/** The site's short name and subtitle (siteNames.ts), at the head of its panel. */
function SiteHeading({ site }: { site: Site }) {
  const subtitle = subtitleOf(site)
  return (
    <div className="site-heading">
      <h2 className="site-title">{displayName(site)}</h2>
      {subtitle && <div className="site-subtitle">{subtitle}</div>}
    </div>
  )
}

/**
 * What and where the site is, from its `description` in /api/sites (lss/registry/sites.yaml).
 * An empty or missing description is simply left out.
 */
function SiteIntro({ site }: { site: Site }) {
  const description = site.description?.trim()
  if (!description) return null
  return (
    <Section id="about" title="About this site" className="site-intro">
      <p>{description}</p>
    </Section>
  )
}

/** Pin the site; save the displayed scenario. */
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
      {/* Where saving happens is where the saved list gets introduced (the project author, 2026-11-15). */}
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
/**
 * Load `load(source, entry)` for the chosen scenario. After a change of scenario it reports
 * "loading" until that scenario's answer arrives; an answer for an earlier choice is dropped.
 */
function useScenarioLoad<T>(
  load: (source: DataSource, entry: ScenarioEntry) => Promise<T>,
  source: DataSource,
  entry: ScenarioEntry | null,
): Load<T> | null {
  const [state, setState] = useState<{ entry: ScenarioEntry; load: Load<T> } | null>(null)
  useEffect(() => {
    if (!entry) return
    let cancelled = false
    load(source, entry)
      .then((data) => !cancelled && setState({ entry, load: { kind: 'ok', data } }))
      .catch((error: unknown) => {
        if (!cancelled) setState({ entry, load: { kind: 'error', error } })
      })
    return () => {
      cancelled = true
    }
  }, [load, source, entry])
  if (!entry) return null
  return state && state.entry === entry ? state.load : { kind: 'loading' }
}

/**
 * A site's page: its precomputed scenarios from GET /api/scenarios, a plain window / height
 * picker, and the chosen scenario's dashboard. Only this site's scenarios are loaded.
 */
function SitePage({ site, source }: { site: Site; source: DataSource }) {
  const list = useLoad(loadScenarios, source)
  const windows = useMemo(
    () => (list.kind === 'ok' ? siteWindows(list.data.scenarios, site.id) : []),
    [list, site.id],
  )
  const [choice, setChoice] = useState<Choice | null>(null)
  const chosen = resolveChoice(windows, choice)
  const entry = chosen?.entry ?? null
  const metrics = useScenarioLoad(loadMetrics, source, entry)
  const sky = useScenarioLoad(loadSky, source, entry)
  const data = metrics?.kind === 'ok' ? metrics.data : null
  const skyData = sky?.kind === 'ok' ? sky.data : null

  // Never show a result under a site other than the one at its location.
  const metricsForSite = data !== null && sameLocation(data.scenario.location, site.location)
  const skyForSite = skyData !== null && sameLocation(skyData.series.scenario.location, site.location)

  // Horizon and sky for the chosen scenario: /api/series + /api/horizon.
  const skySection = !sky ? null : sky.kind === 'loading' ? (
    <p className="muted">Loading horizon and series…</p>
  ) : sky.kind === 'error' ? (
    <ApiProblemView what="the horizon and series" error={sky.error} />
  ) : !skyForSite || !skyData ? null : skyData.horizon ? (
    <SkyView horizon={skyData.horizon} series={skyData.series} />
  ) : (
    <Section id="sky" title="Horizon and sky">
      <p className="muted">
        This version has no terrain horizon for this location and unit height, so the sky view can't be drawn.
      </p>
    </Section>
  )

  return (
    // Sections on this page collapse; the same cards elsewhere don't.
    <CollapsibleSections.Provider value={true}>
      <SiteIntro site={site} />
      <SiteActions site={site} scenario={metricsForSite && data ? data.scenario : null} />
      <ContractCheck
        responses={[
          list.kind === 'ok' ? list.data : null,
          metricsForSite ? data : null,
          skyForSite ? skyData?.series : null,
          skyForSite ? skyData?.horizon : null,
        ]}
      />
      {list.kind === 'loading' && <p className="muted">Loading this site's scenarios…</p>}
      {list.kind === 'error' && (
        <ApiProblemView what="the list of precomputed scenarios" error={list.error} />
      )}
      {list.kind === 'ok' && windows.length === 0 && (
        <section className="card">
          <p className="muted">
            This version has no precomputed results for this site
            {source === 'fixtures' ? ' (fixture mode has only the example scenario)' : ''}.
          </p>
          <p className="muted value">{formatLatLon(site.location.lat, site.location.lon)}</p>
        </section>
      )}
      {chosen && <ScenarioPicker windows={windows} chosen={chosen} onChange={setChoice} />}
      {metrics?.kind === 'loading' && <p className="muted">Loading metrics…</p>}
      {metrics?.kind === 'error' && <ApiProblemView what="metrics" error={metrics.error} />}
      {data && !metricsForSite && (
        <div className="banner error" role="alert">
          The result returned is for a different location than this site, so it isn't shown.
        </div>
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
      {/* 2D site view: the site's terrain images (contract 0.13.0), static copy as fallback. */}
      <Suspense fallback={<p className="muted">Loading the terrain map…</p>}>
        <TerrainSection key={site.id} site={site} source={source} />
      </Suspense>
      {/* Questions, below the dashboard; a fresh box per site. It sends the chosen scenario. */}
      <NlBox key={site.id} site={site} scenario={entry ? entry.scenario : null} source={source} />
    </CollapsibleSections.Provider>
  )
}

export default function App() {
  const source = dataSource()
  const route = useRoute()
  const sites = useLoad<SitesResponse>(loadSites, source)
  const siteList = sites.kind === 'ok' ? sites.data : null
  // Every site name on screen comes from this list (siteNames.ts).
  const names = useMemo(() => siteNames(sites.kind === 'ok' ? sites.data.sites : []), [sites])
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
    // Globe and site share one layout (the project author, 2026-11-15): the globe stays mounted,
    // and a site's screen opens in a side panel beside it, so you keep your place on the Moon.
    const siteId = route.view === 'site' ? route.siteId : null
    const site = siteId ? sites.data.sites.find((s) => s.id === siteId) : undefined
    body = (
      <div className={`globe-layout${siteId ? ' with-panel' : ''}`}>
        <GlobeView data={sites.data} focusSiteId={site ? site.id : null} source={source} />
        {siteId && (
          <aside className="site-panel" aria-label="Site details">
            {/* The site's name stays in view while the panel scrolls (the project author, 2026-11-23). */}
            <div className="site-panel-head">
              {site && <SiteHeading site={site} />}
              <button
                type="button"
                className="site-panel-close"
                aria-label="Close site details"
                title="Close (back to the whole Moon)"
                onClick={() => navigate({ view: 'globe' })}
              >
                ✕
              </button>
            </div>
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

      <SiteNamesContext.Provider value={names}>{body}</SiteNamesContext.Provider>

      <footer className="muted">Not affiliated with or endorsed by NASA.</footer>
    </main>
  )
}
