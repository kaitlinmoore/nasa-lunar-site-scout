// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// Side-by-side comparison (C6): one column per scenario, the site screen's metric rows, values
// rendered exactly as on the site screen. A scenario without a result says so in its column.
import type { MetricsResponse } from '../api/client'
import { formatScenarioSummary } from '../format'
import { MetricValue } from '../metrics'
import { COMMS_SPEC, fieldDoc, type MetricSpec, metricFields, POWER_SPEC } from '../metricSpec'
import { NotComputed } from '../Value'
import type { SavedScenario } from './store'

export type CompareEntry = { saved: SavedScenario; result: MetricsResponse | null }

function GroupRows<T extends object>({
  title,
  spec,
  entries,
  pick,
}: {
  title: string
  spec: MetricSpec<T>
  entries: CompareEntry[]
  pick: (r: MetricsResponse) => T
}) {
  return (
    <>
      <tr className="compare-group">
        <th scope="rowgroup" colSpan={entries.length + 1}>
          {title}
        </th>
      </tr>
      {metricFields(spec).map((field) => (
        <tr key={field}>
          <th scope="row" title={fieldDoc(spec.schema, field)}>
            {spec.labels[field]}
          </th>
          {entries.map(({ saved, result }) => (
            <td key={saved.id}>
              {result ? (
                <MetricValue
                  metrics={pick(result)}
                  field={field}
                  spec={spec}
                  scenarioWindow={{ start: result.scenario.window_start, end: result.scenario.window_end }}
                />
              ) : (
                <span className="muted">–</span>
              )}
            </td>
          ))}
        </tr>
      ))}
    </>
  )
}

export default function CompareTable({
  entries,
  noResultText,
}: {
  entries: CompareEntry[]
  noResultText: string
}) {
  return (
    <div className="compare-scroll">
      <table className="metrics compare">
        <thead>
          <tr>
            <th scope="col">Scenario</th>
            {entries.map(({ saved }) => {
              const s = saved.scenario
              return (
                <th scope="col" key={saved.id}>
                  <div>{saved.label}</div>
                  <div className="definition value">{formatScenarioSummary(s)}</div>
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody>
          <tr>
            <th scope="row">Result</th>
            {entries.map(({ saved, result }) => (
              <td key={saved.id}>
                {result ? (
                  <span className="muted value">scenario key {result.scenario_key}</span>
                ) : (
                  <span className="not-computed">{noResultText}</span>
                )}
              </td>
            ))}
          </tr>
          <GroupRows title="Power" spec={POWER_SPEC} entries={entries} pick={(r) => r.power} />
          <GroupRows
            title="Comms (direct to Earth)"
            spec={COMMS_SPEC}
            entries={entries}
            pick={(r) => r.comms}
          />
          <tr className="compare-group">
            <th scope="rowgroup" colSpan={entries.length + 1}>
              Terrain fidelity
            </th>
          </tr>
          <tr>
            <th scope="row">Tier</th>
            {entries.map(({ saved, result }) => (
              <td key={saved.id}>
                {!result ? (
                  <span className="muted">–</span>
                ) : result.fidelity ? (
                  <span className={`badge tier-${result.fidelity.tier}`} title={result.fidelity.summary}>
                    {result.fidelity.tier}
                  </span>
                ) : (
                  <NotComputed />
                )}
              </td>
            ))}
          </tr>
        </tbody>
      </table>
    </div>
  )
}
