// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// Where the "South Pole" cue label goes (Kaitlin, 2026-11-16): to the left of the pole point, moved
// further left until no visible site marker overlaps it, so the polar markers never cover it at the
// start view. Pure (screen pixels only), so it can be unit-tested in Node.

/** A marker on screen, relative to the pole point: centre offset and radius, CSS pixels. */
export type MarkerCircle = { dx: number; dy: number; r: number }

/**
 * The x of the label's right edge relative to the pole (always < 0). The label is a box of the
 * given size, vertically centred on the pole; it starts `gap` px left of the pole point and steps
 * left past every marker it would touch.
 */
export function poleLabelRightEdge(
  markers: MarkerCircle[],
  label: { width: number; height: number },
  poleRadius: number,
  gap: number,
): number {
  let right = -(poleRadius + gap)
  // Each step moves the box left of at least one marker, so this ends within markers.length steps.
  for (let step = 0; step <= markers.length; step++) {
    const left = right - label.width
    const hits = markers.filter(
      (m) => m.dx + m.r > left - gap && m.dx - m.r < right + gap && Math.abs(m.dy) < label.height / 2 + m.r,
    )
    if (hits.length === 0) return right
    right = Math.min(...hits.map((m) => m.dx - m.r)) - gap
  }
  return right
}
