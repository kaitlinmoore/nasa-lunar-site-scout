// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// One label style for everything the globe writes on the Moon: site names, the "South Pole" cue, and
// later the IAU landmark labels (the project author, 2026-11-16). The surface runs from black shadow to bright
// grey, so a text outline alone isn't enough: each label also sits on a subtle dark backing. Every
// value is a token in index.css (theme "Penumbra" sets the fonts; the outline and backing stay).
import { Cartesian2, Color, LabelStyle } from 'cesium'

function token(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

function tokenNumber(name: string, fallback: number): number {
  const n = parseFloat(token(name))
  return Number.isFinite(n) ? n : fallback
}

/** The backing's padding around the text, CSS px (also needed to measure a label's box). */
export function labelPadding(): { x: number; y: number } {
  return { x: tokenNumber('--globe-label-bg-padding-x', 6), y: tokenNumber('--globe-label-bg-padding-y', 3) }
}

/**
 * Cesium label options shared by every globe label: text colour and font are the caller's, the
 * outline and backing are common. Spread into an Entity's `label`.
 */
export function globeLabelStyle(font: string, fill: Color) {
  const pad = labelPadding()
  return {
    font,
    fillColor: fill,
    outlineColor: Color.fromCssColorString(token('--globe-label-outline') || '#0d1117'),
    outlineWidth: tokenNumber('--globe-label-outline-width', 3),
    style: LabelStyle.FILL_AND_OUTLINE,
    showBackground: true,
    backgroundColor: Color.fromCssColorString(token('--globe-label-bg') || 'rgba(13, 17, 23, 0.72)'),
    backgroundPadding: new Cartesian2(pad.x, pad.y),
  }
}

/**
 * Load the fonts the globe's labels use (self-hosted web fonts, main.tsx) before Cesium draws any
 * label: Cesium rasterises a label's text when it's created, and a font that hasn't loaded yet
 * would be drawn (and measured) in the fallback face. A font that fails to load is drawn in the
 * fallback face; the globe isn't held back by it.
 */
export async function loadGlobeLabelFonts(): Promise<void> {
  if (!('fonts' in document)) return
  const fonts = ['--globe-label-font', '--globe-feature-label-font', '--globe-pole-font']
    .map(token)
    .filter((f) => f !== '')
  await Promise.allSettled(fonts.map((f) => document.fonts.load(f)))
}

const sizes = new Map<string, { width: number; height: number }>()
let measureCtx: CanvasRenderingContext2D | null | undefined

/**
 * A label's box on screen, CSS px, backing included (for the declutter and the pole label): text
 * width from the canvas's own measure, height from the font size. Cached per font and text.
 */
export function labelBoxSize(text: string, font: string): { width: number; height: number } {
  const key = `${font}\n${text}`
  const hit = sizes.get(key)
  if (hit) return hit
  if (measureCtx === undefined) measureCtx = document.createElement('canvas').getContext('2d')
  const pad = labelPadding()
  const px = Number(/(\d+(?:\.\d+)?)px/.exec(font)?.[1] ?? 12)
  let width = text.length * px * 0.6
  if (measureCtx) {
    measureCtx.font = font
    width = measureCtx.measureText(text).width
  }
  const size = { width: width + 2 * pad.x, height: px * 1.2 + 2 * pad.y }
  sizes.set(key, size)
  return size
}
