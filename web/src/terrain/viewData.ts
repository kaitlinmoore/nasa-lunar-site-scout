// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// Terrain images for the 2D site view, contract 0.13.0:
// GET /api/terrain/views?site_id= lists a site's views (TerrainView), and each image is
// GET /api/terrain/view/{site_id}/{view}/{layer}.png (an 8-bit greyscale PNG; a 404 says why in plain
// words). When the live API gives no usable answer, the static copy has the same:
// /static-api/terrain_views.json (StaticIndex.terrain_views) and /static-api/terrain_view/{site_id}/{view}/{layer}.png.
// Every field the map uses is checked before anything is drawn; a view that doesn't fit is an error,
// never a guess.
import { API_BASE, getJson, type Schemas } from '../api/client'
import { STATIC_BASE, staticTerrainViews, withStaticFallback } from '../api/staticFallback'
import type { DataSource } from '../api/source'
import { type PolarGrid, polarGrid } from './polarGrid'

export type TerrainView = Schemas['TerrainView']
type TerrainViewsResponse = Schemas['TerrainViewsResponse']
type Layer = Schemas['TerrainViewLayer']

/** A site's views and where their images come from (the live API, or the static copy). */
export type SiteViews = { views: TerrainView[]; from: 'live' | 'static' }

export type LoadedView = {
  view: TerrainView
  grid: PolarGrid
  /** The served point in the images' grid, m. */
  centerPs: [number, number]
  /** Object URL of the hillshade PNG as sent. */
  hillshadeUrl: string
  /** Slope class per pixel, row-major from the top-left (class index, or slope.nodata); null without a slope image. */
  slopeClasses: Uint8Array | null
  /** Object URL of the slope classes drawn in the palette (no-data pixels transparent); null without one. */
  slopeUrl: string | null
}

const isNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)
const isColour = (v: unknown): v is string => typeof v === 'string' && /^#[0-9a-f]{6}$/i.test(v)
/** Equal within a millimetre (grid metres are sent as decimals). */
const near = (a: number, b: number) => Math.abs(a - b) < 1e-3

/** Checks a TerrainView before it's drawn; throws with the first problem. */
export function checkView(v: TerrainView, siteId: string): TerrainView {
  const fail = (what: string): never => {
    throw new Error(`the terrain view ${String(v.view)} ${what}`)
  }
  if (v.site_id !== siteId) fail(`is for ${String(v.site_id)}, not ${siteId}`)
  if (typeof v.view !== 'string' || !/^[a-z0-9]+$/.test(v.view)) fail('has no usable name')
  const b = v.bounds_ps_m
  if (!Array.isArray(b) || b.length !== 4 || !b.every(isNum) || !(b[2] > b[0] && b[3] > b[1]))
    fail('has bad bounds')
  if (!Number.isInteger(v.width) || !Number.isInteger(v.height) || v.width <= 0 || v.height <= 0)
    fail('has a bad size')
  if (!isNum(v.pixel_m) || v.pixel_m <= 0) fail('has a bad pixel size')
  if (!near(b[2] - b[0], v.width * v.pixel_m) || !near(b[3] - b[1], v.height * v.pixel_m)) {
    fail("has bounds that don't match its size × pixel size")
  }
  if (!isNum(v.center?.lat) || !isNum(v.center?.lon)) fail('has no centre')
  if (!v.layers.includes('hillshade')) fail('has no hillshade image')
  const s = v.slope
  if (v.layers.includes('slope')) {
    if (!s) fail('has a slope image but no slope classes')
    else {
      if (!Array.isArray(s.class_edges_deg) || !s.class_edges_deg.every(isNum))
        fail('has bad slope class edges')
      if (!Array.isArray(s.class_labels) || s.class_labels.length !== s.class_edges_deg.length + 1) {
        fail("has slope labels that don't match its class edges")
      }
      if (!Number.isInteger(s.nodata) || s.nodata < s.class_labels.length || s.nodata > 255) {
        fail('has a bad no-data value')
      }
      for (const p of [s.palette_light, s.palette_dark]) {
        if (!Array.isArray(p) || p.length !== s.class_labels.length || !p.every(isColour)) {
          fail("has a palette that doesn't match its slope classes")
        }
      }
    }
  }
  return v
}

/** The page's slope-class colours: the `--slope-class-<n>` tokens in index.css, one per class. */
function tokenPalette(count: number): string[] | null {
  const style = getComputedStyle(document.documentElement)
  const colours = Array.from({ length: count }, (_, i) => style.getPropertyValue(`--slope-class-${i + 1}`).trim())
  const extra = style.getPropertyValue(`--slope-class-${count + 1}`).trim()
  return colours.every(isColour) && extra === '' ? colours : null
}

/**
 * The page's palette for a view's slope classes: the theme's tokens (2026-11-23:
 * the data's dark palette was five blues that were hard to tell apart over the hillshade) when
 * there is exactly one token per class; otherwise the view's dark palette (the app is dark only).
 * Only the colours change: the classes, their order and their labels are the view's own.
 */
export function slopePalette(slope: NonNullable<TerrainView['slope']>): string[] {
  return tokenPalette(slope.class_labels.length) ?? slope.palette_dark
}

/**
 * A site's views, smallest extent first (the API's order; sorted again here); none when the site has
 * none. Fixture mode has no terrain images.
 */
export async function loadViews(source: DataSource, siteId: string): Promise<SiteViews> {
  if (source === 'fixtures') return { views: [], from: 'static' }
  const pick = (r: TerrainViewsResponse) =>
    r.views
      .filter((v) => v.site_id === siteId)
      .map((v) => checkView(v, siteId))
      .sort((a, b) => a.width * a.pixel_m - b.width * b.pixel_m)
  let from: SiteViews['from'] = 'live'
  const views = await withStaticFallback(
    async () =>
      pick(await getJson<TerrainViewsResponse>(`/api/terrain/views?site_id=${encodeURIComponent(siteId)}`)),
    async () => {
      const r = pick(await staticTerrainViews())
      from = 'static'
      return r
    },
  )
  return { views, from }
}

function imageUrl(from: SiteViews['from'], v: TerrainView, layer: Layer): string {
  const path = `${encodeURIComponent(v.site_id)}/${encodeURIComponent(v.view)}/${layer}.png`
  return from === 'live' ? `${API_BASE}/api/terrain/view/${path}` : `${STATIC_BASE}terrain_view/${path}`
}

/** One image as a PNG blob; a 404 carries the API's plain reason. */
async function fetchImage(from: SiteViews['from'], v: TerrainView, layer: Layer): Promise<Blob> {
  const url = imageUrl(from, v, layer)
  let res: Response
  try {
    res = await fetch(url)
  } catch (e) {
    throw new Error(`the ${layer} image couldn't be loaded (${e instanceof Error ? e.message : String(e)})`)
  }
  if (!res.ok) {
    let reason = ''
    try {
      const body = (await res.json()) as { detail?: { reason?: unknown } }
      if (typeof body.detail?.reason === 'string') reason = body.detail.reason
    } catch {
      // not JSON: the status alone
    }
    throw new Error(reason ? `${reason} (${layer})` : `the ${layer} image: HTTP ${res.status}`)
  }
  // The static host answers a missing file with the web page (status 200), so check the type.
  if (!(res.headers.get('content-type') ?? '').startsWith('image/png')) {
    throw new Error(`the ${layer} image isn't a PNG`)
  }
  return res.blob()
}

/** The pixels of a PNG exactly as stored (no colour management, no premultiplication). */
async function decode(blob: Blob, what: string, width: number, height: number): Promise<ImageData> {
  const bitmap = await createImageBitmap(blob, { colorSpaceConversion: 'none', premultiplyAlpha: 'none' })
  try {
    if (bitmap.width !== width || bitmap.height !== height) {
      throw new Error(
        `the ${what} image is ${bitmap.width} × ${bitmap.height} px, not ${width} × ${height} as described`,
      )
    }
    const ctx = new OffscreenCanvas(width, height).getContext('2d', { willReadFrequently: true })
    if (!ctx) throw new Error('this browser cannot read image pixels')
    ctx.drawImage(bitmap, 0, 0)
    return ctx.getImageData(0, 0, width, height)
  } finally {
    bitmap.close()
  }
}

/** Slope classes from the 8-bit grey slope PNG; every pixel must be a class or no-data. */
export function slopeClassesFrom(pixels: ImageData, slope: NonNullable<TerrainView['slope']>): Uint8Array {
  const { data } = pixels
  const n = slope.class_labels.length
  const out = new Uint8Array(pixels.width * pixels.height)
  for (let i = 0; i < out.length; i++) {
    const v = data[4 * i]
    if (data[4 * i + 1] !== v || data[4 * i + 2] !== v || data[4 * i + 3] !== 255) {
      throw new Error('the slope image is not plain grey')
    }
    if (v >= n && v !== slope.nodata) throw new Error(`the slope image has the value ${v}, which is no class`)
    out[i] = v
  }
  return out
}

async function paletteUrl(classes: Uint8Array, v: TerrainView, slope: NonNullable<TerrainView['slope']>) {
  const rgb = slopePalette(slope).map((c) => [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16)))
  const img = new ImageData(v.width, v.height)
  for (let i = 0; i < classes.length; i++) {
    const c = classes[i]
    if (c === slope.nodata) continue // transparent
    img.data.set(rgb[c], 4 * i)
    img.data[4 * i + 3] = 255
  }
  const canvas = new OffscreenCanvas(v.width, v.height)
  canvas.getContext('2d')?.putImageData(img, 0, 0)
  return URL.createObjectURL(await canvas.convertToBlob({ type: 'image/png' }))
}

/** Loads and checks a view's images. Call `release` when done with it. */
export async function loadView(from: SiteViews['from'], v: TerrainView): Promise<LoadedView> {
  const grid = polarGrid(v.proj4)
  const centerPs = grid.fromLatLon(v.center.lat, v.center.lon)
  const [l, b, r, t] = v.bounds_ps_m
  // The bounds snap to the pixel grid around the served point, so it lies within one pixel of the middle.
  if (Math.abs(centerPs[0] - (l + r) / 2) > v.pixel_m || Math.abs(centerPs[1] - (b + t) / 2) > v.pixel_m) {
    throw new Error(
      `the terrain view ${v.view}'s centre is more than one pixel from the middle of its bounds`,
    )
  }
  const withSlope = v.layers.includes('slope') && v.slope !== null && v.slope !== undefined
  const [hillBlob, slopeBlob] = await Promise.all([
    fetchImage(from, v, 'hillshade'),
    withSlope ? fetchImage(from, v, 'slope') : Promise.resolve(null),
  ])
  // The hillshade is drawn as sent; decoding it only checks its size.
  await decode(hillBlob, 'hillshade', v.width, v.height)
  let slopeClasses: Uint8Array | null = null
  let slopeUrl: string | null = null
  if (slopeBlob && v.slope) {
    slopeClasses = slopeClassesFrom(await decode(slopeBlob, 'slope', v.width, v.height), v.slope)
    slopeUrl = await paletteUrl(slopeClasses, v, v.slope)
  }
  return { view: v, grid, centerPs, hillshadeUrl: URL.createObjectURL(hillBlob), slopeClasses, slopeUrl }
}

export function release(l: LoadedView) {
  URL.revokeObjectURL(l.hillshadeUrl)
  if (l.slopeUrl) URL.revokeObjectURL(l.slopeUrl)
}

/** The slope class index at a grid point: null outside the image or without a slope image, or slope.nodata. */
export function slopeClassAt(l: LoadedView, x: number, y: number): number | null {
  if (!l.slopeClasses) return null
  const [left, , , top] = l.view.bounds_ps_m
  const col = Math.floor((x - left) / l.view.pixel_m)
  const row = Math.floor((top - y) / l.view.pixel_m)
  if (col < 0 || row < 0 || col >= l.view.width || row >= l.view.height) return null
  return l.slopeClasses[row * l.view.width + col]
}
