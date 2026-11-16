// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// Screen-space declutter for the globe's names (Kaitlin, 2026-11-16): names are placed in priority
// order, and a name that would overlap anything already placed (a site marker or label, the South Pole
// label, or a name placed before it) is hidden. Pure (screen pixels only), so it can be unit-tested in Node.

/** A box on screen, CSS pixels: left, top, right, bottom. */
export type ScreenBox = { x0: number; y0: number; x1: number; y1: number }

/** Whether two boxes come closer than `gap` px. */
export function overlaps(a: ScreenBox, b: ScreenBox, gap: number): boolean {
  return a.x0 < b.x1 + gap && b.x0 < a.x1 + gap && a.y0 < b.y1 + gap && b.y0 < a.y1 + gap
}

/**
 * Which candidates to show, in their given (priority) order: each is shown unless its box (null =
 * not drawable now) overlaps an obstacle or a candidate already shown.
 */
export function declutter(boxes: (ScreenBox | null)[], obstacles: ScreenBox[], gap: number): boolean[] {
  const placed = [...obstacles]
  return boxes.map((box) => {
    if (!box || placed.some((p) => overlaps(box, p, gap))) return false
    placed.push(box)
    return true
  })
}
