// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// Timeline (C5): scrub the scenario window. The slider steps through the series samples the
// API sent (no interpolation between them). An event mark selects that event: the event's own
// time from the API is shown (refined to the second where the API refined it), while the plot
// and readout move to the nearest sample, labelled as such.
import type { MetricEvent } from '../api/client'
import { EVENT_LABELS, formatSamplePosition, formatUtc } from '../format'
import { nearestTimeIndex } from './geometry'

const EVENT_BODY: Record<MetricEvent['kind'], 'sun' | 'earth'> = {
  sunrise: 'sun',
  sunset: 'sun',
  earthrise: 'earth',
  earthset: 'earth',
}

export default function Timeline({
  time,
  timeMs,
  events,
  index,
  selectedEvent,
  onChange,
  onSelectEvent,
}: {
  time: string[]
  timeMs: number[]
  events: MetricEvent[]
  index: number
  selectedEvent: MetricEvent | null
  onChange: (index: number) => void
  onSelectEvent: (event: MetricEvent, nearestIndex: number) => void
}) {
  const n = time.length
  const start = timeMs[0]
  const span = timeMs[n - 1] - start
  return (
    <div className="timeline">
      {selectedEvent ? (
        <div className="timeline-now">
          <div>
            <span className="timeline-time">{EVENT_LABELS[selectedEvent.kind]}</span>{' '}
            <span className="timeline-time value" title={`API value: ${selectedEvent.time}`}>
              {formatUtc(selectedEvent.time)}
            </span>{' '}
            {selectedEvent.refined && <span className="badge">refined</span>}
          </div>
          <div className="muted">
            Plot and readout at the nearest sample: {formatUtc(time[index])} ·{' '}
            {formatSamplePosition(index, n)}
          </div>
        </div>
      ) : (
        <div className="timeline-now">
          <span className="timeline-time value">{formatUtc(time[index])}</span>
          <span className="muted"> · {formatSamplePosition(index, n)}</span>
        </div>
      )}
      <div className="timeline-track">
        <input
          type="range"
          className="timeline-slider"
          min={0}
          max={n - 1}
          step={1}
          value={index}
          onChange={(e) => onChange(Number(e.target.value))}
          aria-label="Selected time in the scenario window"
          aria-valuetext={formatUtc(time[index])}
        />
        <div className="timeline-events">
          {events.map((ev, i) => {
            const t = Date.parse(ev.time)
            if (!(t >= start && t <= start + span)) return null
            const label = `${EVENT_LABELS[ev.kind]} ${formatUtc(ev.time)}${ev.refined ? ' (refined)' : ''}`
            const selected = ev === selectedEvent
            return (
              <button
                key={`${ev.kind}-${ev.time}-${i}`}
                type="button"
                className={`timeline-event event-${EVENT_BODY[ev.kind]}${selected ? ' is-selected' : ''}`}
                style={{ left: `${((t - start) / span) * 100}%` }}
                title={`${label}. Show this event.`}
                aria-label={`${label}. Show this event.`}
                aria-pressed={selected}
                onClick={() => onSelectEvent(ev, nearestTimeIndex(timeMs, t))}
              />
            )
          })}
        </div>
      </div>
      <div className="timeline-ends muted">
        <span>{formatUtc(time[0])}</span>
        <span>{formatUtc(time[n - 1])}</span>
      </div>
    </div>
  )
}
