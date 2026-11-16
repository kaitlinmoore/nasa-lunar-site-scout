// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// The site page's scenario picker (G2): a plain time-window and unit-height choice among the site's
// precomputed scenarios (Kaitlin approved it plain, 2026-11-16; polish waits for her layout pass).
// Only what is precomputed can be chosen: each window lists the heights it has.
import type { ScenarioEntry } from './api/client'
import { formatDateRange, formatHeight, formatLength, formatStepPlain } from './format'
import type { Choice, WindowOption } from './scenarioChoice'

export default function ScenarioPicker({
  windows,
  chosen,
  onChange,
}: {
  windows: WindowOption[]
  chosen: { window: WindowOption; entry: ScenarioEntry }
  onChange: (choice: Choice) => void
}) {
  const height = chosen.entry.scenario.unit_height_m
  const count = windows.reduce((n, w) => n + w.heights.length, 0)
  return (
    <form className="scenario-picker" aria-label="Precomputed scenario" onSubmit={(e) => e.preventDefault()}>
      <label>
        Time window
        <select
          value={chosen.window.key}
          onChange={(e) => onChange({ windowKey: e.target.value, unit_height_m: height })}
        >
          {windows.map((w) => (
            <option key={w.key} value={w.key}>
              {formatDateRange(w.window_start, w.window_end)} · {formatLength(w.window_start, w.window_end)} ·{' '}
              {formatStepPlain(w.step)}
            </option>
          ))}
        </select>
      </label>
      <label>
        Unit height
        <select
          value={String(height)}
          onChange={(e) => onChange({ windowKey: chosen.window.key, unit_height_m: Number(e.target.value) })}
        >
          {chosen.window.heights.map((h) => (
            <option key={h.unit_height_m} value={String(h.unit_height_m)}>
              {formatHeight(h.unit_height_m)}
            </option>
          ))}
        </select>
      </label>
      <span className="muted">
        {count} precomputed {count === 1 ? 'scenario' : 'scenarios'} for this site
      </span>
    </form>
  )
}
