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
  type MetricsResponse,
  type Scenario,
  type Schemas,
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

export async function staticSites(): Promise<SitesResponse> {
  return getStaticJson<SitesResponse>((await staticIndex()).sites)
}

export async function staticMetrics(scenario: Scenario): Promise<MetricsResponse> {
  const entry = entryFor(await staticIndex(), scenario)
  if (!entry) throw new Error(NOT_IN_COPY)
  return getStaticJson<MetricsResponse>(entry.metrics)
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
