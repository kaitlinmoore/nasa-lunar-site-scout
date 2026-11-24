// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// The scenario whose dashboard is on the site page, for NL answers that would otherwise repeat it
// (layout pass, deferred item 1: the site summary repeated the whole dashboard). Null where no
// dashboard is shown with the answer.
import { createContext } from 'react'
import type { Scenario } from '../api/client'

export const DashboardScenario = createContext<Scenario | null>(null)
