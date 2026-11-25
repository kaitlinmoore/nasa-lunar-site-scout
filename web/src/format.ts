// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
import { durationSeconds } from './scenario'

// Display formatting. Units follow the contract's field-name convention
// (lss/contract/models.py: degrees and meters unless the name says `_h`, `_km`, ...).
// Only values the API sent are formatted; nothing is defaulted. The one kind of derived value
// allowed is plain arithmetic on what the API sent, e.g. a window's length (the project author, 2026-11-15).
// The project author's display decisions (2026-11-15): fractions as percent; precision h 1 dp, deg 2 dp,
// % 1 dp; coordinates signed as sent; counts name what they count and the time window they cover;
// "Time window" (not "window"), range first with exact UTC times second, step as "results every …".
// Lengths (`_m`) of 1000 m or more in km, e.g. a 10000 m radius as "10 km" (2026-11-23).
// Layout lives in the components and styling in index.css; all text formatting lives here.

export type Unit = 'h' | 'deg' | 'fraction' | 'count' | 'm'

/** Unit of a metric field, from its name suffix. */
export function unitOf(field: string): Unit {
  if (field.endsWith('_h')) return 'h'
  if (field.endsWith('_deg')) return 'deg'
  if (field.endsWith('_fraction')) return 'fraction'
  if (field.endsWith('_count')) return 'count'
  if (field.endsWith('_m')) return 'm'
  throw new Error(`no unit convention for field ${field}`)
}

/** What a count field counts, [singular, plural]. A count field without an entry is an error. */
const COUNT_NOUNS: Record<string, readonly [string, string]> = {
  shadow_count: ['shadow period', 'shadow periods'],
}

/** Value with its unit. Fractions (0..1) are shown as percent; counts name what they count. */
export function formatValue(value: number, unit: Unit, field: string): string {
  switch (unit) {
    case 'h':
      return `${value.toFixed(1)} h`
    case 'deg':
      return `${value.toFixed(2)}°`
    case 'fraction':
      return `${(value * 100).toFixed(1)} %`
    case 'count': {
      const nouns = COUNT_NOUNS[field]
      if (!nouns) throw new Error(`no count noun for field ${field}`)
      return `${value} ${value === 1 ? nouns[0] : nouns[1]}`
    }
    case 'm':
      return formatMetres(value)
  }
}

/**
 * A length sent in metres: below 1000 m as sent ("236.901 m"), from 1000 m in km ("10 km",
 * "12.5 km"). The km value is the metres divided by 1000, not rounded (toPrecision(12) only drops
 * binary noise such as 1.2345000000000002).
 */
export function formatMetres(value: number): string {
  if (Math.abs(value) < 1000) return `${value} m`
  return `${Number((value / 1000).toPrecision(12))} km`
}

/** ISO 8601 UTC timestamp as "2028-11-23 06:00 UTC" (seconds shown only when non-zero). */
export function formatUtc(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const s = d.toISOString() // always UTC
  const secs = s.slice(17, 19)
  return `${s.slice(0, 10)} ${s.slice(11, 16)}${secs === '00' ? '' : `:${secs}`} UTC`
}

/** Simple ISO 8601 durations ("PT6H", "PT30M", "P1D") as "6 h"; anything else as sent. */
export function formatDuration(iso: string): string {
  const m = /^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$/.exec(iso)
  if (!m || iso === 'P' || iso === 'PT') return iso
  const parts = [m[1] && `${m[1]} d`, m[2] && `${m[2]} h`, m[3] && `${m[3]} min`, m[4] && `${m[4]} s`].filter(
    Boolean,
  )
  return parts.join(' ')
}

/** Planetocentric latitude/longitude (east-positive), signed degrees exactly as sent. */
export function formatLatLon(lat: number, lon: number): string {
  return `${lat}° lat, ${lon}° lon`
}

/** Height above the DEM surface, exactly as sent. */
export function formatHeight(m: number): string {
  return `${m} m`
}

/** The time window a count covers: "in this time window (15 May – 14 Jun 2028)". */
export function formatWindowQualifier(start: string, end: string): string {
  return `in this time window (${formatDateRange(start, end)})`
}

/** A contract description used mid-sentence ("Refined between ..." -> "refined between ..."). */
export function midSentence(description: string): string {
  return description.charAt(0).toLowerCase() + description.slice(1)
}

/** Compass point for an azimuth tick on the sky plot ("0° N", "90° E"); other ticks as plain degrees. */
export function formatAzimuthTick(az: number): string {
  const points: Record<number, string> = { 0: 'N', 90: 'E', 180: 'S', 270: 'W', 360: 'N' }
  return points[az] ? `${az}° ${points[az]}` : `${az}°`
}

/** Elevation axis tick, e.g. "-2°". */
export function formatElevationTick(el: number): string {
  return `${el}°`
}

/** Which sample is selected, e.g. "sample 25 of 721". */
export function formatSamplePosition(index: number, count: number): string {
  return `sample ${index + 1} of ${count}`
}

/**
 * Azimuth of the horizon-profile sample a lookup used, e.g. "profile sample at 133.40° az".
 * Works for any profile spacing (the API's real horizon is 0.1°); degree precision as elsewhere.
 */
export function formatProfileSample(az: number): string {
  return `profile sample at ${formatValue(az, 'deg', 'azimuth_deg')} az`
}

/** Where an interpolated horizon value came from, e.g. "linear between samples at 133.40° and 133.50° az". */
export function formatInterpolatedBetween(azLo: number, azHi: number): string {
  const f = (a: number) => formatValue(a, 'deg', 'azimuth_deg')
  return `linear between samples at ${f(azLo)} and ${f(azHi)} az`
}

/** Terrain layer line, e.g. "pgda_78_site_dems: near field, 5 m, to 10 km". */
export function formatTerrainLayer(layer: {
  dataset_id: string
  role: string
  resolution_m: number
  max_range_km?: number | null
}): string {
  const role = layer.role.replace('_', ' ')
  const range = layer.max_range_km == null ? '' : `, to ${layer.max_range_km} km`
  return `${layer.dataset_id}: ${role}, ${layer.resolution_m} m${range}`
}

/** Display names for event kinds (contract `EventKind`). */
export const EVENT_LABELS: Record<'sunrise' | 'sunset' | 'earthrise' | 'earthset', string> = {
  sunrise: 'Sunrise',
  sunset: 'Sunset',
  earthrise: 'Earthrise',
  earthset: 'Earthset',
}

/** Under a longest-period duration whose `_clipped` flag is true (contract 0.3.0). */
export const CLIPPED_NOTE = 'clipped to the window; the full period is longer'
/** Under a longest-period duration whose `_clipped` flag is null. */
export const CLIPPED_UNKNOWN_NOTE = 'whether it runs past the window: not computed'

/** time_to_sunset_h is null because sunset_in_window is false (contract 0.4.0). */
export const NO_SUNSET_IN_WINDOW = 'no sunset in this time window'
/** time_to_earthset_h is null because earthset_in_window is false (contract 0.4.0). */
export const NO_EARTHSET_IN_WINDOW = 'no Earthset in this time window'

/**
 * One-line scenario summary in plain words, e.g. "1 m · 15 May – 14 Jun 2028 (30 days) · results
 * every hour". Show `formatExactRange` next to it where the exact times matter.
 */
export function formatScenarioSummary(s: {
  unit_height_m: number
  window_start: string
  window_end: string
  step: string
}): string {
  const range = `${formatDateRange(s.window_start, s.window_end)} (${formatLength(s.window_start, s.window_end)})`
  return `${formatHeight(s.unit_height_m)} · ${range} · ${formatStepPlain(s.step)}`
}

/** Plain names for Scenario fields, e.g. in "differs in: unit height, time window start". */
export const SCENARIO_FIELD_LABELS: Record<string, string> = {
  location: 'location',
  unit_height_m: 'unit height',
  window_start: 'time window start',
  window_end: 'time window end',
  step: 'how often results are given (step)',
}

/** A UTC time for a text field, written explicitly: "2028-05-15 00:00" (shown next to "UTC"). */
export function formatUtcInput(iso: string): string {
  const s = new Date(iso).toISOString()
  return `${s.slice(0, 10)} ${s.slice(11, 16)}`
}

/** "2028-05-15 00:00" (or "2028-05-15T00:00"), read as UTC -> "2028-05-15T00:00:00Z"; null if malformed. */
export function parseUtcInput(text: string): string | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})$/.exec(text.trim())
  if (!m) return null
  const iso = `${m[1]}-${m[2]}-${m[3]}T${m[4]}:${m[5]}:00Z`
  const d = new Date(iso)
  // Reject impossible dates like 2028-02-30 (Date would roll them over).
  return Number.isNaN(d.getTime()) || d.toISOString().slice(0, 16) !== iso.slice(0, 16) ? null : iso
}

// ---- Time window in plain words (the project author, 2026-11-15: "Time window"; range first, exact UTC
// times second; total length; step as "results every hour"). Length is plain arithmetic on the
// two times the API sent, which the project author allowed.

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function utcParts(iso: string) {
  const d = new Date(iso)
  return {
    y: d.getUTCFullYear(),
    m: d.getUTCMonth(),
    day: d.getUTCDate(),
    time: d.toISOString().slice(11, 19).replace(/:00$/, ''),
  }
}

/** Calendar range in words, UTC: "15 May – 14 Jun 2028", "1–14 May 2028", "28 Dec 2028 – 3 Jan 2029". */
export function formatDateRange(startIso: string, endIso: string): string {
  const a = utcParts(startIso)
  const b = utcParts(endIso)
  if (a.y !== b.y) return `${a.day} ${MONTHS[a.m]} ${a.y} – ${b.day} ${MONTHS[b.m]} ${b.y}`
  if (a.m !== b.m) return `${a.day} ${MONTHS[a.m]} – ${b.day} ${MONTHS[b.m]} ${b.y}`
  if (a.day !== b.day) return `${a.day}–${b.day} ${MONTHS[b.m]} ${b.y}`
  return `${a.day} ${MONTHS[a.m]} ${a.y}`
}

/** The exact start and end: "from 15 May 2028 00:00 UTC to 14 Jun 2028 00:00 UTC". */
export function formatExactRange(startIso: string, endIso: string): string {
  const f = (iso: string) => {
    const p = utcParts(iso)
    return `${p.day} ${MONTHS[p.m]} ${p.y} ${p.time} UTC`
  }
  return `from ${f(startIso)} to ${f(endIso)}`
}

/** Total length of a window: "30 days", "1 day", "30 days 6 h", "6 h 30 min", "45 min". */
export function formatLength(startIso: string, endIso: string): string {
  const totalMin = Math.round((Date.parse(endIso) - Date.parse(startIso)) / 60000)
  const days = Math.floor(totalMin / 1440)
  const hours = Math.floor((totalMin % 1440) / 60)
  const mins = totalMin % 60
  const parts = [
    days ? `${days} ${days === 1 ? 'day' : 'days'}` : '',
    hours ? `${hours} h` : '',
    mins ? `${mins} min` : '',
  ].filter(Boolean)
  return parts.length ? parts.join(' ') : '0 min'
}

/** The sampling step in plain words: "results every hour", "results every 6 hours", "results every day". */
export function formatStepPlain(step: string): string {
  const secs = durationSeconds(step)
  if (secs === null || secs <= 0) return `results every ${formatDuration(step)}`
  const unit = (n: number, one: string, many: string) => (n === 1 ? `every ${one}` : `every ${n} ${many}`)
  if (secs % 86400 === 0) return `results ${unit(secs / 86400, 'day', 'days')}`
  if (secs % 3600 === 0) return `results ${unit(secs / 3600, 'hour', 'hours')}`
  if (secs % 60 === 0) return `results ${unit(secs / 60, 'minute', 'minutes')}`
  return `results ${unit(secs, 'second', 'seconds')}`
}

/** Text cut at a word boundary to at most `max` characters, with "…" if anything was cut. */
export function truncateText(text: string, max: number): string {
  const t = text.trim()
  if (t.length <= max) return t
  const cut = t.slice(0, max)
  const space = cut.lastIndexOf(' ')
  return `${(space > max * 0.6 ? cut.slice(0, space) : cut).replace(/[\s,;:.–-]+$/, '')}…`
}

/** Menu label for the saved page: "Saved scenarios (2)"; no count when none are saved. */
export function formatSavedLabel(scenarioCount: number): string {
  return scenarioCount > 0 ? `Saved scenarios (${scenarioCount})` : 'Saved scenarios'
}
