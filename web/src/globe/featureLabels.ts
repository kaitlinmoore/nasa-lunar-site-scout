// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// IAU feature names on the globe (contract 0.14.0), in the shared label style (labelStyle.ts) but
// quieter than the site labels: their own colour and font, centred on the feature, no marker.
//
// Zoom rule (PROPOSED, for Kaitlin to tune): a name shows while the camera is within
// FEATURE_ZOOM.distancePerDiameter × its diameter of the feature's centre, so the bigger the feature, the
// further out its name appears, and the number of names on screen stays about the same at every zoom.
// Satellite features ("Cabeus B") are not drawn (FEATURE_ZOOM.satellite) until Kaitlin decides.
// Names whose centre is beyond the Moon's limb are hidden, like the site markers.
import {
  Cartesian3,
  Color,
  DistanceDisplayCondition,
  Ellipsoid,
  EllipsoidalOccluder,
  HorizontalOrigin,
  LabelCollection,
  VerticalOrigin,
  type Viewer,
} from 'cesium'
import type { FeatureLabelRow } from './featureLabelData'
import { globeLabelStyle } from './labelStyle'

export const FEATURE_ZOOM = {
  /** A name shows while the camera is within this many diameters of the feature's centre. */
  distancePerDiameter: 12,
  /** Satellite features: not drawn (proposal: never, or only when zoomed in close). */
  satellite: 'never' as const,
}

function token(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

/** Adds the names to the viewer's scene; returns a function that removes them. */
export function attachFeatureLabels(
  viewer: Viewer,
  rows: FeatureLabelRow[],
  distancePerDiameter = FEATURE_ZOOM.distancePerDiameter,
): () => void {
  const scene = viewer.scene
  const labels = scene.primitives.add(new LabelCollection({ scene })) as LabelCollection
  const style = globeLabelStyle(
    token('--globe-feature-label-font') || '500 12px system-ui, sans-serif',
    Color.fromCssColorString(token('--globe-feature-label') || '#d0d7de'),
  )
  const placed: { label: ReturnType<LabelCollection['add']>; position: Cartesian3 }[] = []
  for (const [, name, , lat, lon, diameterKm] of rows) {
    if (!(diameterKm > 0)) continue // no size, no zoom level: not drawn
    const position = Cartesian3.fromDegrees(lon, lat, 0, Ellipsoid.MOON)
    const label = labels.add({
      position,
      text: name,
      ...style,
      horizontalOrigin: HorizontalOrigin.CENTER,
      verticalOrigin: VerticalOrigin.CENTER,
      disableDepthTestDistance: Number.POSITIVE_INFINITY,
      distanceDisplayCondition: new DistanceDisplayCondition(0, distancePerDiameter * diameterKm * 1000),
    })
    placed.push({ label, position })
  }
  const occluder = new EllipsoidalOccluder(Ellipsoid.MOON, scene.camera.positionWC)
  const hideFarSide = () => {
    occluder.cameraPosition = scene.camera.positionWC
    for (const p of placed) {
      const visible = occluder.isPointVisible(p.position)
      if (p.label.show !== visible) p.label.show = visible
    }
  }
  const remove = scene.preRender.addEventListener(hideFarSide)
  scene.requestRender()
  return () => {
    remove()
    if (!scene.isDestroyed()) {
      scene.primitives.remove(labels)
      scene.requestRender()
    }
  }
}
