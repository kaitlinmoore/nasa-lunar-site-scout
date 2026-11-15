// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// Timeline (C5): scrub the scenario window. The slider steps through the series samples the
// API sent (no interpolation between them). Event marks jump to the nearest sample.
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
  onChange,
}: {
  time: string[]
  timeMs: number[]
  events: MetricEvent[]
  index: number
  onChange: (index: number) => void
}) {
  const n = time.length
  const start = timeMs[0]
  const span = timeMs[n - 1] - start
  return (
    <div className="timeline">
      <div className="timeline-now">
        <span className="timeline-time value">{formatUtc(time[index])}</span>
        <span className="muted"> · {formatSamplePosition(index, n)}</span>
      </div>
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
            return (
              <button
                key={`${ev.kind}-${ev.time}-${i}`}
                type="button"
                className={`timeline-event event-${EVENT_BODY[ev.kind]}`}
                style={{ left: `${((t - start) / span) * 100}%` }}
                title={`${label}. Jump to the nearest sample.`}
                aria-label={`${label}. Jump to the nearest sample.`}
                onClick={() => onChange(nearestTimeIndex(timeMs, t))}
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
