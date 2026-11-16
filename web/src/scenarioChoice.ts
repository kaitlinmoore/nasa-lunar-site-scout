// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// The site page's scenario picker (G2; Kaitlin approved a plain height / window picker, 2026-11-16):
// a site's precomputed scenarios (GET /api/scenarios, contract 0.11.0) grouped by time window, each
// with the unit heights it has. Pure, so it can be unit-tested in Node.
import type { components } from './api/schema'
import { durationSeconds } from './scenario'

type ScenarioEntry = components['schemas']['ScenarioEntry']

export type WindowOption = {
  /** Identifies the window (start, end, step); stable across reloads. */
  key: string
  window_start: string
  window_end: string
  step: string
  /** The heights this window has, lowest first, each with its scenario. */
  heights: { unit_height_m: number; entry: ScenarioEntry }[]
}

function windowKey(e: ScenarioEntry): string {
  const s = e.scenario
  const step = durationSeconds(s.step)
  return [
    new Date(s.window_start).toISOString(),
    new Date(s.window_end).toISOString(),
    step === null ? s.step : `${step}s`,
  ].join('|')
}

const windowLength = (w: WindowOption) => Date.parse(w.window_end) - Date.parse(w.window_start)

/**
 * The site's windows, shortest first (then earliest), so the default is the most detailed one;
 * heights lowest first. Entries for other sites are ignored.
 */
export function siteWindows(entries: ScenarioEntry[], siteId: string): WindowOption[] {
  const byKey = new Map<string, WindowOption>()
  for (const e of entries) {
    if (e.site_id !== siteId) continue
    const key = windowKey(e)
    let w = byKey.get(key)
    if (!w) {
      const s = e.scenario
      w = { key, window_start: s.window_start, window_end: s.window_end, step: s.step, heights: [] }
      byKey.set(key, w)
    }
    if (!w.heights.some((h) => h.unit_height_m === e.scenario.unit_height_m)) {
      w.heights.push({ unit_height_m: e.scenario.unit_height_m, entry: e })
    }
  }
  const windows = [...byKey.values()]
  for (const w of windows) w.heights.sort((a, b) => a.unit_height_m - b.unit_height_m)
  return windows.sort(
    (a, b) => windowLength(a) - windowLength(b) || Date.parse(a.window_start) - Date.parse(b.window_start),
  )
}

export type Choice = { windowKey: string; unit_height_m: number }

/**
 * The window the picker opens on when the site has it (Kaitlin, 2026-11-16): the 30 days from
 * 15 May 2028 (any step). The other windows are still offered.
 */
export const PREFERRED_WINDOW = { start: '2028-05-15T00:00:00Z', days: 30 }

const DAY_MS = 24 * 60 * 60 * 1000

function isPreferred(w: WindowOption): boolean {
  const start = Date.parse(PREFERRED_WINDOW.start)
  return (
    Date.parse(w.window_start) === start &&
    Date.parse(w.window_end) === start + PREFERRED_WINDOW.days * DAY_MS
  )
}

/** The window to open on: the preferred one if the site has it, else the shortest (the first). */
function defaultWindow(windows: WindowOption[]): WindowOption | undefined {
  return windows.find(isPreferred) ?? windows[0]
}

/** The default: the preferred window (else the shortest) at its lowest height. */
export function defaultChoice(windows: WindowOption[]): Choice | null {
  const w = defaultWindow(windows)
  return w && w.heights.length > 0 ? { windowKey: w.key, unit_height_m: w.heights[0].unit_height_m } : null
}

/**
 * The chosen window and height, made valid: an unknown window falls back to the default window,
 * and a height the window doesn't have falls back to that window's lowest height.
 */
export function resolveChoice(
  windows: WindowOption[],
  choice: Choice | null,
): { window: WindowOption; entry: ScenarioEntry } | null {
  const fallback = defaultChoice(windows)
  const want = choice ?? fallback
  if (!want) return null
  const window = windows.find((w) => w.key === want.windowKey) ?? defaultWindow(windows)
  if (!window) return null
  const height = window.heights.find((h) => h.unit_height_m === want.unit_height_m) ?? window.heights[0]
  return height ? { window, entry: height.entry } : null
}
