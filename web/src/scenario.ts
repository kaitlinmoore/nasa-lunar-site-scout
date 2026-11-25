// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// Scenario helpers for save + compare: validation that mirrors the contract's Scenario
// rules (lss/contract/models.py), and a structural id used to de-duplicate saved scenarios and
// to match fixture results. The id is web-side only; it is NOT the server's `scenario_key`.
import type { Scenario, SiteLocation } from './api/client'

/** Seconds in an ISO 8601 duration like "PT1H", "P1DT6H", "PT30M", "PT0.5S"; null if unsupported. */
export function durationSeconds(iso: string): number | null {
  const m =
    /^P(?:(\d+(?:\.\d+)?)D)?(?:T(?:(\d+(?:\.\d+)?)H)?(?:(\d+(?:\.\d+)?)M)?(?:(\d+(?:\.\d+)?)S)?)?$/.exec(iso)
  if (!m || iso === 'P' || iso.endsWith('T')) return null
  const [d, h, mi, s] = m.slice(1).map((x) => (x ? Number(x) : 0))
  return d * 86400 + h * 3600 + mi * 60 + s
}

/** An ISO 8601 timestamp with an explicit zone ("Z" or ±hh:mm), as the contract requires. */
function isAwareTimestamp(s: string): boolean {
  return (
    /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})$/.test(s) &&
    !Number.isNaN(Date.parse(s))
  )
}

const SCENARIO_KEYS = new Set(['location', 'unit_height_m', 'window_start', 'window_end', 'step'])
const LOCATION_KEYS = new Set(['lat', 'lon', 'name'])

/** Check a value against the contract's Location rules (unknown fields rejected). */
export function validateLocation(x: unknown): { ok: SiteLocation } | { error: string } {
  if (typeof x !== 'object' || x === null) return { error: 'location is missing' }
  const loc = x as Record<string, unknown>
  const extra = Object.keys(loc).filter((k) => !LOCATION_KEYS.has(k))
  if (extra.length) return { error: `unknown location field(s): ${extra.join(', ')}` }
  const { lat, lon, name } = loc
  if (typeof lat !== 'number' || !Number.isFinite(lat) || lat < -90 || lat > 90) {
    return { error: 'location.lat must be a number from -90 to 90' }
  }
  if (typeof lon !== 'number' || !Number.isFinite(lon) || lon < -180 || lon > 180) {
    return { error: 'location.lon must be a number from -180 to 180 (east-positive)' }
  }
  if (name !== undefined && name !== null && typeof name !== 'string') {
    return { error: 'location.name must be text' }
  }
  return { ok: { lat, lon, name: (name as string | null | undefined) ?? null } }
}

/**
 * Check a value against the contract's Scenario rules. Unknown fields are rejected, as the API
 * does (extra="forbid"). Returns the scenario with times normalized to UTC ("…Z"), or an error.
 */
export function validateScenario(x: unknown): { ok: Scenario } | { error: string } {
  if (typeof x !== 'object' || x === null) return { error: 'scenario is not an object' }
  const o = x as Record<string, unknown>
  const extra = Object.keys(o).filter((k) => !SCENARIO_KEYS.has(k))
  if (extra.length) return { error: `unknown scenario field(s): ${extra.join(', ')}` }

  const loc = validateLocation(o.location)
  if ('error' in loc) return loc

  const h = o.unit_height_m
  if (typeof h !== 'number' || !Number.isFinite(h) || h <= 0) {
    return { error: 'unit_height_m must be a number greater than 0' }
  }

  const { window_start: ws, window_end: we } = o
  if (typeof ws !== 'string' || !isAwareTimestamp(ws)) {
    return { error: 'window_start must be an ISO 8601 time with a zone (e.g. 2028-05-15T00:00:00Z)' }
  }
  if (typeof we !== 'string' || !isAwareTimestamp(we)) {
    return { error: 'window_end must be an ISO 8601 time with a zone (e.g. 2028-06-14T00:00:00Z)' }
  }
  if (Date.parse(we) <= Date.parse(ws)) return { error: 'window_end must be after window_start' }

  const step = o.step === undefined ? 'PT1H' : o.step // contract default: 1 h
  if (typeof step !== 'string') return { error: 'step must be an ISO 8601 duration (e.g. PT1H)' }
  const secs = durationSeconds(step)
  if (secs === null) return { error: `step "${step}" isn't a supported ISO 8601 duration (e.g. PT1H, P1D)` }
  if (secs <= 0) return { error: 'step must be positive' }

  return {
    ok: {
      location: loc.ok,
      unit_height_m: h,
      window_start: toUtcIso(ws),
      window_end: toUtcIso(we),
      step,
    },
  }
}

/** An aware ISO timestamp as UTC "YYYY-MM-DDTHH:MM:SSZ" (milliseconds kept only if non-zero). */
export function toUtcIso(s: string): string {
  const iso = new Date(s).toISOString()
  return iso.endsWith('.000Z') ? `${iso.slice(0, 19)}Z` : iso
}

/**
 * Structural id of a scenario: location (lat, lon), unit height, UTC window and step in seconds.
 * The location name is excluded, as in the server's key, so a renamed site keeps its id.
 */
export function scenarioId(s: Scenario): string {
  const step = durationSeconds(s.step)
  return [
    s.location.lat,
    s.location.lon,
    s.unit_height_m,
    new Date(s.window_start).toISOString(),
    new Date(s.window_end).toISOString(),
    step === null ? s.step : `${step}s`,
  ].join('|')
}
