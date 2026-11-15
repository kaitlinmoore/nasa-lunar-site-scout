// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// C7a globe view: the Cesium Moon with clickable curated-site markers (lazy chunk), plus a
// plain list of the same sites. The list is the accessible equivalent of the markers (canvas
// markers can't be reached by keyboard or screen reader) and keeps working if WebGL or the
// Cesium token fails.
import { lazy, Suspense } from 'react'
import type { Site, SitesResponse } from '../api/client'
import { formatLatLon } from '../format'
import { navigate, routeHref } from '../route'

const MoonGlobe = lazy(() => import('./MoonGlobe'))

const ION_TOKEN = import.meta.env.VITE_CESIUM_ION_TOKEN

function SiteList({ sites }: { sites: Site[] }) {
  return (
    <ul className="site-list">
      {sites.map((site) => {
        const route = { view: 'site', siteId: site.id } as const
        return (
          <li key={site.id}>
            <a
              href={routeHref(route)}
              onClick={(e) => {
                e.preventDefault()
                navigate(route)
              }}
            >
              {site.name}
            </a>{' '}
            <span className="muted value">{formatLatLon(site.location.lat, site.location.lon)}</span>
          </li>
        )
      })}
    </ul>
  )
}

export default function GlobeView({ data }: { data: SitesResponse }) {
  const open = (siteId: string) => navigate({ view: 'site', siteId })
  return (
    <section className="card">
      <h2>Moon</h2>
      {data._placeholder && (
        <div className="banner placeholder" role="note">
          <strong>Placeholder data, not a computed result:</strong> site list.
          {data._note && <div className="muted">{data._note}</div>}
        </div>
      )}
      {ION_TOKEN ? (
        <Suspense fallback={<p className="muted">Loading the globe…</p>}>
          <MoonGlobe sites={data.sites} token={ION_TOKEN} onSelect={open} />
        </Suspense>
      ) : (
        <p className="muted">
          The globe needs a Cesium ion token, and this build has none. The site list below still
          works.
        </p>
      )}
      {/* Caption wording chosen by Kaitlin (2026-11-15); expert detail behind "Details". */}
      <p className="globe-caption">
        Near the Moon's south pole the Sun skims the horizon, so a few metres of height or a nearby
        hill decide between light and shadow. Choose a site to see it worked out from our own terrain
        calculations; the globe itself is just for finding your way.
      </p>
      <details className="globe-details">
        <summary>Details</summary>
        <p>
          The 3D Moon is Cesium's model (imagery and LOLA terrain), used for display only. Its terrain
          sits about 2.5 km above the LOLA heights our calculations use, so site markers are placed on
          its rendered surface and no values are taken from it. Every number in this tool comes from our
          own API.
        </p>
      </details>
      <h3 className="list-heading">Curated sites</h3>
      {data.sites.length === 0 ? <p className="muted">No curated sites.</p> : <SiteList sites={data.sites} />}
    </section>
  )
}
