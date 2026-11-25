// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// IAU feature names on the globe (contract 0.14.0), in the shared label style (labelStyle.ts) but
// quieter than the site labels: their own colour and font, centred on the feature, no marker.
//
// Zoom rule (the project author, 2026-11-16):
// - A name shows while the camera is within FEATURE_ZOOM.distancePerDiameter (12) × its diameter of the
//   feature's centre: the bigger the feature, the further out its name appears.
// - Craters and montes that contain or neighbour a curated site (rim within nearSite.neighbourKm of the
//   site, at least nearSite.minDiameterKm wide) show from nearSite.showWithinM, so the landmarks that
//   matter for the sites (Shackleton, de Gerlache, Malapert, Haworth, Nobile, Cabeus…) are named whenever
//   the sites are in view below the start view.
// - Declutter (declutter.ts): site markers, site labels and the South Pole label come first, then the
//   near-site names, then the others largest first; a name that would overlap one placed before it is
//   hidden.
// - Satellite features ("Cabeus B") are not drawn.
// Names whose centre is beyond the Moon's limb are hidden, like the site markers.
import {
  Cartesian2,
  Cartesian3,
  Color,
  Ellipsoid,
  EllipsoidalOccluder,
  HorizontalOrigin,
  LabelCollection,
  SceneTransforms,
  VerticalOrigin,
  type Viewer,
} from 'cesium'
import type { Site } from '../api/client'
import { declutter, type ScreenBox } from './declutter'
import type { FeatureLabelRow } from './featureLabelData'
import { globeLabelStyle, labelBoxSize } from './labelStyle'

export const FEATURE_ZOOM = {
  /** A name shows while the camera is within this many diameters of the feature's centre. */
  distancePerDiameter: 12,
  /** Names near the curated sites show from further out. */
  nearSite: {
    /** IAU types that count: craters and montes. */
    types: ['AA', 'MO'],
    /** The feature's rim (centre + diameter / 2) within this distance of a site, km. */
    neighbourKm: 10,
    /** Smaller features aren't boosted (they'd be named far beyond where they can be seen). */
    minDiameterKm: 10,
    /** Shown while the camera is within this distance of the feature, m (the start view is ~5000 km). */
    showWithinM: 2_000_000,
  },
  /** Minimum space between names (and between a name and a site marker or label), CSS px. */
  gapPx: 3,
}

const MOON_RADIUS_KM = 1737.4

/** Great-circle distance on the 1737.4 km sphere, km. */
function surfaceKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const r = Math.PI / 180
  const c =
    Math.sin(lat1 * r) * Math.sin(lat2 * r) +
    Math.cos(lat1 * r) * Math.cos(lat2 * r) * Math.cos((lon1 - lon2) * r)
  return MOON_RADIUS_KM * Math.acos(Math.min(1, Math.max(-1, c)))
}

/** The ids of the features whose names are boosted near the curated sites. */
export function nearSiteFeatureIds(rows: FeatureLabelRow[], sites: Site[]): Set<number> {
  const rule = FEATURE_ZOOM.nearSite
  const ids = new Set<number>()
  for (const [id, , type, lat, lon, d] of rows) {
    if (!rule.types.includes(type) || d < rule.minDiameterKm) continue
    if (sites.some((s) => surfaceKm(s.location.lat, s.location.lon, lat, lon) <= d / 2 + rule.neighbourKm)) {
      ids.add(id)
    }
  }
  return ids
}

function token(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

/**
 * Adds the names to the viewer's scene. `obstacles` gives the screen boxes names must keep clear of
 * (site markers and labels, the South Pole label), each frame. Returns `detach` (removes them) and
 * `nearSiteBoxes`: where the near-site names would go this frame, shown or not, so the South Pole
 * label can step around them (poleLabel.ts) before they're placed.
 */
export function attachFeatureLabels(
  viewer: Viewer,
  rows: FeatureLabelRow[],
  sites: Site[],
  obstacles: () => ScreenBox[],
): { detach: () => void; nearSiteBoxes: () => ScreenBox[] } {
  const scene = viewer.scene
  const labels = scene.primitives.add(new LabelCollection({ scene })) as LabelCollection
  const font = token('--globe-feature-label-font') || '500 12px system-ui, sans-serif'
  const style = globeLabelStyle(font, Color.fromCssColorString(token('--globe-feature-label') || '#d0d7de'))
  const boosted = nearSiteFeatureIds(rows, sites)
  type Placed = {
    label: ReturnType<LabelCollection['add']>
    position: Cartesian3
    showWithinM: number
    size: { width: number; height: number }
  }
  const near: Placed[] = []
  const others: Placed[] = []
  for (const [id, name, , lat, lon, diameterKm] of rows) {
    if (!(diameterKm > 0)) continue // no size, no zoom level: not drawn
    const position = Cartesian3.fromDegrees(lon, lat, 0, Ellipsoid.MOON)
    const label = labels.add({
      position,
      text: name,
      ...style,
      show: false,
      horizontalOrigin: HorizontalOrigin.CENTER,
      verticalOrigin: VerticalOrigin.CENTER,
      disableDepthTestDistance: Number.POSITIVE_INFINITY,
    })
    const ownM = FEATURE_ZOOM.distancePerDiameter * diameterKm * 1000
    const isNear = boosted.has(id)
    const showWithinM = isNear ? Math.max(ownM, FEATURE_ZOOM.nearSite.showWithinM) : ownM
    ;(isNear ? near : others).push({ label, position, showWithinM, size: labelBoxSize(name, font) })
  }
  // Priority: near-site names first, then the others; rows come largest first, so each group is too.
  const order = [...near, ...others]

  const occluder = new EllipsoidalOccluder(Ellipsoid.MOON, scene.camera.positionWC)
  const win = new Cartesian2()
  /** Where a name would go this frame, or null if it isn't drawable (too far, beyond the limb, off screen). */
  const boxOf = (p: Placed): ScreenBox | null => {
    const camera = scene.camera.positionWC
    if (Cartesian3.distance(camera, p.position) > p.showWithinM) return null
    occluder.cameraPosition = camera
    if (!occluder.isPointVisible(p.position)) return null
    const c = SceneTransforms.worldToWindowCoordinates(scene, p.position, win)
    const w = scene.canvas.clientWidth
    const h = scene.canvas.clientHeight
    if (
      !c ||
      c.x < -p.size.width ||
      c.y < -p.size.height ||
      c.x > w + p.size.width ||
      c.y > h + p.size.height
    ) {
      return null
    }
    const half = { x: p.size.width / 2, y: p.size.height / 2 }
    return { x0: c.x - half.x, y0: c.y - half.y, x1: c.x + half.x, y1: c.y + half.y }
  }
  const place = () => {
    const boxes = order.map(boxOf)
    const show = declutter(boxes, obstacles(), FEATURE_ZOOM.gapPx)
    order.forEach((p, i) => {
      if (p.label.show !== show[i]) p.label.show = show[i]
    })
  }
  const remove = scene.preRender.addEventListener(place)
  scene.requestRender()
  return {
    detach: () => {
      remove()
      if (!scene.isDestroyed()) {
        scene.primitives.remove(labels)
        scene.requestRender()
      }
    },
    nearSiteBoxes: () => near.map(boxOf).filter((b): b is ScreenBox => b !== null),
  }
}
