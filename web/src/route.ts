// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// Minimal URL routing (no router dependency): `?site=<id>` opens that site's screen; no `site`
// shows the globe (C7a). Other query params (e.g. `?source=fixtures`) are kept when navigating,
// and the browser's back/forward buttons work.
import { useEffect, useState } from 'react'

export type Route = { view: 'globe' } | { view: 'site'; siteId: string }

export function currentRoute(): Route {
  const siteId = new URLSearchParams(window.location.search).get('site')
  return siteId ? { view: 'site', siteId } : { view: 'globe' }
}

/** URL for a route, keeping the other query params. */
export function routeHref(route: Route): string {
  const params = new URLSearchParams(window.location.search)
  if (route.view === 'site') params.set('site', route.siteId)
  else params.delete('site')
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
