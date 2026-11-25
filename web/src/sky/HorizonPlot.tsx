// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// Horizon/sky plot: terrain horizon profile (elevation vs azimuth) with the Sun and Earth
// tracks over the window and their positions at the selected sample. SVG; colours from CSS
// tokens via classes. Values are plotted exactly as sent; nothing is interpolated.
import { useMemo } from 'react'
import type { BodyTrack, HorizonProfile, SeriesResponse } from '../api/client'
import { formatAzimuthTick, formatElevationTick } from '../format'
import { elevationDomain, linear, splitAtAzimuthWrap, ticks } from './geometry'

// Plot geometry in SVG user units (the SVG scales to its container width).
const W = 960
const H = 360
const M = { left: 52, right: 32, top: 12, bottom: 36 }
const X0 = M.left
const X1 = W - M.right
const Y0 = H - M.bottom
const Y1 = M.top

type Scale = (v: number) => number

function trackPaths(track: BodyTrack, x: Scale, y: Scale): string[] {
  return splitAtAzimuthWrap(track.azimuth_deg).map((run) =>
    run.map((i) => `${x(track.azimuth_deg[i]).toFixed(1)},${y(track.elevation_deg[i]).toFixed(1)}`).join(' '),
  )
}

function BodyMarker({
  track,
  index,
  x,
  y,
  body,
}: {
  track: BodyTrack
  index: number
  x: Scale
  y: Scale
  body: 'sun' | 'earth'
}) {
  const visible = track.visible_fraction[index] > 0
  return (
    <circle
      className={`plot-marker plot-${body} ${visible ? 'is-visible' : 'is-hidden'}`}
      cx={x(track.azimuth_deg[index])}
      cy={y(track.elevation_deg[index])}
      r={7}
    />
  )
}

export default function HorizonPlot({
  horizon,
  series,
  index,
  placeholder,
}: {
  horizon: HorizonProfile
  series: SeriesResponse
  index: number
  placeholder: boolean
}) {
  const plot = useMemo(() => {
    const dom = elevationDomain([horizon.elevation_deg, series.sun.elevation_deg, series.earth.elevation_deg])
    const x = linear(0, 360, X0, X1)
    const y = linear(dom.min, dom.max, Y0, Y1)
    // Terrain: the profile as sent, for any azimuth spacing. To close the 0/360° seam, the
    // last sample is repeated at -360° and the first at +360° (same directions, no new values);
    // the plot clips everything outside 0–360°.
    const az = [...horizon.azimuth_deg]
    const el = [...horizon.elevation_deg]
    if (az.length) {
      const n = az.length
      az.unshift(az[n - 1] - 360)
      el.unshift(el[n - 1])
      az.push(az[1] + 360)
      el.push(el[1])
    }
    const line = az.map((a, i) => `${x(a).toFixed(1)},${y(el[i]).toFixed(1)}`).join(' ')
    const fill = az.length ? `${x(az[0])},${Y0} ${line} ${x(az[az.length - 1])},${Y0}` : ''
    return {
      x,
      y,
      dom,
      line,
      fill,
      sun: trackPaths(series.sun, x, y),
      earth: trackPaths(series.earth, x, y),
      xTicks: ticks(0, 360, 45),
      yTicks: ticks(dom.min, dom.max, dom.step),
    }
  }, [horizon, series])

  const { x, y } = plot
  return (
    <svg
      className="sky-plot"
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label="Terrain horizon profile with Sun and Earth tracks, elevation versus azimuth"
    >
      <defs>
        <clipPath id="plot-area">
          <rect x={X0} y={Y1} width={X1 - X0} height={Y0 - Y1} />
        </clipPath>
      </defs>

      {/* grid + axes */}
      {plot.yTicks.map((v) => (
        <g key={`y${v}`}>
          <line className={v === 0 ? 'plot-zero' : 'plot-grid'} x1={X0} x2={X1} y1={y(v)} y2={y(v)} />
          <text className="plot-tick" x={X0 - 6} y={y(v)} textAnchor="end" dominantBaseline="middle">
            {formatElevationTick(v)}
          </text>
        </g>
      ))}
      {plot.xTicks.map((v) => (
        <g key={`x${v}`}>
          <line className="plot-grid" x1={x(v)} x2={x(v)} y1={Y1} y2={Y0} />
          <text className="plot-tick" x={x(v)} y={Y0 + 16} textAnchor="middle">
            {formatAzimuthTick(v)}
          </text>
        </g>
      ))}
      <text className="plot-axis-label" x={(X0 + X1) / 2} y={H - 4} textAnchor="middle">
        Azimuth (deg clockwise from north)
      </text>
      <text
        className="plot-axis-label"
        transform={`translate(12 ${(Y0 + Y1) / 2}) rotate(-90)`}
        textAnchor="middle"
      >
        Elevation (deg)
      </text>

      {/* tracks under the terrain, so their below-horizon parts read as hidden */}
      {plot.sun.map((pts, i) => (
        <polyline key={`s${i}`} className="plot-track plot-sun" points={pts} />
      ))}
      {plot.earth.map((pts, i) => (
        <polyline key={`e${i}`} className="plot-track plot-earth" points={pts} />
      ))}
      <g clipPath="url(#plot-area)">
        <polygon className="plot-terrain" points={plot.fill} />
        <polyline className="plot-horizon" points={plot.line} />
      </g>

      {/* placeholder watermark: over the terrain (so it's never hidden), under the markers */}
      {placeholder && (
        <text className="plot-watermark" x={(X0 + X1) / 2} y={(Y0 + Y1) / 2} textAnchor="middle">
          PLACEHOLDER DATA
        </text>
      )}

      {/* positions at the selected sample */}
      <BodyMarker track={series.sun} index={index} x={x} y={y} body="sun" />
      <BodyMarker track={series.earth} index={index} x={x} y={y} body="earth" />
    </svg>
  )
}
