// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// C1 thin-slice site screen: one scenario's metrics, events and fidelity, exactly as the API
// (or fixture) sent them. null = "not computed", never 0. Definitions come from the contract.
import type { ReactNode } from 'react'
import type {
  CommsMetrics,
  FidelityLabel,
  MetricEvent,
  MetricsResponse,
  PowerMetrics,
  Stat,
} from './api/client'
import {
  EVENT_LABELS,
  CLIPPED_NOTE,
  CLIPPED_UNKNOWN_NOTE,
  formatDuration,
  formatHeight,
  formatLatLon,
  formatUtc,
  formatWindowQualifier,
  midSentence,
  unitOf,
} from './format'
import { NotComputed, Num } from './Value'

const DOCS = __FIELD_DOCS__

// Boolean flags that qualify another metric rather than being shown as their own row.
type PowerFlag = 'longest_shadow_clipped'
type CommsFlag = 'longest_earth_gap_clipped'

// Labels are keyed by the contract types (minus the flags): a renamed or added field is a
// type error here.
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

const COMMS_LABELS: Record<Exclude<keyof CommsMetrics, CommsFlag>, string> = {
  earth_visibility_fraction: 'Earth visibility',
  earth_full_disc_fraction: 'Earth full disc',
  longest_earth_gap_h: 'Longest Earth gap',
  earth_elevation_deg: 'Earth elevation',
  earth_clearance_deg: 'Earth clearance',
  sun_earth_overlap_fraction: 'Sun + Earth overlap',
  time_to_earthset_h: 'Time to Earthset',
}

// Which "clipped to the window" flag qualifies which duration (every flag must be placed).
const POWER_CLIPPED: Record<PowerFlag, keyof PowerMetrics> = {
  longest_shadow_clipped: 'longest_shadow_h',
}
const COMMS_CLIPPED: Record<CommsFlag, keyof CommsMetrics> = {
  longest_earth_gap_clipped: 'longest_earth_gap_h',
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

/** Scenario window, for values (counts) that only make sense with the window they cover. */
type ScenarioWindow = { start: string; end: string }

function WindowQualifier({ start, end }: ScenarioWindow) {
  const q = formatWindowQualifier(start, end)
  return (
    <div className="definition">
      {q.lead} <span className="nowrap">{q.start}</span> – <span className="nowrap">{q.end}</span>
    </div>
  )
}

function Value({
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

function StatValue({ stat, field }: { stat: Stat | undefined; field: string }) {
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

function MetricTable<T extends object>({
  title,
  schema,
  metrics,
  labels,
  clipped,
  scenarioWindow,
}: {
  title: string
  schema: string
  metrics: T
  labels: Partial<Record<keyof T, string>>
  /** flag field -> the duration field it qualifies */
  clipped: Partial<Record<keyof T, keyof T>>
  scenarioWindow: ScenarioWindow
}) {
  const docs = DOCS[schema] ?? {}
  // duration field -> its flag field
  const flagFor = new Map(
    (Object.entries(clipped) as [keyof T & string, keyof T & string][]).map(([flag, field]) => [field, flag]),
  )
  return (
    <section className="card">
      <h2>{title}</h2>
      <table className="metrics">
        <thead>
          <tr>
            <th scope="col">Metric</th>
            <th scope="col">Value</th>
          </tr>
        </thead>
        <tbody>
          {(Object.keys(labels) as (keyof T & string)[]).map((field) => {
            const v = metrics[field] as unknown
            const flag = flagFor.get(field)
            return (
              <tr key={field}>
                <th scope="row">
                  {labels[field]}
                  <div className="definition">
                    {docs[field] ?? <span className="no-def">No definition in the contract yet.</span>}
                  </div>
                </th>
                <td>
                  {isStat(v) ? (
                    <StatValue stat={v} field={field} />
                  ) : (
                    <>
                      <Value
                        value={v as number | null | undefined}
                        field={field}
                        scenarioWindow={scenarioWindow}
                      />
                      {flag && v != null && (
                        <ClippedNote flag={metrics[flag] as boolean | null | undefined} doc={docs[flag]} />
                      )}
                    </>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </section>
  )
}

function Events({ events, step }: { events: MetricEvent[]; step: string }) {
  const sorted = [...events].sort((a, b) => Date.parse(a.time) - Date.parse(b.time))
  const refinedDoc = DOCS.Event?.refined
  return (
    <section className="card">
      <h2>Events</h2>
      {sorted.length === 0 ? (
        <p className="muted">No events in this window.</p>
      ) : (
        <table className="events">
          <thead>
            <tr>
              <th scope="col">Event</th>
              <th scope="col">Time (UTC)</th>
              <th scope="col">Refined</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((e, i) => (
              <tr key={`${e.kind}-${e.time}-${i}`}>
                <td>{EVENT_LABELS[e.kind]}</td>
                <td className="value" title={`API value: ${e.time}`}>
                  {formatUtc(e.time)}
                </td>
                <td>
                  {e.refined ? <span className="badge">refined</span> : <span className="muted">no</span>}
                  {e.note && <div className="definition">{e.note}</div>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="definition">
        {refinedDoc && <>Refined: {midSentence(refinedDoc)}. </>}
        Sampling step: {formatDuration(step)}.
      </p>
    </section>
  )
}

function Fidelity({ fidelity }: { fidelity: FidelityLabel }) {
  return (
    <section className="card">
      <h2>Terrain fidelity</h2>
      <dl>
        <dt>Tier</dt>
        <dd>
          <span className={`badge tier-${fidelity.tier}`}>{fidelity.tier}</span>
        </dd>
        <dt>Summary</dt>
        <dd>{fidelity.summary}</dd>
        <dt>Near-field resolution</dt>
        <dd>
          <Value value={fidelity.near_field_resolution_m} field="near_field_resolution_m" />
        </dd>
        <dt>Far-field resolution</dt>
        <dd>
          <Value value={fidelity.far_field_resolution_m} field="far_field_resolution_m" />
        </dd>
      </dl>
    </section>
  )
}

/** The site screen; `children` (the sky view) renders between the scenario and the metrics. */
export default function SiteScreen({ data, children }: { data: MetricsResponse; children?: ReactNode }) {
  const { scenario } = data
  const { location } = scenario
  const heightDoc = DOCS.Scenario?.unit_height_m
  const scenarioWindow: ScenarioWindow = { start: scenario.window_start, end: scenario.window_end }
  return (
    <>
      <section className="card">
        <h2>Scenario</h2>
        <dl>
          <dt>Site</dt>
          <dd>{location.name ?? <span className="muted">unnamed location</span>}</dd>
          <dt>Coordinates</dt>
          <dd className="value">
            {formatLatLon(location.lat, location.lon)}
            <div className="definition">Planetocentric, east-positive longitude.</div>
          </dd>
          <dt>Unit height</dt>
          <dd className="value">
            {formatHeight(scenario.unit_height_m)}
            {heightDoc && <div className="definition">{heightDoc}.</div>}
          </dd>
          <dt>Window start</dt>
          <dd className="value">{formatUtc(scenario.window_start)}</dd>
          <dt>Window end</dt>
          <dd className="value">{formatUtc(scenario.window_end)}</dd>
          <dt>Step</dt>
          <dd className="value">{formatDuration(scenario.step)}</dd>
          <dt>Scenario key</dt>
          <dd className="value muted">{data.scenario_key}</dd>
        </dl>
      </section>
      {children}
      <div className="grid-2">
        <MetricTable
          title="Power"
          schema="PowerMetrics"
          metrics={data.power}
          labels={POWER_LABELS}
          clipped={POWER_CLIPPED}
          scenarioWindow={scenarioWindow}
        />
        <MetricTable
          title="Comms (direct to Earth)"
          schema="CommsMetrics"
          metrics={data.comms}
          labels={COMMS_LABELS}
          clipped={COMMS_CLIPPED}
          scenarioWindow={scenarioWindow}
        />
      </div>
      <Events events={data.events ?? []} step={scenario.step} />
      {data.fidelity && <Fidelity fidelity={data.fidelity} />}
    </>
  )
}
