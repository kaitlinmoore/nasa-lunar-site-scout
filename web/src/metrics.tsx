// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// Shared metric components: the value cell (stats, flags, counts, nulls). Used by the site
// screen and the comparison (C6) so a value reads the same everywhere. null = "not computed".
import type { Stat } from './api/client'
import { CLIPPED_NOTE, CLIPPED_UNKNOWN_NOTE, formatWindowQualifier, unitOf } from './format'
import { fieldDoc, type InWindow, type MetricSpec, type ScenarioWindow } from './metricSpec'
import { NotComputed, Num } from './Value'

function WindowQualifier({ start, end }: ScenarioWindow) {
  return <div className="definition">{formatWindowQualifier(start, end)}</div>
}

/** A number with its unit, or "not computed"; counts also name the window they cover. */
export function Value({
  value,
  field,
  scenarioWindow,
}: {
  value: number | null | undefined
  field: string
  scenarioWindow?: ScenarioWindow
}) {
  if (value === null || value === undefined) return <NotComputed />
  return (
    <>
      <Num value={value} field={field} />
      {unitOf(field) === 'count' && scenarioWindow && <WindowQualifier {...scenarioWindow} />}
    </>
  )
}

export function StatValue({ stat, field }: { stat: Stat | undefined; field: string }) {
  const parts = [
    ['min', stat?.min],
    ['mean', stat?.mean],
    ['max', stat?.max],
  ] as const
  return (
    <span className="stat">
      {parts.map(([name, v]) => (
        <span key={name}>
          <span className="stat-name">{name}</span> <Value value={v} field={field} />
        </span>
      ))}
    </span>
  )
}

function isStat(v: unknown): v is Stat {
  return typeof v === 'object' && v !== null
}

/**
 * Note under a duration whose period may run past the window edges. Shown only when the
 * duration has a value: true -> "clipped …"; null -> "not computed"; false -> nothing.
 */
function ClippedNote({ flag, doc }: { flag: boolean | null | undefined; doc?: string }) {
  if (flag === false) return null
  return (
    <div className="definition" title={doc}>
      {flag === true ? CLIPPED_NOTE : CLIPPED_UNKNOWN_NOTE}
    </div>
  )
}

/** One metric's value cell: stats, "no sunset in this window", clipped notes, counts, nulls. */
export function MetricValue<T extends object>({
  metrics,
  field,
  spec,
  scenarioWindow,
}: {
  metrics: T
  field: keyof T & string
  spec: MetricSpec<T>
  scenarioWindow: ScenarioWindow
}) {
  const v = metrics[field] as unknown
  if (isStat(v)) return <StatValue stat={v} field={field} />

  const clippedFlag = (Object.entries(spec.clipped) as [keyof T & string, keyof T][]).find(
    ([, target]) => target === field,
  )?.[0]
  const presence = (Object.entries(spec.inWindow) as [keyof T & string, InWindow<T>][]).find(
    ([, w]) => w.field === field,
  )
  if (v == null && presence && metrics[presence[0]] === false) {
    return (
      <span className="value" title={fieldDoc(spec.schema, presence[0])}>
        {presence[1].none}
      </span>
    )
  }
  return (
    <>
      <Value value={v as number | null | undefined} field={field} scenarioWindow={scenarioWindow} />
      {clippedFlag && v != null && (
        <ClippedNote
          flag={metrics[clippedFlag] as boolean | null | undefined}
          doc={fieldDoc(spec.schema, clippedFlag)}
        />
      )}
    </>
  )
}
