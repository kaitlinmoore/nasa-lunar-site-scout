// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// IAU feature names for the globe labels (contract 0.14.0): GET /api/features/labels, compact rows
// [id, name, type, lat, lon, diameter_km], largest first. Without a usable live answer, the static copy's
// feature_labels.json (every name, satellite features included) is filtered here the same way. Names
// label features only: their positions identify features (about 300 m), and no number is shown.
// Attribution comes from the dataset the response names (GET /api/datasets; public domain).
import { getJson, type Schemas } from '../api/client'
import type { DataSource } from '../api/source'
import { staticDatasets, staticFeatureLabels, withStaticFallback } from '../api/staticFallback'

type FeatureLabelsResponse = Schemas['FeatureLabelsResponse']
type DatasetCapability = Schemas['DatasetCapability']

/** [id, name, type, lat, lon, diameter_km], as sent. */
export type FeatureLabelRow = [number, string, string, number, number, number]

/** The IAU type code of satellite features ("Cabeus B"); they come only when asked for. */
export const SATELLITE_TYPE = 'SF'

export type FeatureLabels = {
  datasetId: string
  rows: FeatureLabelRow[]
  /** The dataset entry for attribution, or null if the list couldn't be loaded. */
  dataset: DatasetCapability | null
}

const FIELDS = ['id', 'name', 'type', 'lat', 'lon', 'diameter_km']

/** Checks the response's column order and every row; keeps or drops satellite features. Throws on a misfit. */
export function checkFeatureLabels(r: FeatureLabelsResponse, satellite: boolean): FeatureLabelRow[] {
  if (r.fields.length !== FIELDS.length || r.fields.some((f, i) => f !== FIELDS[i])) {
    throw new Error(`feature labels: unexpected columns ${r.fields.join(', ')}; not shown`)
  }
  const rows: FeatureLabelRow[] = []
  for (const row of r.rows) {
    const [id, name, type, lat, lon, d] = row as FeatureLabelRow
    const ok =
      Number.isInteger(id) &&
      typeof name === 'string' &&
      name.length > 0 &&
      typeof type === 'string' &&
      Number.isFinite(lat) &&
      Math.abs(lat) <= 90 &&
      Number.isFinite(lon) &&
      Math.abs(lon) <= 180 &&
      Number.isFinite(d) &&
      d >= 0
    if (!ok)
      throw new Error(`feature labels: a row doesn't fit the contract (${JSON.stringify(row)}); not shown`)
    if (!satellite && type === SATELLITE_TYPE) continue
    rows.push([id, name, type, lat, lon, d])
  }
  return rows
}

/** The globe's feature names (no satellite features), with attribution; null in fixture mode. */
export async function loadFeatureLabels(source: DataSource): Promise<FeatureLabels | null> {
  if (source === 'fixtures') return null
  const response = await withStaticFallback(
    () => getJson<FeatureLabelsResponse>('/api/features/labels'),
    staticFeatureLabels,
  )
  const rows = checkFeatureLabels(response, false)
  const list = await withStaticFallback(
    () => getJson<Schemas['DatasetsResponse']>('/api/datasets'),
    staticDatasets,
  ).catch(() => null)
  return {
    datasetId: response.dataset_id,
    rows,
    dataset: list?.datasets.find((d) => d.id === response.dataset_id) ?? null,
  }
}
