// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// C1 thin-slice site screen: one scenario's metrics, events and fidelity, exactly as the API
// (or fixture) sent them. null = "not computed", never 0. Definitions come from the contract.
import type { ReactNode } from 'react'
import type { FidelityLabel, MetricEvent, MetricsResponse } from './api/client'
import {
  EVENT_LABELS,
  formatDateRange,
  formatDuration,
  formatExactRange,
  formatHeight,
  formatLatLon,
  formatLength,
  formatStepPlain,
  formatUtc,
  midSentence,
} from './format'
import { MetricValue, Value } from './metrics'
import { useSiteNames } from './siteNames'
import {
  COMMS_SPEC,
  DOCS,
  fieldDoc,
  type MetricSpec,
  metricFields,
  POWER_SPEC,
  type ScenarioWindow,
} from './metricSpec'

function MetricTable<T extends object>({
  title,
  metrics,
  spec,
  scenarioWindow,
}: {
  title: string
  metrics: T
  spec: MetricSpec<T>
  scenarioWindow: ScenarioWindow
}) {
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
          {metricFields(spec).map((field) => (
            <tr key={field}>
              <th scope="row">
                {spec.labels[field]}
                <div className="definition">
                  {fieldDoc(spec.schema, field) ?? (
                    <span className="no-def">No definition in the contract yet.</span>
                  )}
                </div>
              </th>
              <td>
                <MetricValue metrics={metrics} field={field} spec={spec} scenarioWindow={scenarioWindow} />
              </td>
            </tr>
          ))}
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
        <p className="muted">No events in this time window.</p>
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
        Times are at the calculation's samples ({formatStepPlain(step)}) unless refined.
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
  const names = useSiteNames()
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
          <dd>{names.at(location) ?? location.name ?? <span className="muted">unnamed location</span>}</dd>
          <dt>Time window</dt>
          <dd>
            <span className="value">
              {formatDateRange(scenario.window_start, scenario.window_end)} ·{' '}
              {formatLength(scenario.window_start, scenario.window_end)} · {formatStepPlain(scenario.step)}
            </span>
            <div className="definition value">
              {formatExactRange(scenario.window_start, scenario.window_end)}
            </div>
          </dd>
          <dt>Unit height</dt>
          <dd className="value">
            {formatHeight(scenario.unit_height_m)}
            {heightDoc && <div className="definition">{heightDoc}.</div>}
          </dd>
        </dl>
        <details className="advanced">
          <summary>Advanced</summary>
          <dl>
            <dt>Step</dt>
            <dd className="value">
              {scenario.step} ({formatDuration(scenario.step)})
            </dd>
            <dt>Scenario key</dt>
            <dd className="value">{data.scenario_key}</dd>
            <dt>Coordinates</dt>
            <dd className="value">
              {formatLatLon(location.lat, location.lon)}
              <div className="definition">Planetocentric, east-positive longitude.</div>
            </dd>
          </dl>
        </details>
      </section>
      {children}
      <div className="grid-2">
        <MetricTable title="Power" metrics={data.power} spec={POWER_SPEC} scenarioWindow={scenarioWindow} />
        <MetricTable
          title="Comms (direct to Earth)"
          metrics={data.comms}
          spec={COMMS_SPEC}
          scenarioWindow={scenarioWindow}
        />
      </div>
      <Events events={data.events ?? []} step={scenario.step} />
      {data.fidelity && <Fidelity fidelity={data.fidelity} />}
    </>
  )
}
