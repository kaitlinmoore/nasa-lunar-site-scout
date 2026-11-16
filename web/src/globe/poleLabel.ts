// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// Where the "South Pole" cue label goes (Kaitlin, 2026-11-16): to the left of the pole point, moved
// further left until no visible site marker overlaps it, so the polar markers never cover it at the
// start view. Pure (screen pixels only), so it can be unit-tested in Node.

/** A marker on screen, relative to the pole point: centre offset and radius, CSS pixels. */
export type MarkerCircle = { dx: number; dy: number; r: number }

/** A box on screen relative to the pole point (e.g. a near-site feature name), CSS pixels. */
export type RelativeBox = { x0: number; y0: number; x1: number; y1: number }

/**
 * The x of the label's right edge relative to the pole (always < 0). The label is a box of the
 * given size, vertically centred on the pole; it starts `gap` px left of the pole point and steps
 * left past every marker, and every box (the names of the landmarks near the sites; Kaitlin,
 * 2026-11-16), it would touch.
 */
export function poleLabelRightEdge(
  markers: MarkerCircle[],
  label: { width: number; height: number },
  poleRadius: number,
  gap: number,
  boxes: RelativeBox[] = [],
): number {
  let right = -(poleRadius + gap)
  const half = label.height / 2
  // Each step moves the label left of at least one obstacle, so this ends within that many steps.
  for (let step = 0; step <= markers.length + boxes.length; step++) {
    const left = right - label.width
    const lefts = [
      ...markers
        .filter((m) => m.dx + m.r > left - gap && m.dx - m.r < right + gap && Math.abs(m.dy) < half + m.r)
        .map((m) => m.dx - m.r),
      ...boxes
        .filter((b) => b.x1 > left - gap && b.x0 < right + gap && b.y0 < half + gap && b.y1 > -half - gap)
        .map((b) => b.x0),
    ]
    if (lefts.length === 0) return right
    right = Math.min(...lefts) - gap
  }
  return right
}
