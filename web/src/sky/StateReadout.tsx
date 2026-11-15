// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// Sun / Earth / horizon state at the selected sample (C5). Every number is a value the API sent
// at that sample; the terrain horizon is the profile sample nearest the body's azimuth, and the
// readout names which profile sample it used.
import type { BodyTrack, HorizonProfile } from '../api/client'
import { formatProfileSample } from '../format'
import { Num } from '../Value'
import { nearestAzimuthIndex } from './geometry'

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
  const k = nearestAzimuthIndex(horizon.azimuth_deg, az)
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
        <Num value={horizon.elevation_deg[k]} field="elevation_deg" />
        <div className="definition">{formatProfileSample(horizon.azimuth_deg[k])}</div>
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
            <th scope="col">Terrain horizon at its azimuth</th>
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
        <dd>{horizonDoc ?? <span className="no-def">No definition in the contract yet.</span>}</dd>
      </dl>
    </>
  )
}
