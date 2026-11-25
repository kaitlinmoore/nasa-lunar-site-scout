// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// Where the "South Pole" cue label goes. The project author, 2026-11-16: beside the pole point, clear of the
// site markers (and of the names of the landmarks near the sites), so nothing covers it. Changed
// 2026-11-23: stepping only leftwards took it far from the point when zoomed in (120 km: past
// Shackleton, reading as a label of the ground beside it), so it now tries all four sides and uses
// the one where it fits closest to the point; it never covers the point itself, and site labels
// count as obstacles too. Pure (screen pixels only), so it can be unit-tested in Node.

/** A box on screen relative to the pole point (a marker, a site label, a feature name), CSS px. */
export type RelativeBox = { x0: number; y0: number; x1: number; y1: number }

export type PoleSide = 'left' | 'right' | 'above' | 'below'

/** Preference when two sides fit equally close: left (the original place), then right, above, below. */
const SIDES: readonly PoleSide[] = ['left', 'right', 'above', 'below']

/** Unit direction of each side in screen coordinates (y grows downwards). */
const DIRECTION: Record<PoleSide, { x: number; y: number }> = {
  left: { x: -1, y: 0 },
  right: { x: 1, y: 0 },
  above: { x: 0, y: -1 },
  below: { x: 0, y: 1 },
}

/** The label's placement: its side, its centre relative to the pole point, and how far its near edge is. */
export type PolePlacement = { side: PoleSide; dx: number; dy: number; distance: number }

/**
 * How far from the pole the label's near edge must be on one side so that it touches no obstacle
 * (with `gap` around each). It starts `gap` px beyond the pole point and moves outwards past every
 * obstacle it would touch.
 */
function clearDistance(
  side: PoleSide,
  obstacles: RelativeBox[],
  label: { width: number; height: number },
  poleRadius: number,
  gap: number,
): number {
  const d = DIRECTION[side]
  const horizontal = d.x !== 0
  const along = horizontal ? label.width : label.height
  const across = horizontal ? label.height : label.width
  let near = poleRadius + gap
  // Each step moves the label past at least one more obstacle, so this ends within that many steps.
  for (let step = 0; step <= obstacles.length; step++) {
    // The label's box along the side's axis (s, outwards) and across it (t), relative to the pole.
    const s0 = near
    const s1 = near + along
    let needed = near
    for (const b of obstacles) {
      const [bs0, bs1] = horizontal ? [b.x0 * d.x, b.x1 * d.x] : [b.y0 * d.y, b.y1 * d.y]
      const [bt0, bt1] = horizontal ? [b.y0, b.y1] : [b.x0, b.x1]
      const sMin = Math.min(bs0, bs1)
      const sMax = Math.max(bs0, bs1)
      const overlaps =
        sMax > s0 - gap && sMin < s1 + gap && bt1 > -across / 2 - gap && bt0 < across / 2 + gap
      if (overlaps) needed = Math.max(needed, sMax + gap)
    }
    if (needed === near) return near
    near = needed
  }
  return near
}

/**
 * Where the label goes: the side where it fits closest to the pole point. The label stays on
 * `previous` while that side is within `stickiness` px of the best, so it doesn't jump between
 * sides as the view moves.
 */
export function placePoleLabel(
  obstacles: RelativeBox[],
  label: { width: number; height: number },
  poleRadius: number,
  gap: number,
  previous: PoleSide | null = null,
  stickiness = 8,
): PolePlacement {
  const options = SIDES.map((side) => ({ side, distance: clearDistance(side, obstacles, label, poleRadius, gap) }))
  let best = options[0]
  for (const o of options) if (o.distance < best.distance) best = o
  const kept = previous ? options.find((o) => o.side === previous) : undefined
  const chosen = kept && kept.distance <= best.distance + stickiness ? kept : best
  const d = DIRECTION[chosen.side]
  const half = d.x !== 0 ? label.width / 2 : label.height / 2
  const centre = chosen.distance + half
  return { side: chosen.side, dx: d.x * centre, dy: d.y * centre, distance: chosen.distance }
}
