// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// What a site is called on screen (contract 0.9.0; Kaitlin, 2026-11-16): its `short_name`, with
// `subtitle` under it on the site card and panel, falling back to the full `name` when the short
// name is empty. Names come from the site list (/api/sites), never from results: a result's
// `location.name` is used only for a location that isn't a curated site.
import { createContext, useContext } from 'react'
import type { Site } from './api/client'
import { formatLatLon } from './format'

type NamedSite = Pick<Site, 'name' | 'short_name'>

/** The short name, else the full name. */
export function displayName(site: NamedSite): string {
  const short = site.short_name?.trim()
  return short ? short : site.name
}

/** The small line under the name on the card and panel, or null when there is none. */
export function subtitleOf(site: Pick<Site, 'subtitle'>): string | null {
  return site.subtitle?.trim() || null
}

export type SiteNames = {
  /** Display name of the curated site with this id; null when it isn't in the site list. */
  byId: (id: string) => string | null
  /** Display name of the curated site at exactly this location; null when there is none. */
  at: (location: { lat: number; lon: number }) => string | null
}

/** Name lookups over the site list (exact coordinates, as the site screen matches results). */
export function siteNames(sites: Site[]): SiteNames {
  const ids = new Map(sites.map((s) => [s.id, displayName(s)]))
  const places = new Map(sites.map((s) => [`${s.location.lat},${s.location.lon}`, displayName(s)]))
  return {
    byId: (id) => ids.get(id) ?? null,
    at: (l) => places.get(`${l.lat},${l.lon}`) ?? null,
  }
}

/** A location's label: the curated site's name, else the location's own name, else coordinates. */
export function placeLabel(
  names: SiteNames,
  location: { lat: number; lon: number; name?: string | null },
): string {
  return names.at(location) ?? location.name ?? formatLatLon(location.lat, location.lon)
}

/** The site list's names, provided by App once /api/sites has loaded (empty until then). */
export const SiteNamesContext = createContext<SiteNames>(siteNames([]))

export const useSiteNames = () => useContext(SiteNamesContext)
