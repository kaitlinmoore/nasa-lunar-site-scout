// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// Static fallback (plan §4.7; Kaitlin, 2026-11-15: the web switches over, with a visible notice).
// At web deploy, C api exports the API's served results as static JSON under /static-api/ on the
// web host (index.json = contract StaticIndex; paths are relative to it). When the live API gives
// no usable answer (no connection, 5xx), the web reads these files instead and says so.
// Firebase answers a missing file with the web page itself (status 200), so every file's content
// type is checked: anything that isn't JSON counts as missing.
import { useSyncExternalStore } from 'react'
import { scenarioId } from '../scenario'
import {
  ApiError,
  type CompareResponse,
  type HorizonProfile,
  type MetricsResponse,
  type Scenario,
  type ScenariosResponse,
  type SeriesResponse,
  type Schemas,
  type StaticNLEntry,
  type SitesResponse,
} from './client'
import type { ComparisonResult } from './compare'

type StaticIndex = Schemas['StaticIndex']

/** Where the static copy lives: same host as the web, under /static-api/. */
export const STATIC_BASE = `${import.meta.env.BASE_URL}static-api/`

const NOT_IN_COPY =
  "Not in the saved copy of our results, so it can't be shown while the live server isn't answering."

async function getStaticJson<T>(path: string): Promise<T> {
  const res = await fetch(`${STATIC_BASE}${path}`)
  const type = res.headers.get('content-type') ?? ''
  if (!res.ok || !type.includes('application/json')) {
    throw new Error(`saved copy: ${path} isn't available (HTTP ${res.status}, ${type || 'no content type'})`)
  }
  return (await res.json()) as T
}

let index: Promise<StaticIndex> | null = null

/** The static index, fetched once (and again after a failure). */
function staticIndex(): Promise<StaticIndex> {
  if (!index) {
    index = getStaticJson<StaticIndex>('index.json').catch((e: unknown) => {
      index = null
      throw e
    })
  }
  return index
}

function entryFor(idx: StaticIndex, scenario: Scenario) {
  const id = scenarioId(scenario)
  return idx.scenarios.find((e) => scenarioId(e.scenario) === id)
}

/** Terrain views (contract 0.13.0): the copy's TerrainViewsResponse; images at terrain_view/{site}/{view}/{layer}.png. */
export async function staticTerrainViews(): Promise<Schemas['TerrainViewsResponse']> {
  const path = (await staticIndex()).terrain_views
  if (!path) throw new Error('saved copy: no terrain views')
  return getStaticJson<Schemas['TerrainViewsResponse']>(path)
}

export async function staticSites(): Promise<SitesResponse> {
  return getStaticJson<SitesResponse>((await staticIndex()).sites)
}

/**
 * The scenario list, as GET /api/scenarios returns it: the copy's own file (0.11.0), or, in an
 * older copy, built from its entries that name their curated site.
 */
export async function staticScenarios(): Promise<ScenariosResponse> {
  const idx = await staticIndex()
  if (idx.scenario_list) return getStaticJson<ScenariosResponse>(idx.scenario_list)
  return {
    contract_version: idx.contract_version,
    _placeholder: idx._placeholder,
    _note: idx._note,
    scenarios: idx.scenarios
      .filter((e) => e.site_id)
      .map((e) => ({
        site_id: e.site_id ?? null,
        scenario_key: e.scenario_key,
        scenario: e.scenario,
        has_horizon: !!e.horizon,
      })),
  }
}

export async function staticMetrics(scenario: Scenario): Promise<MetricsResponse> {
  const entry = entryFor(await staticIndex(), scenario)
  if (!entry) throw new Error(NOT_IN_COPY)
  return getStaticJson<MetricsResponse>(entry.metrics)
}

/** The cached showcase questions (C8; contract 0.12.0), each with the request it answers. */
export async function staticNlExamples(): Promise<StaticNLEntry[]> {
  return (await staticIndex()).nl_answers ?? []
}

/** One cached answer file: what POST /api/nl returns for that example's request. */
export function staticNlAnswer(path: string): Promise<unknown> {
  return getStaticJson<unknown>(path)
}

/** One scenario's series alone (for a location and height without a horizon profile). */
export async function staticSeries(scenario: Scenario): Promise<SeriesResponse> {
  const entry = entryFor(await staticIndex(), scenario)
  if (!entry) throw new Error(NOT_IN_COPY)
  return getStaticJson<SeriesResponse>(entry.series)
}

export async function staticSky(
  scenario: Scenario,
): Promise<{ series: SeriesResponse; horizon: HorizonProfile }> {
  const entry = entryFor(await staticIndex(), scenario)
  if (!entry || !entry.horizon) throw new Error(NOT_IN_COPY)
  const [series, horizon] = await Promise.all([
    getStaticJson<SeriesResponse>(entry.series),
    getStaticJson<HorizonProfile>(entry.horizon),
  ])
  return { series, horizon }
}

export async function staticCompare(scenarios: Scenario[]): Promise<ComparisonResult> {
  const idx = await staticIndex()
  const items = await Promise.all(
    scenarios.map((s) => {
      const entry = entryFor(idx, s)
      return entry ? getStaticJson<MetricsResponse>(entry.metrics) : Promise.resolve(null)
    }),
  )
  const meta: Pick<CompareResponse, 'contract_version' | '_placeholder' | '_note'> = idx
  return {
    meta,
    items,
    reasons: items.map((item) => (item ? null : NOT_IN_COPY)),
    noneReason: items.every((item) => item === null) ? NOT_IN_COPY : null,
  }
}

/** Whether a live failure should switch to the static copy: no answer, or a server error (5xx). */
export function shouldFallBack(e: unknown): boolean {
  if (!(e instanceof ApiError)) return false
  const p = e.problem
  return p.kind === 'network' || p.kind === 'unavailable' || (p.kind === 'http' && p.status >= 500)
}

// ---- "showing the saved copy" state, for the visible notice ----

let usingCopy = false
const listeners = new Set<() => void>()

function markUsingCopy() {
  if (usingCopy) return
  usingCopy = true
  for (const l of listeners) l()
}

/** True once any part of the page is showing the static copy. */
export function useUsingStaticCopy(): boolean {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l)
      return () => listeners.delete(l)
    },
    () => usingCopy,
  )
}

/** Try the live API; if it gives no usable answer, use the static copy (and say so). */
export async function withStaticFallback<T>(live: () => Promise<T>, copy: () => Promise<T>): Promise<T> {
  try {
    return await live()
  } catch (e) {
    if (!shouldFallBack(e)) throw e
    let result: T
    try {
      result = await copy()
    } catch {
      throw e // the copy couldn't help either: show the live failure
    }
    markUsingCopy()
    return result
  }
}
