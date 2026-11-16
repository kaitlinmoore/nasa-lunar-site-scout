// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// An NL comparison (compare with filters, a rank or a site template; contract 0.10.0+): the saved
// page's comparison table, one column per compared scenario, plus per column what happened to it (no
// precomputed result, filtered out and why, cut by the rank's limit, or its rank) and the values the
// filters and the rank used. Every value is the API's; nothing is filtered or ranked here.
import type { ReactNode } from 'react'
import type { KeyedComparison } from '../api/compare'
import { compareMetricLabel } from '../api/compare'
import type { components } from '../api/schema'
import { formatValue, unitOf } from '../format'
import { COMMS_SPEC, POWER_SPEC } from '../metricSpec'
import CompareTable from '../saved/CompareTable'
import { placeLabel, useSiteNames } from '../siteNames'
import { NotComputed, Num } from '../Value'

type S = components['schemas']

type MetricInfo = { label: string; field: string; definition?: string }

const OPS: Record<S['FilterOp'], string> = { lt: '<', le: '≤', gt: '>', ge: '≥', eq: '=' }

/** A label and a unit for a compare metric (MetricName or a Sun-elevation band label); null if unknown. */
function describeCompareMetric(metric: string): MetricInfo | null {
  const band = /^sun_elevation_band_fraction\[(-?[\d.e+-]+),(-?[\d.e+-]+)\]$/.exec(metric)
  if (band) {
    return {
      label: `Sun elevation ${band[1]}° to ${band[2]}°`,
      field: 'band_fraction',
      definition:
        "share of the time window with the Sun's centre in this band above the local horizontal, whether or not terrain hides it",
    }
  }
  if (metric === 'terrain.slope_at_point_deg')
    return { label: 'Slope at the point', field: 'slope_at_point_deg' }
  const m = /^(power|comms)\.([a-z_]+)(?:\.(min|max|mean))?$/.exec(metric)
  if (!m) return null
  const labels: Record<string, string | undefined> = m[1] === 'power' ? POWER_SPEC.labels : COMMS_SPEC.labels
  const label = labels[m[2]]
  if (!label) return null
  return { label: m[3] ? `${label} (${m[3]})` : label, field: m[2] }
}

const metricName = (metric: string) => describeCompareMetric(metric)?.label ?? metric

/** "Slope at the point < 5.00°", from the query as the API echoed it. */
function filterText(f: S['MetricFilter']): string {
  const label = compareMetricLabel(f.metric)
  const info = describeCompareMetric(label)
  if (!info) return `${label} ${OPS[f.op]} ${f.value}`
  const unit = unitOf(info.field)
  const value = unit === 'count' ? String(f.value) : formatValue(f.value, unit, info.field)
  return `${info.label} ${OPS[f.op]} ${value}`
}

function EvaluatedCell({
  metric,
  value,
  source,
}: {
  metric: string
  value: number | null
  source?: string | null
}) {
  const info = describeCompareMetric(metric)
  if (!info) return <span className="not-computed">a value of a kind this page doesn't know; not shown</span>
  if (value === null) return <NotComputed />
  return (
    <>
      <Num value={value} field={info.field} />
      {source && <div className="definition">from the {source}</div>}
    </>
  )
}

export default function CompareAnswer({
  comparison,
  filters,
  rank,
}: {
  comparison: KeyedComparison
  filters: S['MetricFilter'][]
  rank: S['CompareRank'] | null
}) {
  const names = useSiteNames()
  const label = (s: S['Scenario']) => placeLabel(names, s.location)
  const byKey = new Map(comparison.columns.map((c) => [c.key, c]))
  const { columns } = comparison
  const withResult = columns.filter((c) => c.result).length

  const status = (c: (typeof columns)[number]): ReactNode => {
    const o = c.outcome
    switch (o.kind) {
      case 'not_served':
        return <span className="not-computed">Not precomputed: {o.reason}</span>
      case 'filtered_out':
        return (
          <span className="not-computed">
            Filtered out:{' '}
            {[
              o.failed.length > 0 && `${o.failed.map(metricName).join(', ')} didn't pass`,
              o.notComputed.length > 0 && `${o.notComputed.map(metricName).join(', ')} not computed`,
            ]
              .filter(Boolean)
              .join('; ')}
            .
          </span>
        )
      case 'beyond_limit':
        return <span className="not-computed">Passed, but beyond the top {o.limit}.</span>
      case 'result':
        return (
          <>
            <strong>{o.rank !== null ? `Rank ${o.rank}` : filters.length > 0 ? 'Passed' : 'Result'}</strong>
            {o.tiedWith.length > 0 && (
              <div className="definition">
                tied with{' '}
                {o.tiedWith
                  .map((k) => {
                    const other = byKey.get(k)
                    return other ? label(other.scenario) : k
                  })
                  .join(', ')}
              </div>
            )}
            <div className="muted value">scenario key {c.key}</div>
          </>
        )
    }
  }

  return (
    <div className="nl-result">
      <div className="definition nl-compare-query">
        {filters.length > 0 && <p>Kept only: {filters.map(filterText).join(' · ')}.</p>}
        {rank && (
          <p>
            Ranked by {metricName(compareMetricLabel(rank.metric))},{' '}
            {rank.order === 'asc' ? 'lowest first' : 'highest first'}
            {rank.limit != null && `, top ${rank.limit}`}. The API ranks on the exact values, so values that
            look equal here may differ in a later digit (hover a value to see it); equal values are marked as
            ties.
          </p>
        )}
        <p>
          {columns.length} scenarios compared; {withResult} with results
          {rank ? ', shown in rank order' : ''}.
        </p>
      </div>
      <CompareTable
        entries={columns.map((c) => ({
          saved: { id: c.key, label: label(c.scenario), site_id: null, saved_at: '', scenario: c.scenario },
          result: c.result,
          reason: null,
          status: status(c),
        }))}
        extraGroup={
          comparison.evaluatedMetrics.length === 0
            ? undefined
            : {
                title: 'Values the filters and the rank used',
                rows: comparison.evaluatedMetrics.map((metric) => {
                  const info = describeCompareMetric(metric)
                  return {
                    key: metric,
                    header: (
                      <>
                        {info?.label ?? metric}
                        {info?.definition && <div className="definition">{info.definition}</div>}
                      </>
                    ),
                    cells: columns.map((c) => {
                      const e = c.evaluated.find((v) => v.metric === metric)
                      return e ? (
                        <EvaluatedCell key={c.key} metric={metric} value={e.value} source={e.source} />
                      ) : (
                        <span key={c.key} className="muted">
                          –
                        </span>
                      )
                    }),
                  }
                }),
              }
        }
      />
    </div>
  )
}
