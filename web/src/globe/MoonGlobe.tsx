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
  type Camera,
  Cartesian2,
  Cartesian3,
  Cesium3DTileset,
  Color,
  defined,
  DirectionalLight,
  Ellipsoid,
  EllipsoidalOccluder,
  Entity,
  HeightReference,
  Ion,
  LabelStyle,
  type PerspectiveFrustum,
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

/**
 * Start view: the whole Moon in frame, seen from above 60° S on the first curated site's
 * meridian, north up, so the south pole (and Site01) sit clearly in the lower part of the disc.
 */
const START_VIEW = { lat: -60, margin: 1.12 }

/** Zoom: wheel speed (Cesium's default is 5) and limits, as heights above the Moon ellipsoid. */
const ZOOM = { factor: 2, minHeightM: 20_000, maxHeightM: 12_000_000 }

/**
 * Camera position and orientation that fit the whole Moon in the canvas: look at the Moon's
 * centre from above (lat, lon), north up, at the distance where the limb fits the narrower
 * field of view with `margin`.
 */
function startView(camera: Camera, canvas: HTMLCanvasElement, lon: number) {
  const radius = Ellipsoid.MOON.maximumRadius
  const frustum = camera.frustum as PerspectiveFrustum
  const aspect = canvas.clientWidth / Math.max(1, canvas.clientHeight)
  const fovy = frustum.fovy ?? CesiumMath.toRadians(60)
  const fovx = 2 * Math.atan(Math.tan(fovy / 2) * aspect)
  const distance = (radius * START_VIEW.margin) / Math.sin(Math.min(fovx, fovy) / 2)
  const out = Cartesian3.normalize(Cartesian3.fromDegrees(lon, START_VIEW.lat), new Cartesian3())
  const destination = Cartesian3.multiplyByScalar(out, distance, new Cartesian3())
  const direction = Cartesian3.negate(out, new Cartesian3())
  // "Up" on screen = the Moon's north axis, made perpendicular to the view direction.
  const north = Cartesian3.UNIT_Z
  const along = Cartesian3.multiplyByScalar(direction, Cartesian3.dot(north, direction), new Cartesian3())
  const up = Cartesian3.normalize(Cartesian3.subtract(north, along, new Cartesian3()), new Cartesian3())
  return { destination, orientation: { direction, up } }
}

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

/** On-screen zoom buttons: each press moves this fraction of the current height (within limits). */
const BUTTON_ZOOM = { inFraction: 0.35, outFraction: 0.6 }

/** Entity id of the "South pole" label; it isn't a site and can't be selected. */
const SOUTH_POLE_ID = 'south-pole-label'

type Controls = { zoomIn: () => void; zoomOut: () => void; reset: () => void }

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
  const controls = useRef<Controls | null>(null)
  const [status, setStatus] = useState<Status>({ kind: 'loading' })
  // "You're looking at the Moon's south pole" note: shown at the start view, hidden once the
  // view moves, shown again after Reset (Kaitlin, 2026-11-15: both the pole label and this note).
  const [poleNote, setPoleNote] = useState(true)

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

    // Zoom: gentler wheel, and limits so the Moon never vanishes or the camera dives into it.
    const controller = scene.screenSpaceCameraController
    controller.zoomFactor = ZOOM.factor
    controller.minimumZoomDistance = ZOOM.minHeightM
    controller.maximumZoomDistance = ZOOM.maxHeightM

    const startLon = sites[0]?.location.lon ?? 0
    scene.camera.setView(startView(scene.camera, v.canvas, startLon))
    // Hide the south-pole note on the user's first move (drag, wheel, pinch or a zoom button).
    // Not on camera.moveStart: Cesium fires that on the first frame after setView, too.
    const hideNote = () => setPoleNote(false)
    for (const type of [
      ScreenSpaceEventType.LEFT_DOWN,
      ScreenSpaceEventType.RIGHT_DOWN,
      ScreenSpaceEventType.MIDDLE_DOWN,
      ScreenSpaceEventType.WHEEL,
      ScreenSpaceEventType.PINCH_START,
    ]) {
      v.screenSpaceEventHandler.setInputAction(hideNote, type)
    }

    // On-screen controls: zoom by a fraction of the current height, clamped to the same limits
    // as the wheel; reset flies back to the start view.
    const height = () => scene.camera.positionCartographic.height
    controls.current = {
      zoomIn: () => {
        hideNote()
        const h = height()
        scene.camera.zoomIn(Math.max(0, Math.min(h * BUTTON_ZOOM.inFraction, h - ZOOM.minHeightM)))
        scene.requestRender()
      },
      zoomOut: () => {
        hideNote()
        const h = height()
        scene.camera.zoomOut(Math.max(0, Math.min(h * BUTTON_ZOOM.outFraction, ZOOM.maxHeightM - h)))
        scene.requestRender()
      },
      reset: () =>
        scene.camera.flyTo({
          ...startView(scene.camera, v.canvas, startLon),
          duration: 1,
          complete: () => setPoleNote(true),
        }),
    }

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

    // "South pole" label at 90° S: below its small point (site labels sit above theirs, so
    // Site01's label, ~60 km away, doesn't collide). Not a site: it can't be selected.
    const polePosition = Cartesian3.fromDegrees(0, -90)
    const poleColor = Color.fromCssColorString(token('--globe-pole') || 'white')
    const poleEntity = v.entities.add(
      new Entity({
        id: SOUTH_POLE_ID,
        position: polePosition,
        point: {
          pixelSize: tokenNumber('--globe-pole-size', 6),
          color: poleColor,
          outlineColor,
          outlineWidth,
          heightReference: HeightReference.CLAMP_TO_3D_TILE,
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
        label: {
          text: 'South pole',
          font: token('--globe-pole-font') || '12px sans-serif',
          fillColor: poleColor,
          outlineColor,
          outlineWidth: outlineWidth + 1,
          style: LabelStyle.FILL_AND_OUTLINE,
          verticalOrigin: VerticalOrigin.TOP,
          pixelOffset: new Cartesian2(0, labelOffset - 4),
          heightReference: HeightReference.CLAMP_TO_3D_TILE,
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
      }),
    )
    markers.push({ entity: poleEntity, position: polePosition })

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

    // Click a site marker -> open its site screen. Pointer cursor over site markers only.
    const siteIds = new Set(sites.map((s) => s.id))
    const pickedSiteId = (pos: Cartesian2): string | undefined => {
      const picked = scene.pick(pos)
      const id = defined(picked) && picked.id instanceof Entity ? picked.id.id : undefined
      return id !== undefined && siteIds.has(id) ? id : undefined
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
      controls.current = null
      if (!v.isDestroyed()) v.destroy()
    }
  }, [sites, ionToken])

  return (
    <div className="globe">
      <div ref={container} className="globe-canvas" />
      {status.kind === 'ready' && poleNote && (
        <p className="globe-note" role="note">
          You're looking at the Moon's south pole (north is up).
        </p>
      )}
      {status.kind !== 'error' && (
        <div className="globe-zoom" role="group" aria-label="Globe view">
          <button
            type="button"
            aria-label="Zoom in"
            title="Zoom in"
            onClick={() => controls.current?.zoomIn()}
          >
            +
          </button>
          <button
            type="button"
            aria-label="Zoom out"
            title="Zoom out"
            onClick={() => controls.current?.zoomOut()}
          >
            −
          </button>
          <button
            type="button"
            aria-label="Reset view"
            title="Reset view (whole Moon, south pole)"
            onClick={() => controls.current?.reset()}
          >
            ⟲
          </button>
        </div>
      )}
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
