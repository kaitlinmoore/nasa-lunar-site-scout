// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// Minimal URL routing (no router dependency): `?site=<id>` opens that site's screen,
// `?view=saved` the saved items and comparison; otherwise the globe. Other query
// params (e.g. `?source=fixtures`) are kept when navigating, and back/forward work.
import { useEffect, useState } from 'react'

export type Route = { view: 'globe' } | { view: 'site'; siteId: string } | { view: 'saved' }

export function currentRoute(): Route {
  const params = new URLSearchParams(window.location.search)
  const siteId = params.get('site')
  if (siteId) return { view: 'site', siteId }
  return params.get('view') === 'saved' ? { view: 'saved' } : { view: 'globe' }
}

/** URL for a route, keeping the other query params. */
export function routeHref(route: Route): string {
  const params = new URLSearchParams(window.location.search)
  params.delete('site')
  params.delete('view')
  if (route.view === 'site') params.set('site', route.siteId)
  if (route.view === 'saved') params.set('view', 'saved')
  const q = params.toString()
  return `${window.location.pathname}${q ? `?${q}` : ''}`
}

const ROUTE_EVENT = 'lss:route'

export function navigate(route: Route) {
  window.history.pushState(null, '', routeHref(route))
  window.dispatchEvent(new Event(ROUTE_EVENT))
}

/** The current route, updated on navigate() and on back/forward. */
export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(currentRoute)
  useEffect(() => {
    const update = () => setRoute(currentRoute())
    window.addEventListener('popstate', update)
    window.addEventListener(ROUTE_EVENT, update)
    return () => {
      window.removeEventListener('popstate', update)
      window.removeEventListener(ROUTE_EVENT, update)
    }
  }, [])
  return route
}
