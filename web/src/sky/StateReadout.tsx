// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// Sun / Earth / horizon state at the selected sample (C5). Sun/Earth numbers are the values the
// API sent at that sample. The terrain horizon at each body's azimuth is interpolated linearly
// between the neighbouring profile samples, as the contract specifies (Kaitlin, 2026-11-15), so
// it's the same value the engine uses; the readout names the samples it came from.
import type { BodyTrack, HorizonProfile } from '../api/client'
import { formatInterpolatedBetween, formatProfileSample } from '../format'
import { Num } from '../Value'
import { horizonAt } from './geometry'

const DOCS = __FIELD_DOCS__

function Row({
  label,
  body,
  track,
  index,
  horizon,
}: {
  label: string
  body: 'sun' | 'earth'
  track: BodyTrack
  index: number
  horizon: HorizonProfile
}) {
  const az = track.azimuth_deg[index]
  const h = horizonAt(horizon.azimuth_deg, horizon.elevation_deg, az)
  return (
    <tr>
      <th scope="row">
        <span className={`legend-swatch swatch-${body}`} aria-hidden="true" /> {label}
      </th>
      <td>
        <Num value={az} field="azimuth_deg" />
      </td>
      <td>
        <Num value={track.elevation_deg[index]} field="elevation_deg" />
      </td>
      <td>
        <Num value={track.visible_fraction[index]} field="visible_fraction" />
      </td>
      <td>
        <Num value={track.clearance_deg?.[index]} field="clearance_deg" />
      </td>
      <td>
        {h === null ? (
          <Num value={null} field="elevation_deg" />
        ) : h.lo === h.hi ? (
          <>
            <Num value={h.elevation} field="elevation_deg" />
            <div className="definition">{formatProfileSample(horizon.azimuth_deg[h.lo])}</div>
          </>
        ) : (
          <>
            <Num value={h.elevation} field="elevation_deg" origin="Interpolated from the API profile" />
            <div className="definition">
              {formatInterpolatedBetween(horizon.azimuth_deg[h.lo], horizon.azimuth_deg[h.hi])}
            </div>
          </>
        )}
      </td>
    </tr>
  )
}

export default function StateReadout({
  sun,
  earth,
  index,
  horizon,
}: {
  sun: BodyTrack
  earth: BodyTrack
  index: number
  horizon: HorizonProfile
}) {
  const docs = DOCS.BodyTrack ?? {}
  const horizonDoc = DOCS.HorizonProfile?.elevation_deg
  return (
    <>
      <table className="readout">
        <thead>
          <tr>
            <th scope="col">Body</th>
            <th scope="col">Azimuth</th>
            <th scope="col">Elevation</th>
            <th scope="col">Visible disc</th>
            <th scope="col">Clearance</th>
            <th scope="col">Terrain horizon at its azimuth (interpolated)</th>
          </tr>
        </thead>
        <tbody>
          <Row label="Sun" body="sun" track={sun} index={index} horizon={horizon} />
          <Row label="Earth" body="earth" track={earth} index={index} horizon={horizon} />
        </tbody>
      </table>
      <dl className="readout-defs">
        <dt>Visible disc</dt>
        <dd>{docs.visible_fraction ?? <span className="no-def">No definition in the contract yet.</span>}</dd>
        <dt>Clearance</dt>
        <dd>{docs.clearance_deg ?? <span className="no-def">No definition in the contract yet.</span>}</dd>
        <dt>Terrain horizon</dt>
        <dd>
          {horizonDoc ?? <span className="no-def">No definition in the contract yet.</span>}
          <div>
            Read at each body's azimuth by linear interpolation between the neighbouring profile
            samples, as the contract specifies, so it's the same value the engine uses.
          </div>
        </dd>
      </dl>
    </>
  )
}
