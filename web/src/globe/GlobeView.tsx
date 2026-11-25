// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// Globe view: the Cesium Moon with clickable curated-site markers (lazy chunk), plus a
// plain list of the same sites. The list is the accessible equivalent of the markers (canvas
// markers can't be reached by keyboard or screen reader) and keeps working if WebGL or the
// Cesium token fails.
// Site selection (the project author, 2026-11-15): clicking a marker or a list entry shows a
// card on the globe (name, start of the description, "See details"); "See details" opens the
// site's side panel beside the globe (`?site=<id>`), and the globe zooms toward the site.
// Pinned sites (the project author, 2026-11-15) live here: a distinct marker, a Pin/Unpin button on the card,
// and a "Pinned" group first in the site list.
import { lazy, Suspense, useEffect, useState } from 'react'
import type { Site, SitesResponse } from '../api/client'
import type { DataSource } from '../api/source'
import { formatLatLon, truncateText } from '../format'
import { displayName, subtitleOf } from '../siteNames'
import { navigate, routeHref } from '../route'
import { type FeatureLabels, loadFeatureLabels } from './featureLabelData'
import { loadGlobeLabelFonts } from './labelStyle'
import { type PinnedSite, useSaved } from '../saved/store'

const MoonGlobe = lazy(() => import('./MoonGlobe'))

const ION_TOKEN = import.meta.env.VITE_CESIUM_ION_TOKEN

/** How much of a site's description the card shows before "See details". */
const CARD_DESCRIPTION_CHARS = 180

function detailsRoute(siteId: string) {
  return { view: 'site', siteId } as const
}

/** The card shown next to a selected site's marker. */
function SiteCard({ site, onClose }: { site: Site; onClose: () => void }) {
  const saved = useSaved()
  const pinned = saved.isPinned(site.id)
  const description = site.description?.trim()
  const subtitle = subtitleOf(site)
  const route = detailsRoute(site.id)
  return (
    <div className="site-card" role="dialog" aria-labelledby={`site-card-${site.id}`}>
      <button type="button" className="site-card-close" aria-label="Close" title="Close" onClick={onClose}>
        ✕
      </button>
      <h3 id={`site-card-${site.id}`}>{displayName(site)}</h3>
      {subtitle && <div className="site-subtitle">{subtitle}</div>}
      {description && <p>{truncateText(description, CARD_DESCRIPTION_CHARS)}</p>}
      <a
        className="button"
        href={routeHref(route)}
        onClick={(e) => {
          e.preventDefault()
          // The panel replaces the card. Clearing the selection also stops the card coming back
          // (and pulling the globe toward the site) when the panel is closed.
          onClose()
          navigate(route)
        }}
      >
        See details
      </a>{' '}
      <button
        type="button"
        aria-pressed={pinned}
        onClick={() => (pinned ? saved.unpinSite(site.id) : saved.pinSite(site))}
      >
        {pinned ? '★ Pinned' : '☆ Pin site'}
      </button>
    </div>
  )
}

function SiteList({
  sites,
  selected,
  onSelect,
}: {
  sites: Site[]
  selected: string | null
  onSelect: (siteId: string) => void
}) {
  if (sites.length === 0) return null
  return (
    <ul className="site-list">
      {sites.map((site) => (
        <li key={site.id}>
          <a
            href={routeHref(detailsRoute(site.id))}
            aria-current={selected === site.id ? 'true' : undefined}
            onClick={(e) => {
              e.preventDefault()
              onSelect(site.id)
            }}
          >
            {displayName(site)}
          </a>{' '}
          <span className="muted value">{formatLatLon(site.location.lat, site.location.lon)}</span>
        </li>
      ))}
    </ul>
  )
}

export default function GlobeView({
  data,
  focusSiteId,
  source,
}: {
  data: SitesResponse
  focusSiteId: string | null
  source: DataSource
}) {
  const [selected, setSelected] = useState<string | null>(null)
  // IAU feature names for the globe (contract 0.14.0); the globe works without them.
  const [features, setFeatures] = useState<FeatureLabels | null>(null)
  const [featuresProblem, setFeaturesProblem] = useState<string | null>(null)
  useEffect(() => {
    let cancelled = false
    loadFeatureLabels(source)
      .then((f) => !cancelled && setFeatures(f))
      .catch((e: unknown) => !cancelled && setFeaturesProblem(e instanceof Error ? e.message : String(e)))
    return () => {
      cancelled = true
    }
  }, [source])
  // The labels' web fonts, loaded before the globe draws any label (labelStyle.ts).
  const [fontsReady, setFontsReady] = useState(false)
  useEffect(() => {
    let cancelled = false
    void loadGlobeLabelFonts().then(() => !cancelled && setFontsReady(true))
    return () => {
      cancelled = true
    }
  }, [])
  const { doc, unpinSite } = useSaved()
  const pins: PinnedSite[] = doc.pinned_sites
  const pinnedIds = new Set(pins.map((p) => p.site_id))
  const pinnedSites = data.sites.filter((s) => pinnedIds.has(s.id))
  const otherSites = data.sites.filter((s) => !pinnedIds.has(s.id))
  // A pin whose site isn't in the current list (e.g. imported from another build).
  const missingPins = pins.filter((p) => !data.sites.some((s) => s.id === p.site_id))
  const selectedSite = data.sites.find((s) => s.id === selected) ?? null
  // With the panel open for a site, its card would repeat the panel: don't show it.
  const cardSite = selectedSite && selectedSite.id !== focusSiteId ? selectedSite : null

  // Escape closes the card.
  useEffect(() => {
    if (!cardSite) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setSelected(null)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [cardSite])

  const listSelected = selected ?? focusSiteId
  // Without a globe (no token), a list click goes straight to the site's panel.
  const select = (siteId: string) => (ION_TOKEN ? setSelected(siteId) : navigate(detailsRoute(siteId)))

  return (
    <section className="card">
      <h2>Moon</h2>
      {data._placeholder && (
        <div className="banner placeholder" role="note">
          <strong>Placeholder data, not a computed result:</strong> site list.
          {data._note && <div className="muted">{data._note}</div>}
        </div>
      )}
      {ION_TOKEN && !fontsReady ? (
        <p className="muted">Loading the globe…</p>
      ) : ION_TOKEN ? (
        <Suspense fallback={<p className="muted">Loading the globe…</p>}>
          <MoonGlobe
            featureLabels={features?.rows ?? null}
            sites={data.sites}
            token={ION_TOKEN}
            onSelect={setSelected}
            selectedSiteId={cardSite?.id ?? null}
            focusSiteId={focusSiteId}
            pinnedSiteIds={pins.map((p) => p.site_id)}
            card={cardSite ? <SiteCard site={cardSite} onClose={() => setSelected(null)} /> : null}
          />
        </Suspense>
      ) : (
        <p className="muted">
          The globe needs a Cesium ion token, and this build has none. The site list below still works.
        </p>
      )}
      {/* Caption wording chosen by the project author (2026-11-15); expert detail behind "Details". */}
      <p className="globe-caption">
        Near the Moon's south pole the Sun skims the horizon, so a few metres of height or a nearby hill
        decide between light and shadow. Choose a site to see it worked out from our own terrain calculations;
        the globe itself is just for finding your way.
      </p>
      <details className="globe-details">
        <summary>Details</summary>
        <p>
          The 3D Moon is Cesium's model (imagery and LOLA terrain), used for display only. Its terrain sits
          about 2.5 km above the LOLA heights our calculations use, so site markers are placed on its rendered
          surface and no values are taken from it. Every number in this tool comes from our own API.
        </p>
        {features && (
          <p>
            Feature names:{' '}
            {features.dataset ? (
              <>
                <a href={features.dataset.url}>{features.dataset.name}</a> ({features.dataset.provider});{' '}
                {features.dataset.license}
              </>
            ) : (
              <span className="mono">{features.datasetId}</span>
            )}{' '}
            Names label features only; their positions identify the features (to about 300 m).
          </p>
        )}
        {featuresProblem && <p className="muted">Feature names couldn't be loaded ({featuresProblem}).</p>}
      </details>
      {pins.length > 0 && (
        <>
          <h3 className="list-heading">★ Pinned</h3>
          <SiteList sites={pinnedSites} selected={listSelected} onSelect={select} />
          {missingPins.length > 0 && (
            <ul className="site-list">
              {missingPins.map((p) => (
                <li key={p.site_id}>
                  {p.name} <span className="muted">(not in the current site list)</span>{' '}
                  <button type="button" className="link-button" onClick={() => unpinSite(p.site_id)}>
                    Unpin
                  </button>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
      <h3 className="list-heading">{pins.length > 0 ? 'Other curated sites' : 'Curated sites'}</h3>
      {data.sites.length === 0 ? (
        <p className="muted">No curated sites.</p>
      ) : otherSites.length === 0 ? (
        <p className="muted">All curated sites are pinned.</p>
      ) : (
        <SiteList sites={otherSites} selected={listSelected} onSelect={select} />
      )}
    </section>
  )
}
