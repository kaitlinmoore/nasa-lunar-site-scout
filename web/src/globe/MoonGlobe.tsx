// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// C7a minimal globe: Cesium Moon (ion asset 2684829), display only.
// - No numbers come from Cesium. Its terrain sits ~2.5 km above LOLA heights, so site markers are
//   clamped to the rendered surface (CLAMP_TO_3D_TILE) and every value shown elsewhere comes
//   from our API.
// - Markers ignore the depth test (a clamped marker is otherwise half-buried in the terrain it
//   sits on) and are hidden instead when they're beyond the Moon's limb from the camera.
// - Lighting is a "flashlight" that follows the camera, and Cesium's Sun and Moon are hidden:
//   Cesium's own Sun direction would paint illumination that isn't ours, and illumination is
//   exactly what this tool computes.
// Loaded lazily (a separate chunk) so the site screen never pays for Cesium.
import {
  BoundingSphere,
  Cartesian2,
  Cartesian3,
  Cesium3DTileset,
  Color,
  defined,
  DirectionalLight,
  Ellipsoid,
  EllipsoidalOccluder,
  Entity,
  HeadingPitchRange,
  HeightReference,
  Ion,
  LabelStyle,
  Math as CesiumMath,
  ScreenSpaceEventType,
  VerticalOrigin,
  Viewer,
} from 'cesium'
import 'cesium/Build/Cesium/Widgets/widgets.css'
import { useEffect, useRef, useState } from 'react'
import type { Site } from '../api/client'

/** Cesium ion asset: "Cesium Moon" (imagery + LOLA terrain in one 3D tileset). */
const CESIUM_MOON_ASSET_ID = 2684829

/** Initial view: looking at the south pole from 45° above the horizontal, 3000 km away. */
const INITIAL_VIEW = { lat: -90, lon: 0, pitchDeg: -45, rangeM: 3_000_000 }

/** A CSS token's value from :root, so marker colours, sizes and fonts live in index.css too. */
function token(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

/** A numeric CSS token (e.g. "12px" -> 12), or `fallback` if unset. */
function tokenNumber(name: string, fallback: number): number {
  const n = parseFloat(token(name))
  return Number.isFinite(n) ? n : fallback
}

type Status = { kind: 'loading' } | { kind: 'ready' } | { kind: 'error'; message: string }

export default function MoonGlobe({
  sites,
  token: ionToken,
  onSelect,
}: {
  sites: Site[]
  token: string
  onSelect: (siteId: string) => void
}) {
  const container = useRef<HTMLDivElement>(null)
  const onSelectRef = useRef(onSelect)
  const [status, setStatus] = useState<Status>({ kind: 'loading' })

  useEffect(() => {
    onSelectRef.current = onSelect
  }, [onSelect])

  useEffect(() => {
    if (!container.current) return
    let viewer: Viewer | undefined
    let cancelled = false
    try {
      Ellipsoid.default = Ellipsoid.MOON
      Ion.defaultAccessToken = ionToken
      viewer = new Viewer(container.current, {
        globe: false,
        skyAtmosphere: false,
        baseLayerPicker: false,
        geocoder: false,
        homeButton: false,
        sceneModePicker: false,
        navigationHelpButton: false,
        animation: false,
        timeline: false,
        fullscreenButton: false,
        infoBox: false,
        selectionIndicator: false,
        scene3DOnly: true,
        requestRenderMode: true,
      })
    } catch (e) {
      // e.g. no WebGL in this browser. Reported asynchronously, like the tileset's failures.
      const message = e instanceof Error ? e.message : String(e)
      queueMicrotask(() => {
        if (!cancelled) setStatus({ kind: 'error', message })
      })
      return () => {
        cancelled = true
      }
    }
    const v = viewer
    const scene = v.scene

    // Display-only lighting: a light that always points where the camera looks.
    scene.sun = undefined
    scene.moon = undefined
    const light = new DirectionalLight({ direction: Cartesian3.clone(scene.camera.directionWC) })
    scene.light = light
    scene.preRender.addEventListener(() => {
      light.direction = Cartesian3.clone(scene.camera.directionWC, light.direction)
    })

    const pole = Cartesian3.fromDegrees(INITIAL_VIEW.lon, INITIAL_VIEW.lat)
    scene.camera.flyToBoundingSphere(new BoundingSphere(pole, 0), {
      offset: new HeadingPitchRange(0, CesiumMath.toRadians(INITIAL_VIEW.pitchDeg), INITIAL_VIEW.rangeM),
      duration: 0,
    })

    // Site markers: clamped to the rendered tileset surface; no height is read back.
    const markers: { entity: Entity; position: Cartesian3 }[] = []
    const markerColor = Color.fromCssColorString(token('--globe-marker') || 'white')
    const outlineColor = Color.fromCssColorString(token('--globe-marker-outline') || 'black')
    const labelFont = token('--globe-label-font') || '14px sans-serif'
    const markerSize = tokenNumber('--globe-marker-size', 12)
    const outlineWidth = tokenNumber('--globe-marker-outline-width', 2)
    const labelOffset = tokenNumber('--globe-label-offset', 14)
    for (const site of sites) {
      const position = Cartesian3.fromDegrees(site.location.lon, site.location.lat)
      const entity = v.entities.add(
        new Entity({
          id: site.id,
          name: site.name,
          position,
          point: {
            pixelSize: markerSize,
            color: markerColor,
            outlineColor,
            outlineWidth,
            heightReference: HeightReference.CLAMP_TO_3D_TILE,
            disableDepthTestDistance: Number.POSITIVE_INFINITY,
          },
          label: {
            text: site.name,
            font: labelFont,
            fillColor: markerColor,
            outlineColor,
            outlineWidth: outlineWidth + 1,
            style: LabelStyle.FILL_AND_OUTLINE,
            verticalOrigin: VerticalOrigin.BOTTOM,
            pixelOffset: new Cartesian2(0, -labelOffset),
            heightReference: HeightReference.CLAMP_TO_3D_TILE,
            disableDepthTestDistance: Number.POSITIVE_INFINITY,
          },
        }),
      )
      markers.push({ entity, position })
    }

    // With the depth test off, hide markers on the far side of the Moon (beyond the limb).
    const occluder = new EllipsoidalOccluder(Ellipsoid.MOON, scene.camera.positionWC)
    scene.preRender.addEventListener(() => {
      occluder.cameraPosition = scene.camera.positionWC
      let changed = false
      for (const m of markers) {
        const visible = occluder.isPointVisible(m.position)
        if (m.entity.show !== visible) {
          m.entity.show = visible
          changed = true
        }
      }
      if (changed) scene.requestRender()
    })

    // Click a marker -> open its site screen. Pointer cursor over markers.
    const pickedSiteId = (pos: Cartesian2): string | undefined => {
      const picked = scene.pick(pos)
      return defined(picked) && picked.id instanceof Entity ? picked.id.id : undefined
    }
    const handler = v.screenSpaceEventHandler
    handler.removeInputAction(ScreenSpaceEventType.LEFT_DOUBLE_CLICK) // no entity tracking
    handler.setInputAction((e: { position: Cartesian2 }) => {
      const id = pickedSiteId(e.position)
      if (id) onSelectRef.current(id)
    }, ScreenSpaceEventType.LEFT_CLICK)
    handler.setInputAction((e: { endPosition: Cartesian2 }) => {
      v.canvas.style.cursor = pickedSiteId(e.endPosition) ? 'pointer' : ''
    }, ScreenSpaceEventType.MOUSE_MOVE)

    Cesium3DTileset.fromIonAssetId(CESIUM_MOON_ASSET_ID, { enableCollision: true })
      .then((tileset) => {
        if (cancelled || v.isDestroyed()) return
        scene.primitives.add(tileset)
        scene.requestRender()
        setStatus({ kind: 'ready' })
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setStatus({ kind: 'error', message: e instanceof Error ? e.message : String(e) })
        }
      })

    return () => {
      cancelled = true
      if (!v.isDestroyed()) v.destroy()
    }
  }, [sites, ionToken])

  return (
    <div className="globe">
      <div ref={container} className="globe-canvas" />
      {status.kind === 'loading' && <p className="globe-status muted">Loading the Cesium Moon…</p>}
      {status.kind === 'error' && (
        <div className="banner error globe-status" role="alert">
          <strong>Couldn't show the globe.</strong> The site list below still works.
          <div className="mono">{status.message}</div>
        </div>
      )}
    </div>
  )
}
