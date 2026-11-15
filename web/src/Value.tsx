// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// One API value with its unit, or "not computed" for null (never 0). Hover shows the raw value.
import { formatValue, unitOf } from './format'

export function NotComputed() {
  return <span className="not-computed">not computed</span>
}

export function Num({
  value,
  field,
  origin = 'API value',
}: {
  value: number | null | undefined
  field: string
  /** What the hover text calls the raw number, e.g. "Interpolated from the API profile". */
  origin?: string
}) {
  if (value === null || value === undefined) return <NotComputed />
  return (
    <span className="value" title={`${origin}: ${value}`}>
      {formatValue(value, unitOf(field), field)}
    </span>
  )
}
