// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// Saved items: pinned sites and saved scenarios as one portable JSON document,
// kept in browser storage and exported/imported as a file in the same format. A comparison is
// the list of saved scenarios selected for it (`compare_ids`).
import { useSyncExternalStore } from 'react'
import type { Scenario, SiteLocation } from '../api/client'
import { scenarioId, validateLocation, validateScenario } from '../scenario'

export const SAVED_FORMAT = 'lunar-site-scout.saved'
export const SAVED_VERSION = 1
const STORAGE_KEY = 'lunar-site-scout.saved.v1'

export type PinnedSite = { site_id: string; name: string; location: SiteLocation; pinned_at: string }
export type SavedScenario = {
  /** structural id (scenario.ts), unique within the document */
  id: string
  /** what the user sees in lists, e.g. the site name */
  label: string
  /** curated site id, when the scenario was made from one */
  site_id: string | null
  saved_at: string
  scenario: Scenario
}
export type SavedDoc = {
  format: typeof SAVED_FORMAT
  version: typeof SAVED_VERSION
  pinned_sites: PinnedSite[]
  scenarios: SavedScenario[]
  /** the current comparison: saved scenario ids, in column order */
  compare_ids: string[]
}

export function emptyDoc(): SavedDoc {
  return { format: SAVED_FORMAT, version: SAVED_VERSION, pinned_sites: [], scenarios: [], compare_ids: [] }
}

export type Rejected = { what: string; reason: string }

/**
 * Validate a parsed document. Items that fail are listed in `rejected` with the reason (never
 * dropped silently). A wrong format or version rejects the whole document.
 */
export function parseDoc(raw: unknown): { doc: SavedDoc; rejected: Rejected[] } | { error: string } {
  if (typeof raw !== 'object' || raw === null) return { error: 'not a JSON object' }
  const o = raw as Record<string, unknown>
  if (o.format !== SAVED_FORMAT)
    return { error: `not a saved-items file (format should be "${SAVED_FORMAT}")` }
  if (o.version !== SAVED_VERSION) {
    return { error: `unsupported version ${String(o.version)} (this app reads version ${SAVED_VERSION})` }
  }
  const doc = emptyDoc()
  const rejected: Rejected[] = []

  const pins = Array.isArray(o.pinned_sites) ? o.pinned_sites : []
  pins.forEach((p: unknown, i) => {
    const r = p as Record<string, unknown> | null
    const loc = validateLocation(r?.location)
    if (!r || typeof r.site_id !== 'string' || typeof r.name !== 'string') {
      rejected.push({ what: `pinned site ${i + 1}`, reason: 'needs site_id and name' })
    } else if ('error' in loc) {
      rejected.push({ what: `pinned site "${r.name}"`, reason: loc.error })
    } else if (doc.pinned_sites.some((x) => x.site_id === r.site_id)) {
      rejected.push({ what: `pinned site "${r.name}"`, reason: 'listed twice' })
    } else {
      doc.pinned_sites.push({
        site_id: r.site_id,
        name: r.name,
        location: loc.ok,
        pinned_at: typeof r.pinned_at === 'string' ? r.pinned_at : new Date().toISOString(),
      })
    }
  })

  const items = Array.isArray(o.scenarios) ? o.scenarios : []
  items.forEach((it: unknown, i) => {
    const r = it as Record<string, unknown> | null
    const label = typeof r?.label === 'string' && r.label ? r.label : `scenario ${i + 1}`
    const v = validateScenario(r?.scenario)
    if ('error' in v) {
      rejected.push({ what: `scenario "${label}"`, reason: v.error })
      return
    }
    const id = scenarioId(v.ok)
    if (doc.scenarios.some((x) => x.id === id)) {
      rejected.push({ what: `scenario "${label}"`, reason: 'same scenario listed twice' })
      return
    }
    doc.scenarios.push({
      id,
      label,
      site_id: typeof r?.site_id === 'string' ? r.site_id : null,
      saved_at: typeof r?.saved_at === 'string' ? r.saved_at : new Date().toISOString(),
      scenario: v.ok,
    })
  })

  // Keep only comparison ids that point at a scenario we kept.
  const ids = new Set(doc.scenarios.map((s) => s.id))
  doc.compare_ids = (Array.isArray(o.compare_ids) ? o.compare_ids : []).filter(
    (x): x is string => typeof x === 'string' && ids.has(x),
  )
  return { doc, rejected }
}

/** The document as a file: pretty JSON with an export time. */
export function exportJson(doc: SavedDoc): string {
  return JSON.stringify({ ...doc, exported_at: new Date().toISOString() }, null, 2)
}

export type ImportReport = { added: number; alreadySaved: number; pinsAdded: number; rejected: Rejected[] }

/** Merge an imported document into the current one; nothing already saved is overwritten. */
export function mergeDocs(
  current: SavedDoc,
  incoming: SavedDoc,
): { doc: SavedDoc; added: number; alreadySaved: number; pinsAdded: number } {
  const have = new Set(current.scenarios.map((s) => s.id))
  const newScenarios = incoming.scenarios.filter((s) => !have.has(s.id))
  const havePins = new Set(current.pinned_sites.map((p) => p.site_id))
  const newPins = incoming.pinned_sites.filter((p) => !havePins.has(p.site_id))
  return {
    doc: {
      ...current,
      scenarios: [...current.scenarios, ...newScenarios],
      pinned_sites: [...current.pinned_sites, ...newPins],
    },
    added: newScenarios.length,
    alreadySaved: incoming.scenarios.length - newScenarios.length,
    pinsAdded: newPins.length,
  }
}

// ---- browser storage + subscription (shared across components and tabs) ----

type State = { doc: SavedDoc; storageError: string | null }

function describeRejected(rejected: Rejected[]): string {
  return rejected.map((r) => `${r.what} (${r.reason})`).join('; ')
}

function readStorage(): State {
  let text: string | null
  try {
    text = window.localStorage.getItem(STORAGE_KEY)
  } catch (e) {
    return { doc: emptyDoc(), storageError: `browser storage unavailable: ${String(e)}` }
  }
  if (text === null) return { doc: emptyDoc(), storageError: null }
  try {
    const parsed = parseDoc(JSON.parse(text))
    if ('error' in parsed) throw new Error(parsed.error)
    return {
      doc: parsed.doc,
      storageError: parsed.rejected.length
        ? `some stored items were invalid and are not shown: ${describeRejected(parsed.rejected)}`
        : null,
    }
  } catch (e) {
    // Keep the unreadable data under a backup key rather than overwriting it.
    try {
      window.localStorage.setItem(`${STORAGE_KEY}.unreadable-${Date.now()}`, text)
    } catch {
      // nothing more we can do; the error below says what happened
    }
    return {
      doc: emptyDoc(),
      storageError:
        `stored saved items couldn't be read (${e instanceof Error ? e.message : String(e)}); ` +
        'a backup copy was kept in browser storage',
    }
  }
}

let state: State | null = null
const listeners = new Set<() => void>()

function current(): State {
  if (state === null) state = readStorage()
  return state
}

function emit() {
  for (const l of listeners) l()
}

function write(doc: SavedDoc) {
  let storageError: string | null = null
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(doc))
  } catch (e) {
    storageError =
      `couldn't save to browser storage (${String(e)}); ` +
      'changes last only until the page is closed. Export to keep them.'
  }
  state = { doc, storageError }
  emit()
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  const onStorage = (e: StorageEvent) => {
    if (e.key === STORAGE_KEY) {
      state = readStorage()
      emit()
    }
  }
  window.addEventListener('storage', onStorage) // other tabs
  return () => {
    listeners.delete(listener)
    window.removeEventListener('storage', onStorage)
  }
}

/** The saved document (live), any storage problem, and the actions that change it. */
export function useSaved() {
  const s = useSyncExternalStore(subscribe, current)
  const doc = s.doc
  return {
    doc,
    storageError: s.storageError,
    isPinned: (siteId: string) => doc.pinned_sites.some((p) => p.site_id === siteId),
    isSaved: (scenario: Scenario) => doc.scenarios.some((x) => x.id === scenarioId(scenario)),
    pinSite: (site: { id: string; name: string; location: SiteLocation }) => {
      if (doc.pinned_sites.some((p) => p.site_id === site.id)) return
      write({
        ...doc,
        pinned_sites: [
          ...doc.pinned_sites,
          { site_id: site.id, name: site.name, location: site.location, pinned_at: new Date().toISOString() },
        ],
      })
    },
    unpinSite: (siteId: string) =>
      write({ ...doc, pinned_sites: doc.pinned_sites.filter((p) => p.site_id !== siteId) }),
    /** Save a scenario; returns false (and changes nothing) if it's invalid or already saved. */
    saveScenario: (
      scenario: Scenario,
      label: string,
      siteId: string | null,
    ): { saved: boolean; reason?: string } => {
      const v = validateScenario(scenario)
      if ('error' in v) return { saved: false, reason: v.error }
      const id = scenarioId(v.ok)
      if (doc.scenarios.some((x) => x.id === id)) return { saved: false, reason: 'already saved' }
      write({
        ...doc,
        scenarios: [
          ...doc.scenarios,
          { id, label, site_id: siteId, saved_at: new Date().toISOString(), scenario: v.ok },
        ],
      })
      return { saved: true }
    },
    removeScenario: (id: string) =>
      write({
        ...doc,
        scenarios: doc.scenarios.filter((x) => x.id !== id),
        compare_ids: doc.compare_ids.filter((x) => x !== id),
      }),
    setCompareIds: (ids: string[]) => write({ ...doc, compare_ids: ids }),
    /** Parse, validate and merge a file's text; returns a report or an error. */
    importText: (text: string): ImportReport | { error: string } => {
      let raw: unknown
      try {
        raw = JSON.parse(text)
      } catch {
        return { error: "the file isn't valid JSON" }
      }
      const parsed = parseDoc(raw)
      if ('error' in parsed) return parsed
      const merged = mergeDocs(doc, parsed.doc)
      write(merged.doc)
      return {
        added: merged.added,
        alreadySaved: merged.alreadySaved,
        pinsAdded: merged.pinsAdded,
        rejected: parsed.rejected,
      }
    },
  }
}
