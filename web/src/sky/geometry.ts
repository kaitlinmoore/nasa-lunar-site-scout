// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// Pure helpers for the sky view: plot scales, azimuth wrap-around, and nearest-sample lookups.
// Nothing here interpolates: lookups return an index into the arrays the API sent.

/** Linear map from [d0, d1] to [r0, r1]. */
export function linear(d0: number, d1: number, r0: number, r1: number) {
  const k = (r1 - r0) / (d1 - d0)
  return (v: number) => r0 + (v - d0) * k
}

/** Tick values from `min` to `max` (inclusive) at multiples of `step`. */
export function ticks(min: number, max: number, step: number): number[] {
  const out: number[] = []
  for (let v = Math.ceil(min / step) * step; v <= max + 1e-9; v += step) out.push(Number(v.toFixed(6)))
  return out
}

/** A step giving roughly `target` ticks over a span: 1, 2 or 5 × 10^n. */
export function niceStep(span: number, target = 6): number {
  const raw = span / target
  const p = 10 ** Math.floor(Math.log10(raw))
  const m = raw / p
  return (m < 1.5 ? 1 : m < 3.5 ? 2 : m < 7.5 ? 5 : 10) * p
}

/** Elevation axis range covering every plotted value, padded and rounded out to `step`. */
export function elevationDomain(values: number[][], pad = 0.5): { min: number; max: number; step: number } {
  let lo = Infinity
  let hi = -Infinity
  for (const arr of values) {
    for (const v of arr) {
      if (v < lo) lo = v
      if (v > hi) hi = v
    }
  }
  if (!Number.isFinite(lo)) return { min: -1, max: 1, step: 1 }
  const step = niceStep(hi - lo + 2 * pad)
  return { min: Math.floor((lo - pad) / step) * step, max: Math.ceil((hi + pad) / step) * step, step }
}

/**
 * Split a track into runs that don't cross the 0/360° azimuth seam (a jump of more than 180°
 * between consecutive samples), so a polyline doesn't streak across the whole plot.
 * Returns runs of sample indices.
 */
export function splitAtAzimuthWrap(azimuth: number[]): number[][] {
  const runs: number[][] = []
  let run: number[] = []
  azimuth.forEach((az, i) => {
    if (i > 0 && Math.abs(az - azimuth[i - 1]) > 180) {
      runs.push(run)
      run = []
    }
    run.push(i)
  })
  if (run.length) runs.push(run)
  return runs
}

/** Index of the sample time nearest to `t` (ms). `times` must be ascending. */
export function nearestTimeIndex(times: number[], t: number): number {
  let lo = 0
  let hi = times.length - 1
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1
    if (times[mid] <= t) lo = mid
    else hi = mid
  }
  return Math.abs(times[hi] - t) < Math.abs(times[lo] - t) ? hi : lo
}

/** Smallest angle between two azimuths, deg. */
function azimuthGap(a: number, b: number): number {
  const d = Math.abs(a - b) % 360
  return d > 180 ? 360 - d : d
}

/** Index of the horizon sample whose azimuth is nearest to `az` (circular). */
export function nearestAzimuthIndex(azimuths: number[], az: number): number {
  let best = 0
  for (let i = 1; i < azimuths.length; i++) {
    if (azimuthGap(azimuths[i], az) < azimuthGap(azimuths[best], az)) best = i
  }
  return best
}
