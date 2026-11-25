// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// Collapsible sections of the site page (the project author's idea): which ones exist, which
// start open, and the visitor's choices kept in this browser (the project author, 2026-11-23: all open
// except Events and Terrain fidelity; remembered per browser, the same for every site). The card
// itself is Section.tsx.
import { createContext } from 'react'

/** Sections of the site page that can be collapsed. */
export type SectionId =
  | 'about'
  | 'scenario'
  | 'sky'
  | 'power'
  | 'comms'
  | 'events'
  | 'fidelity'
  | 'terrain'
  | 'questions'

/** Which sections start open (a visitor's own choice wins, since it's remembered). */
export const SECTION_DEFAULTS: Record<SectionId, boolean> = {
  about: true,
  scenario: true,
  sky: true,
  power: true,
  comms: true,
  events: false,
  fidelity: false,
  terrain: true,
  questions: true,
}

/** Remember open/closed per section in this browser (same for every site). */
const REMEMBER_SECTIONS = true
const STORAGE_KEY = 'lunar-site-scout.sections.v1'

/** True where sections may collapse (the site page); false or absent elsewhere. */
export const CollapsibleSections = createContext(false)

/** Only the sections the visitor toggled are stored, so the defaults apply to the rest. */
export function readStored(): Partial<Record<SectionId, boolean>> {
  if (!REMEMBER_SECTIONS) return {}
  try {
    const parsed: unknown = JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? '{}')
    return parsed && typeof parsed === 'object' ? (parsed as Partial<Record<SectionId, boolean>>) : {}
  } catch {
    return {}
  }
}

export function storeSection(id: SectionId, open: boolean) {
  if (!REMEMBER_SECTIONS) return
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...readStored(), [id]: open }))
  } catch {
    // Storage unavailable (private mode, quota): the choice lasts for this page only.
  }
}

export function initialOpen(id: SectionId): boolean {
  const stored = readStored()[id]
  return typeof stored === 'boolean' ? stored : SECTION_DEFAULTS[id]
}

