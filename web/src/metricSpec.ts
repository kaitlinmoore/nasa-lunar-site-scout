// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// Metric specs shared by the site screen and the comparison (C6): row order, labels, which flag
// qualifies which field, and the contract's field descriptions. Components are in metrics.tsx.
import type { CommsMetrics, PowerMetrics } from './api/client'
import { NO_EARTHSET_IN_WINDOW, NO_SUNSET_IN_WINDOW } from './format'

export const DOCS = __FIELD_DOCS__

// Boolean flags that qualify another metric rather than being shown as their own row.
type PowerClippedFlag = 'longest_shadow_clipped'
type CommsClippedFlag = 'longest_earth_gap_clipped'
type PowerInWindowFlag = 'sunset_in_window'
type CommsInWindowFlag = 'earthset_in_window'
type PowerFlag = PowerClippedFlag | PowerInWindowFlag
type CommsFlag = CommsClippedFlag | CommsInWindowFlag

/** An "event occurs in the window" flag: when false, its time-to field is null by contract. */
export type InWindow<T> = { field: keyof T; none: string }

/** Everything needed to render one metric group (power or comms). */
export type MetricSpec<T> = {
  /** contract schema name, for the field descriptions */
  schema: string
  /** row order and labels; flags are not rows */
  labels: Partial<Record<keyof T, string>>
  /** clipped flag field -> the duration field it qualifies */
  clipped: Partial<Record<keyof T, keyof T>>
  /** in-window flag field -> the time-to field it explains when null */
  inWindow: Partial<Record<keyof T, InWindow<T>>>
}

// Labels are keyed by the contract types (minus the flags): a renamed or added field is a
// type error here. Every flag must be placed in its map.
const POWER_LABELS: Record<Exclude<keyof PowerMetrics, PowerFlag>, string> = {
  illumination_fraction: 'Illumination',
  mean_visible_disk_fraction: 'Mean visible solar disc',
  sunlit_duration_h: 'Sunlit duration',
  longest_sunlit_period_h: 'Longest sunlit period',
  longest_shadow_h: 'Longest shadow',
  shadow_count: 'Shadow periods',
  sun_elevation_deg: 'Sun elevation',
  sun_azimuth_deg: 'Sun azimuth',
  time_to_sunset_h: 'Time to sunset',
}
const POWER_CLIPPED: Record<PowerClippedFlag, keyof PowerMetrics> = {
  longest_shadow_clipped: 'longest_shadow_h',
}
// Contract 0.4.0: when the flag is false the time-to value is null because the event doesn't
// happen in the window. That's a result ("no sunset in this window"), not "not computed".
const POWER_IN_WINDOW: Record<PowerInWindowFlag, InWindow<PowerMetrics>> = {
  sunset_in_window: { field: 'time_to_sunset_h', none: NO_SUNSET_IN_WINDOW },
}

const COMMS_LABELS: Record<Exclude<keyof CommsMetrics, CommsFlag>, string> = {
  earth_visibility_fraction: 'Earth visibility',
  earth_full_disc_fraction: 'Earth full disc',
  longest_earth_gap_h: 'Longest Earth gap',
  earth_elevation_deg: 'Earth elevation',
  earth_clearance_deg: 'Earth clearance',
  sun_earth_overlap_fraction: 'Sun + Earth overlap',
  time_to_earthset_h: 'Time to Earthset',
}
const COMMS_CLIPPED: Record<CommsClippedFlag, keyof CommsMetrics> = {
  longest_earth_gap_clipped: 'longest_earth_gap_h',
}
const COMMS_IN_WINDOW: Record<CommsInWindowFlag, InWindow<CommsMetrics>> = {
  earthset_in_window: { field: 'time_to_earthset_h', none: NO_EARTHSET_IN_WINDOW },
}

export const POWER_SPEC: MetricSpec<PowerMetrics> = {
  schema: 'PowerMetrics',
  labels: POWER_LABELS,
  clipped: POWER_CLIPPED,
  inWindow: POWER_IN_WINDOW,
}
export const COMMS_SPEC: MetricSpec<CommsMetrics> = {
  schema: 'CommsMetrics',
  labels: COMMS_LABELS,
  clipped: COMMS_CLIPPED,
  inWindow: COMMS_IN_WINDOW,
}

/** Row fields of a metric group, in display order. */
export function metricFields<T>(spec: MetricSpec<T>): (keyof T & string)[] {
  return Object.keys(spec.labels) as (keyof T & string)[]
}

/** The contract's description of a field, if it has one. */
export function fieldDoc(schema: string, field: string): string | undefined {
  return DOCS[schema]?.[field]
}

/** Scenario window, for values (counts) that only make sense with the window they cover. */
export type ScenarioWindow = { start: string; end: string }
