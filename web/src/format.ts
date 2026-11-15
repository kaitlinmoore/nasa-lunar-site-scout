// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// Display formatting. Units follow the contract's field-name convention
// (lss/contract/models.py: degrees and meters unless the name says `_h`, `_km`, ...).
// Only values the API sent are formatted; nothing is derived or defaulted.
// Kaitlin's display decisions (2026-11-15): fractions as percent; precision h 1 dp, deg 2 dp,
// % 1 dp; coordinates signed as sent; counts name what they count and the window they cover.
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
      return `${value} m`
  }
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
  const parts = [
    m[1] && `${m[1]} d`,
    m[2] && `${m[2]} h`,
    m[3] && `${m[3]} min`,
    m[4] && `${m[4]} s`,
  ].filter(Boolean)
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

/**
 * The scenario window a count covers, as parts so the layout can keep each date unbroken:
 * { lead: "in the window", start: "2028-11-15 00:00", end: "2028-12-15 00:00 UTC" }.
 */
export function formatWindowQualifier(start: string, end: string) {
  return { lead: 'in the window', start: formatUtc(start).replace(/ UTC$/, ''), end: formatUtc(end) }
}

/** A contract description used mid-sentence ("Refined between ..." -> "refined between ..."). */
export function midSentence(description: string): string {
  return description.charAt(0).toLowerCase() + description.slice(1)
}
