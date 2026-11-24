// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// Sky view (C5): horizon/sky plot + timeline + state readout, sharing one selected sample.
// Refuses to plot a horizon and a series that belong to different locations or heights.
import { useMemo, useState } from 'react'
import type { HorizonProfile, MetricEvent, SeriesResponse } from '../api/client'
import { formatTerrainLayer } from '../format'
import HorizonPlot from './HorizonPlot'
import StateReadout from './StateReadout'
import Timeline from './Timeline'
import Section from '../Section'

/** Why the horizon can't be drawn with this series, or null when they match. */
function mismatch(horizon: HorizonProfile, series: SeriesResponse): string | null {
  const a = horizon.location
  const b = series.scenario.location
  if (a.lat !== b.lat || a.lon !== b.lon) {
    return `the horizon is for ${a.lat}°, ${a.lon}° but the series is for ${b.lat}°, ${b.lon}°`
  }
  if (horizon.unit_height_m !== series.scenario.unit_height_m) {
    return `the horizon is for ${horizon.unit_height_m} m but the series is for ${series.scenario.unit_height_m} m`
  }
  return null
}

function PlaceholderNotice({ horizon, series }: { horizon: HorizonProfile; series: SeriesResponse }) {
  const which = [horizon._placeholder && 'terrain horizon', series._placeholder && 'Sun/Earth series'].filter(
    Boolean,
  )
  if (which.length === 0) return null
  return (
    <div className="banner placeholder" role="note">
      <strong>Placeholder data, not a computed result:</strong> {which.join(' and ')}.
    </div>
  )
}

export default function SkyView({ horizon, series }: { horizon: HorizonProfile; series: SeriesResponse }) {
  const [index, setIndex] = useState(0)
  // The event picked on the timeline, if any; moving the slider clears it.
  const [selectedEvent, setSelectedEvent] = useState<MetricEvent | null>(null)
  const timeMs = useMemo(() => series.time.map((t) => Date.parse(t)), [series])
  const problem = mismatch(horizon, series)
  const placeholder = horizon._placeholder || series._placeholder

  return (
    <Section id="sky" title="Horizon and sky">
      <PlaceholderNotice horizon={horizon} series={series} />
      {problem ? (
        <div className="banner error" role="alert">
          <strong>Can't plot:</strong> {problem}.
        </div>
      ) : series.time.length === 0 ? (
        <p className="muted">The series has no samples.</p>
      ) : (
        <>
          <HorizonPlot horizon={horizon} series={series} index={index} placeholder={placeholder} />
          <ul className="legend">
            <li>
              <span className="legend-swatch swatch-sun" aria-hidden="true" /> Sun track
            </li>
            <li>
              <span className="legend-swatch swatch-earth" aria-hidden="true" /> Earth track
            </li>
            <li>
              <span className="legend-swatch swatch-terrain" aria-hidden="true" /> Terrain horizon
            </li>
            <li>Marker filled: some of the disc visible · hollow: none visible</li>
          </ul>
          <Timeline
            time={series.time}
            timeMs={timeMs}
            events={series.events ?? []}
            index={index}
            selectedEvent={selectedEvent}
            onChange={(i) => {
              setSelectedEvent(null)
              setIndex(i)
            }}
            onSelectEvent={(ev, i) => {
              setSelectedEvent(ev)
              setIndex(i)
            }}
          />
          <StateReadout sun={series.sun} earth={series.earth} index={index} horizon={horizon} />
          <div className="definition sky-notes">
            {series.downsampled && <p>The plotted series is thinned for display.</p>}
            <p>
              Terrain horizon
              {horizon.max_range_km != null && <> to {horizon.max_range_km} km</>}
              {horizon.terrain_stack?.length ? (
                <>: {horizon.terrain_stack.map(formatTerrainLayer).join('; ')}.</>
              ) : (
                '.'
              )}
            </p>
          </div>
        </>
      )}
    </Section>
  )
}
