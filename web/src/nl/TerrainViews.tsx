// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// NL answer views for contract 0.9.0: slope statistics (`terrain`) and the site summary
// (`site_summary` = slope statistics + nearby features + metrics). Values are the API's, formatted
// like the site screen's; a missing value says "not computed". Each result's own `limitations`
// are shown with it.
import type { Schemas } from '../api/client'
import { formatLatLon } from '../format'
import { StatValue, Value } from '../metrics'
import { fieldDoc } from '../metricSpec'
import SiteScreen from '../SiteScreen'

type TerrainResponse = Schemas['TerrainResponse']
type ProximityResponse = Schemas['ProximityResponse']
type SiteSummaryResponse = Schemas['SiteSummaryResponse']
type SiteLocation = Schemas['Location']

const placeName = (l: SiteLocation) => l.name ?? formatLatLon(l.lat, l.lon)

const FEATURE_TYPE_LABELS: Record<string, string> = {
  crater: 'crater',
  psr: 'permanently shadowed region',
  ice_detection: 'surface-ice detection',
  hazard: 'hazard',
  landing_site: 'landing site',
  named_feature: 'named feature',
}

function ResultLimits({ limitations, title }: { limitations: string[] | undefined; title: string }) {
  if (!limitations || limitations.length === 0) return null
  return (
    <div className="banner notice" role="status">
      <strong>{title}</strong>
      <ul>
        {limitations.map((l, i) => (
          <li key={i}>{l}</li>
        ))}
      </ul>
    </div>
  )
}

/** Slope statistics around a location (POST /api/terrain). */
export function TerrainView({ terrain }: { terrain: TerrainResponse }) {
  const doc = (field: string) => fieldDoc('TerrainResponse', field)
  const layer = terrain.slope_layer
  return (
    <section className="card">
      <h2>Slope</h2>
      <dl>
        <dt>Area</dt>
        <dd className="value">
          {placeName(terrain.location)} · within <Value value={terrain.radius_m} field="radius_m" />
          <div className="definition">{formatLatLon(terrain.location.lat, terrain.location.lon)}</div>
        </dd>
        <dt>At the point</dt>
        <dd className="value">
          <Value value={terrain.slope_at_point_deg} field="slope_at_point_deg" />
          {doc('slope_at_point_deg') && <div className="definition">{doc('slope_at_point_deg')}</div>}
        </dd>
        <dt>Within the radius</dt>
        <dd className="value">
          <StatValue stat={terrain.slope_deg ?? undefined} field="slope_deg" />
          {doc('slope_deg') && <div className="definition">{doc('slope_deg')}</div>}
        </dd>
        <dt>Measured on</dt>
        <dd>
          {layer ? (
            <>
              <span className="value">{layer.dataset_id}</span>{' '}
              <span className="muted">
                ({layer.role === 'near_field' ? 'near field' : 'far field'},{' '}
                <Value value={layer.resolution_m} field="resolution_m" /> pixels)
              </span>
            </>
          ) : (
            <span className="not-computed">not given</span>
          )}
          {doc('slope_layer') && <div className="definition">{doc('slope_layer')}</div>}
        </dd>
      </dl>
      <ResultLimits limitations={terrain.limitations} title="Limits of these values:" />
    </section>
  )
}

/** Nearby features (the site summary's `features`, a ProximityResponse). */
function FeaturesView({ features }: { features: ProximityResponse }) {
  const shown = features.results.length
  return (
    <section className="card">
      <h2>Nearby features</h2>
      {shown === 0 ? (
        <p className="muted">None found.</p>
      ) : (
        <table className="metrics">
          <thead>
            <tr>
              <th scope="col">Feature</th>
              <th scope="col">Distance</th>
              <th scope="col">Diameter</th>
              <th scope="col">Data</th>
            </tr>
          </thead>
          <tbody>
            {features.results.map(({ feature, distance_m }) => (
              <tr key={feature.id}>
                <td>
                  {feature.name ?? <span className="muted">unnamed</span>}
                  <div className="definition">{FEATURE_TYPE_LABELS[feature.type] ?? feature.type}</div>
                </td>
                <td className="value">
                  <Value value={distance_m} field="distance_m" />
                </td>
                <td className="value">
                  <Value value={feature.diameter_m} field="diameter_m" />
                </td>
                <td className="value">{feature.dataset_id}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {features.total != null && features.total > shown && (
        <p className="muted">
          The {shown} closest of {features.total} within the radius.
        </p>
      )}
    </section>
  )
}

/** A site summary (POST /api/site_summary): what the API has for a location, part by part. */
export function SiteSummaryView({ summary }: { summary: SiteSummaryResponse }) {
  const { terrain, features, metrics } = summary
  return (
    <>
      <p>
        <span className="muted">Summary for</span> {placeName(summary.location)} · within{' '}
        <Value value={summary.radius_m} field="radius_m" />
      </p>
      <ResultLimits limitations={summary.limitations} title="Not in this summary:" />
      {terrain && <TerrainView terrain={terrain} />}
      {features && <FeaturesView features={features} />}
      {metrics && <SiteScreen data={metrics} />}
      {!terrain && !features && !metrics && <p className="muted">The summary has no parts.</p>}
    </>
  )
}
