// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// The terrain images' map grid (the view.json `proj4`): south polar stereographic on the lunar
// sphere. proj4 converts between the grid and lat/lon on the SAME sphere, so no Earth datum is ever
// involved. Anything else is refused rather than drawn with the wrong geometry.
//
// Deliberately NOT registered with OpenLayers (ol/proj/proj4 `register`): OpenLayers would then
// measure distances via EPSG:4326, i.e. on the Earth. The map gets its own Projection with the
// exact stereographic scale factor below instead.
import proj4 from 'proj4'

export type PolarGrid = {
  /** The proj4 definition, as sent. */
  def: string
  radiusM: number
  /** Grid metres → [lat, lon] in degrees on the lunar sphere. */
  toLatLon(x: number, y: number): [number, number]
  /** [lat, lon] in degrees → grid metres. */
  fromLatLon(lat: number, lon: number): [number, number]
  /**
   * Scale factor k at a grid point (grid distance / ground distance). For polar stereographic
   * true at the pole: k = 2 / (1 + sin|lat|) = 1 + ρ² / (4R²), ρ = distance from the pole in the grid.
   */
  scale(x: number, y: number): number
}

/** The parameters every terrain image must have; the definition may add nothing else but +no_defs. */
const REQUIRED: Record<string, string> = {
  proj: 'stere',
  lat_0: '-90',
  lat_ts: '-90',
  lon_0: '0',
  x_0: '0',
  y_0: '0',
  units: 'm',
}

/** Parses and checks the definition; throws with the reason if it isn't the expected grid. */
export function polarGrid(def: string): PolarGrid {
  const params: Record<string, string> = {}
  for (const token of def.trim().split(/\s+/)) {
    const m = /^\+([A-Za-z_0-9]+)(?:=(.*))?$/.exec(token)
    if (!m) throw new Error(`unexpected token "${token}" in the map projection`)
    params[m[1]] = m[2] ?? ''
  }
  for (const [key, want] of Object.entries(REQUIRED)) {
    const got = params[key]
    const same = Number.isNaN(Number(want))
      ? got === want
      : got !== undefined && got !== '' && Number(got) === Number(want)
    if (!same) {
      throw new Error(
        `the map projection isn't south polar stereographic as expected (+${key}=${params[key] ?? 'missing'})`,
      )
    }
  }
  const extra = Object.keys(params).filter((k) => !(k in REQUIRED) && k !== 'R' && k !== 'no_defs')
  if (extra.length > 0)
    throw new Error(`the map projection has unexpected parameters: ${extra.map((k) => `+${k}`).join(' ')}`)
  const radiusM = Number(params.R)
  if (!Number.isFinite(radiusM) || radiusM <= 0)
    throw new Error('the map projection has no sphere radius (+R)')

  const lonLat = `+proj=longlat +R=${radiusM} +no_defs`
  const forward = proj4(lonLat, def)
  return {
    def,
    radiusM,
    toLatLon(x, y) {
      const [lon, lat] = forward.inverse([x, y])
      return [lat, lon]
    },
    fromLatLon(lat, lon) {
      const [x, y] = forward.forward([lon, lat])
      return [x, y]
    },
    scale(x, y) {
      return 1 + (x * x + y * y) / (4 * radiusM * radiusM)
    },
  }
}
