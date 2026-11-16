// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// Terrain images for the 2D site view (C5): stream A's PNG + view.json, format 1 (A's proposal in
// reference/logs/engine-progress.md, "terrain images for the 2D view"). Not a contract type yet:
// C api will define GET /api/terrain/view, and this module then switches to it.
//
// Until then the images come from the local data folder (LSS_DATA_DIR/cache/terrain_view), served by
// the dev server only, at TERRAIN_VIEW_BASE (vite.config.ts). Every field the map uses is checked
// before anything is drawn; a file that doesn't match is an error, never a guess.
import { type PolarGrid, polarGrid } from './polarGrid'

/** Where the dev server serves LSS_DATA_DIR/cache/terrain_view/ (vite.config.ts). */
export const TERRAIN_VIEW_BASE = '/dev-terrain-view'

/** view.json, format 1 (only the fields the map uses are typed). */
export type TerrainViewMeta = {
  format: 1
  site_id: string
  view: string
  center_ps_m: [number, number]
  /** [left, bottom, right, top] in grid metres. */
  bounds_ps_m: [number, number, number, number]
  proj4: string
  map_up: string
  pixel_m: number
  width: number
  height: number
  source: { file_id: string; dataset_id: string; url: string }
  hillshade: { file: string; light_azimuth_map_deg: number; light_altitude_deg: number; note: string }
  slope: {
    file: string
    definition: string
    class_edges_deg: number[]
    class_labels: string[]
    nodata: number
    suggested_palette: { light: string[]; dark: string[] }
  }
}

export type TerrainView = {
  meta: TerrainViewMeta
  grid: PolarGrid
  /** Object URL of the hillshade PNG as sent. */
  hillshadeUrl: string
  /** Slope class per pixel, row-major from the top-left (class index, or meta.slope.nodata). */
  slopeClasses: Uint8Array
  /** Object URL of the slope classes drawn in the palette (no-data pixels transparent). */
  slopeUrl: string
}

const isNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)
const isFileName = (v: unknown): v is string => typeof v === 'string' && /^[a-z0-9_]+\.png$/.test(v)
const isColour = (v: unknown): v is string => typeof v === 'string' && /^#[0-9a-f]{6}$/i.test(v)
/** Equal within a millimetre (grid metres are sent as decimals). */
const near = (a: number, b: number) => Math.abs(a - b) < 1e-3

/** Checks a view.json body; throws with the first problem. */
export function checkMeta(raw: unknown, siteId: string, view: string | null = null): TerrainViewMeta {
  const m = raw as TerrainViewMeta
  const fail = (what: string): never => {
    throw new Error(`the terrain image description (view.json) ${what}`)
  }
  if (typeof raw !== 'object' || raw === null) fail('is not an object')
  if (m.format !== 1) fail(`has format ${String(m.format)}; this page reads format 1`)
  if (m.site_id !== siteId) fail(`is for ${String(m.site_id)}, not ${siteId}`)
  if (typeof m.view !== 'string' || !/^[a-z0-9]+$/.test(m.view)) fail('has no view name')
  if (view !== null && m.view !== view) fail(`is for view ${m.view}, not ${view}`)
  const b = m.bounds_ps_m
  if (!Array.isArray(b) || b.length !== 4 || !b.every(isNum) || !(b[2] > b[0] && b[3] > b[1]))
    fail('has bad bounds')
  if (!Number.isInteger(m.width) || !Number.isInteger(m.height) || m.width <= 0 || m.height <= 0)
    fail('has a bad size')
  if (!isNum(m.pixel_m) || m.pixel_m <= 0) fail('has a bad pixel size')
  if (!near(b[2] - b[0], m.width * m.pixel_m) || !near(b[3] - b[1], m.height * m.pixel_m)) {
    fail("has bounds that don't match its size × pixel size")
  }
  // The centre is the served point; the bounds are snapped to the map's pixel grid around it, so the
  // point sits within one pixel of the middle (Site01 pilot: 2.5 m in x and y).
  const c = m.center_ps_m
  if (
    !Array.isArray(c) ||
    c.length !== 2 ||
    !c.every(isNum) ||
    Math.abs(c[0] - (b[0] + b[2]) / 2) > m.pixel_m ||
    Math.abs(c[1] - (b[1] + b[3]) / 2) > m.pixel_m
  ) {
    fail('has a centre (the served point) more than one pixel from the middle of its bounds')
  }
  if (typeof m.proj4 !== 'string') fail('has no projection')
  if (typeof m.source?.url !== 'string' || typeof m.source?.dataset_id !== 'string') fail('has no source')
  if (!isFileName(m.hillshade?.file)) fail('has no hillshade file')
  const s = m.slope
  if (!isFileName(s?.file)) fail('has no slope file')
  if (!Array.isArray(s.class_edges_deg) || !s.class_edges_deg.every(isNum)) fail('has bad slope class edges')
  if (!Array.isArray(s.class_labels) || s.class_labels.length !== s.class_edges_deg.length + 1) {
    fail("has slope labels that don't match its class edges")
  }
  if (!Number.isInteger(s.nodata) || s.nodata < s.class_labels.length || s.nodata > 255)
    fail('has a bad no-data value')
  for (const theme of ['light', 'dark'] as const) {
    const p = s.suggested_palette?.[theme]
    if (!Array.isArray(p) || p.length !== s.class_labels.length || !p.every(isColour)) {
      fail(`has a ${theme} palette that doesn't match its slope classes`)
    }
  }
  return m
}

/** The page's palette: the app has a dark theme only (index.css), so A's dark palette. */
export function slopePalette(meta: TerrainViewMeta): string[] {
  return meta.slope.suggested_palette.dark
}

async function fetchOk(url: string): Promise<Response | null> {
  const res = await fetch(url)
  if (res.status === 404) return null
  if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`)
  return res
}

/**
 * A site's views, each checked, smallest extent first; [] when the site has none. The dev server
 * lists them like the coming GET /api/terrain/views?site_id= (C api, contract 0.13.0), so no view
 * names are built in (A's pilot has "2km" and "10km"; the decided set is "2km" and "wide").
 */
export async function loadViews(siteId: string): Promise<TerrainViewMeta[]> {
  const res = await fetchOk(`${TERRAIN_VIEW_BASE}/${encodeURIComponent(siteId)}/views.json`)
  if (!res) return []
  if (!(res.headers.get('content-type') ?? '').includes('json'))
    throw new Error('the list of terrain views is not JSON')
  const body = (await res.json()) as { views?: unknown }
  if (!Array.isArray(body.views)) throw new Error('the list of terrain views has no views')
  const views = body.views.map((v) => checkMeta(v, siteId))
  if (new Set(views.map((v) => v.view)).size !== views.length)
    throw new Error('the list of terrain views repeats a view')
  return views.sort((a, b) => a.width * a.pixel_m - b.width * b.pixel_m)
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
export function slopeClassesFrom(pixels: ImageData, meta: TerrainViewMeta): Uint8Array {
  const { data } = pixels
  const n = meta.slope.class_labels.length
  const out = new Uint8Array(pixels.width * pixels.height)
  for (let i = 0; i < out.length; i++) {
    const v = data[4 * i]
    if (data[4 * i + 1] !== v || data[4 * i + 2] !== v || data[4 * i + 3] !== 255) {
      throw new Error('the slope image is not plain grey')
    }
    if (v >= n && v !== meta.slope.nodata)
      throw new Error(`the slope image has the value ${v}, which is no class`)
    out[i] = v
  }
  return out
}

async function paletteUrl(classes: Uint8Array, meta: TerrainViewMeta): Promise<string> {
  const rgb = slopePalette(meta).map((c) => [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16)))
  const img = new ImageData(meta.width, meta.height)
  for (let i = 0; i < classes.length; i++) {
    const v = classes[i]
    if (v === meta.slope.nodata) continue // transparent
    img.data.set(rgb[v], 4 * i)
    img.data[4 * i + 3] = 255
  }
  const canvas = new OffscreenCanvas(meta.width, meta.height)
  canvas.getContext('2d')?.putImageData(img, 0, 0)
  return URL.createObjectURL(await canvas.convertToBlob({ type: 'image/png' }))
}

/** Loads and checks a view's images. Call `release` when done with it. */
export async function loadView(meta: TerrainViewMeta): Promise<TerrainView> {
  const grid = polarGrid(meta.proj4)
  const dir = `${TERRAIN_VIEW_BASE}/${encodeURIComponent(meta.site_id)}/${meta.view}`
  const [hill, slope] = await Promise.all([
    fetchOk(`${dir}/${meta.hillshade.file}`),
    fetchOk(`${dir}/${meta.slope.file}`),
  ])
  if (!hill || !slope) throw new Error('an image named in view.json is missing')
  const [hillBlob, slopeBlob] = await Promise.all([hill.blob(), slope.blob()])
  // The hillshade is drawn as sent; decoding it only checks its size.
  await decode(hillBlob, 'hillshade', meta.width, meta.height)
  const slopeClasses = slopeClassesFrom(await decode(slopeBlob, 'slope', meta.width, meta.height), meta)
  return {
    meta,
    grid,
    hillshadeUrl: URL.createObjectURL(hillBlob),
    slopeClasses,
    slopeUrl: await paletteUrl(slopeClasses, meta),
  }
}

export function release(view: TerrainView) {
  URL.revokeObjectURL(view.hillshadeUrl)
  URL.revokeObjectURL(view.slopeUrl)
}

/** The slope class index at a grid point, null outside the image, or meta.slope.nodata. */
export function slopeClassAt(view: TerrainView, x: number, y: number): number | null {
  const [left, , , top] = view.meta.bounds_ps_m
  const col = Math.floor((x - left) / view.meta.pixel_m)
  const row = Math.floor((top - y) / view.meta.pixel_m)
  if (col < 0 || row < 0 || col >= view.meta.width || row >= view.meta.height) return null
  return view.slopeClasses[row * view.meta.width + col]
}
