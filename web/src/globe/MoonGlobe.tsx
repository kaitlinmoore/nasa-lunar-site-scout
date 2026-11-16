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
// - Site selection (Kaitlin, 2026-11-15, layout (c)): a click shows a card anchored next to the
//   marker (`card`, positioned here after every render); "See details" opens the side panel and
//   the globe zooms toward the site (`focusSiteId`); closing it returns to the whole Moon.
// Loaded lazily (a separate chunk) so the site screen never pays for Cesium.
import {
  BoundingSphere,
  type Camera,
  Cartesian2,
  Cartesian3,
  Cesium3DTileset,
  Color,
  ConstantProperty,
  defined,
  DirectionalLight,
  DistanceDisplayCondition,
  Ellipsoid,
  EllipsoidalOccluder,
  Entity,
  HeadingPitchRange,
  HeightReference,
  Ion,
  type PerspectiveFrustum,
  Math as CesiumMath,
  SceneTransforms,
  ScreenSpaceEventType,
  HorizontalOrigin,
  VerticalOrigin,
  Viewer,
} from 'cesium'
import 'cesium/Build/Cesium/Widgets/widgets.css'
import { type ReactNode, useEffect, useRef, useState } from 'react'
import { displayName } from '../siteNames'
import { globeLabelStyle, labelPadding } from './labelStyle'
import { type MarkerCircle, poleLabelRightEdge } from './poleLabel'
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
  // Cesium's `fov` is the angle across the wider side. Derive both angles from the canvas's
  // current size: `frustum.fovy` lags a layout change (e.g. the side panel closing) by a frame.
  const fov = frustum.fov ?? CesiumMath.toRadians(60)
  const fovy = aspect <= 1 ? fov : 2 * Math.atan(Math.tan(fov / 2) / aspect)
  const fovx = aspect <= 1 ? 2 * Math.atan(Math.tan(fov / 2) * aspect) : fov
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

/** Place labels are in title case (Kaitlin, 2026-11-16), like the sites' short names. */
const POLE_LABEL_TEXT = 'South Pole'
/** Entity id of the "South Pole" label; it isn't a site and can't be selected. */
const SOUTH_POLE_ID = 'south-pole-label'

/** Space between the "South Pole" label and the pole point or a site marker, CSS px (poleLabel.ts). */
const POLE_LABEL_GAP_PX = 4

/** "See details" view: the site from 55° above its horizon, 900 km away, so the region around it stays in view. */
const FOCUS_VIEW = { pitchDeg: -55, rangeM: 900_000, durationS: 1.2 }

/**
 * Card placement next to its marker, in CSS pixels: gap from the marker (wide enough to clear the
 * "South Pole" label beside Site01), margin from the canvas edge.
 */
const CARD = { gap: 36, margin: 8, raise: 24 }

/**
 * Site labels show only when the camera is this close to the site (Kaitlin, 2026-11-15, readiness
 * fix P2): further out, the polar sites' labels pile into an unreadable stack. The crowded-site test
 * separated the markers at about 180 km. The "South Pole" cue label isn't affected.
 */
const SITE_LABEL_MAX_DISTANCE_M = 300_000

/** Click tolerance in CSS pixels around the cursor when collecting the markers it hits. */
const PICK_SIZE_PX = 10

/** Several site markers under one click (readiness fix P3): a chooser at the click point. */
type Chooser = { x: number; y: number; ids: string[]; flipX: boolean; flipY: boolean }

type Controls = {
  zoomIn: () => void
  zoomOut: () => void
  reset: () => void
  /** Zoom toward a site (the side panel is open). `instant` for a deep link. */
  focusSite: (siteId: string, instant?: boolean) => void
  /** Turn the globe so a site's marker is on screen (a list click on a hidden site). */
  showSite: (siteId: string) => void
  /** Re-place the card and hide the selected site's label (after the selection or card changed). */
  refresh: () => void
  /** Restyle markers so pinned sites stand out. */
  setPinned: (siteIds: string[]) => void
}

export default function MoonGlobe({
  sites,
  token: ionToken,
  onSelect,
  selectedSiteId,
  focusSiteId,
  pinnedSiteIds,
  card,
}: {
  sites: Site[]
  token: string
  /** A site marker was clicked (its id), or empty space was (null). */
  onSelect: (siteId: string | null) => void
  /** The site whose card is shown, if any. */
  selectedSiteId: string | null
  /** The site whose side panel is open (the globe zooms toward it), if any. */
  focusSiteId: string | null
  /** Pinned sites: drawn with a distinct marker (ring colour, size, ★ before the name). */
  pinnedSiteIds: string[]
  /** The card's content, anchored next to the selected site's marker. */
  card: ReactNode
}) {
  const container = useRef<HTMLDivElement>(null)
  const cardAnchor = useRef<HTMLDivElement>(null)
  const selectedRef = useRef(selectedSiteId)
  const focusRef = useRef(focusSiteId)
  const pinnedRef = useRef(pinnedSiteIds)
  const onSelectRef = useRef(onSelect)
  const controls = useRef<Controls | null>(null)
  const [status, setStatus] = useState<Status>({ kind: 'loading' })
  // "You're looking at the Moon's south pole" note: shown at the start view, hidden once the
  // view moves, shown again after Reset (Kaitlin, 2026-11-15: both the pole label and this note).
  const [poleNote, setPoleNote] = useState(true)
  const [chooser, setChooser] = useState<Chooser | null>(null)

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
    const onUserInput = () => {
      hideNote()
      setChooser(null)
    }
    for (const type of [
      ScreenSpaceEventType.LEFT_DOWN,
      ScreenSpaceEventType.RIGHT_DOWN,
      ScreenSpaceEventType.MIDDLE_DOWN,
      ScreenSpaceEventType.WHEEL,
      ScreenSpaceEventType.PINCH_START,
    ]) {
      v.screenSpaceEventHandler.setInputAction(onUserInput, type)
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
      focusSite: (siteId, instant = false) => {
        const position = positions.get(siteId)
        if (!position) return
        hideNote()
        scene.camera.flyToBoundingSphere(new BoundingSphere(position, 0), {
          offset: new HeadingPitchRange(0, CesiumMath.toRadians(FOCUS_VIEW.pitchDeg), FOCUS_VIEW.rangeM),
          duration: instant ? 0 : FOCUS_VIEW.durationS,
        })
      },
      showSite: (siteId) => {
        const position = positions.get(siteId)
        if (!position || onScreen(position)) return
        hideNote()
        // Same height as now, looking at the site, so it comes into view without a jump in scale.
        scene.camera.flyToBoundingSphere(new BoundingSphere(position, 0), {
          offset: new HeadingPitchRange(0, CesiumMath.toRadians(-80), Math.max(height(), 1_500_000)),
          duration: 1,
        })
      },
      refresh: () => {
        syncLabels()
        placeCard()
        scene.requestRender()
      },
      setPinned: (siteIds) => {
        const pinned = new Set(siteIds)
        for (const site of sites) {
          const entity = v.entities.getById(site.id)
          if (!entity?.point || !entity.label) continue
          const isPinned = pinned.has(site.id)
          entity.point.outlineColor = new ConstantProperty(isPinned ? pinColor : outlineColor)
          entity.point.outlineWidth = new ConstantProperty(isPinned ? pinOutlineWidth : outlineWidth)
          entity.point.pixelSize = new ConstantProperty(isPinned ? pinSize : markerSize)
          entity.label.text = new ConstantProperty(isPinned ? `★ ${displayName(site)}` : displayName(site))
        }
        scene.requestRender()
      },
    }

    // Site markers: clamped to the rendered tileset surface; no height is read back.
    const markers: { entity: Entity; position: Cartesian3 }[] = []
    const positions = new Map(
      sites.map((s) => [s.id, Cartesian3.fromDegrees(s.location.lon, s.location.lat)] as const),
    )
    const markerColor = Color.fromCssColorString(token('--globe-marker') || 'white')
    const outlineColor = Color.fromCssColorString(token('--globe-marker-outline') || 'black')
    const labelFont = token('--globe-label-font') || '14px sans-serif'
    const markerSize = tokenNumber('--globe-marker-size', 12)
    const outlineWidth = tokenNumber('--globe-marker-outline-width', 2)
    const labelOffset = tokenNumber('--globe-label-offset', 14)
    const pinColor = Color.fromCssColorString(token('--globe-pin') || 'deepskyblue')
    const pinSize = tokenNumber('--globe-pin-size', 15)
    const pinOutlineWidth = tokenNumber('--globe-pin-outline-width', 3)
    for (const site of sites) {
      const position = positions.get(site.id) as Cartesian3
      const entity = v.entities.add(
        new Entity({
          id: site.id,
          name: displayName(site),
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
            text: displayName(site),
            ...globeLabelStyle(labelFont, markerColor),
            verticalOrigin: VerticalOrigin.BOTTOM,
            pixelOffset: new Cartesian2(0, -labelOffset),
            heightReference: HeightReference.CLAMP_TO_3D_TILE,
            disableDepthTestDistance: Number.POSITIVE_INFINITY,
            distanceDisplayCondition: new DistanceDisplayCondition(0, SITE_LABEL_MAX_DISTANCE_M),
          },
        }),
      )
      markers.push({ entity, position })
    }

    // "South Pole" label at 90° S, left of its small point and kept clear of the site markers
    // (placed every frame below; Kaitlin, 2026-11-16). Not a site: it can't be selected.
    const polePosition = Cartesian3.fromDegrees(0, -90)
    const poleColor = Color.fromCssColorString(token('--globe-pole') || 'white')
    const poleFont = token('--globe-pole-font') || '12px sans-serif'
    const poleRadius = tokenNumber('--globe-pole-size', 6) / 2 + outlineWidth
    const poleLabelBox = (() => {
      const ctx = document.createElement('canvas').getContext('2d')
      if (ctx) ctx.font = poleFont
      const m = ctx?.measureText(POLE_LABEL_TEXT)
      const height = m ? m.actualBoundingBoxAscent + m.actualBoundingBoxDescent : 12
      // + the dark backing around the text on both sides (labelStyle.ts)
      const pad = labelPadding()
      return { width: (m?.width ?? 70) + 2 * pad.x, height: height + 2 * pad.y }
    })()
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
          text: POLE_LABEL_TEXT,
          ...globeLabelStyle(poleFont, poleColor),
          verticalOrigin: VerticalOrigin.CENTER,
          horizontalOrigin: HorizontalOrigin.RIGHT,
          pixelOffset: new Cartesian2(-(poleRadius + POLE_LABEL_GAP_PX), 0),
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

    // Keep the "South Pole" label clear of the visible site markers (poleLabel.ts).
    let poleLabelRight = Number.NaN
    scene.preRender.addEventListener(() => {
      const pole = SceneTransforms.worldToWindowCoordinates(scene, polePosition)
      if (!pole || !poleEntity.label) return
      const circles: MarkerCircle[] = []
      for (const m of markers) {
        if (m.entity === poleEntity || !m.entity.show || !m.entity.point) continue
        const win = SceneTransforms.worldToWindowCoordinates(scene, m.position)
        if (!win) continue
        const size = m.entity.point.pixelSize?.getValue() ?? markerSize
        const outline = m.entity.point.outlineWidth?.getValue() ?? outlineWidth
        circles.push({ dx: win.x - pole.x, dy: win.y - pole.y, r: size / 2 + outline })
      }
      const right = Math.round(poleLabelRightEdge(circles, poleLabelBox, poleRadius, POLE_LABEL_GAP_PX))
      if (right !== poleLabelRight) {
        poleLabelRight = right
        poleEntity.label.pixelOffset = new ConstantProperty(new Cartesian2(right, 0))
        scene.requestRender()
      }
    })

    // The card: anchored next to the selected site's marker after every render; hidden when the
    // site is beyond the limb or off screen. Flips to the marker's left near the right edge.
    const onScreen = (position: Cartesian3): boolean => {
      if (!occluder.isPointVisible(position)) return false
      const win = SceneTransforms.worldToWindowCoordinates(scene, position)
      return (
        !!win && win.x >= 0 && win.y >= 0 && win.x <= v.canvas.clientWidth && win.y <= v.canvas.clientHeight
      )
    }
    const placeCard = () => {
      const el = cardAnchor.current
      if (!el) return
      const id = selectedRef.current
      const position = id ? positions.get(id) : undefined
      const win =
        position && onScreen(position) ? SceneTransforms.worldToWindowCoordinates(scene, position) : undefined
      if (!win) {
        el.style.visibility = 'hidden'
        return
      }
      const w = v.canvas.clientWidth
      const h = v.canvas.clientHeight
      const cw = el.offsetWidth
      const ch = el.offsetHeight
      let x = win.x + CARD.gap
      if (x + cw > w - CARD.margin) x = win.x - CARD.gap - cw
      x = Math.max(CARD.margin, Math.min(x, w - cw - CARD.margin))
      const y = Math.max(CARD.margin, Math.min(win.y - CARD.raise, h - ch - CARD.margin))
      el.style.left = `${x}px`
      el.style.top = `${y}px`
      el.style.visibility = 'visible'
    }
    scene.postRender.addEventListener(placeCard)

    // While a site's card is open, hide that site's own marker label: the card shows the name,
    // and the label would sit under the card (Kaitlin's follow-up, Phase 2 step 3.1).
    const syncLabels = () => {
      for (const site of sites) {
        const label = v.entities.getById(site.id)?.label
        if (label) label.show = new ConstantProperty(site.id !== selectedRef.current)
      }
    }

    // Click: every site marker under the cursor (within PICK_SIZE_PX). One -> its card; several ->
    // a chooser listing them (readiness fix P3; the top marker alone hid the others); none -> no
    // card. Pointer cursor over site markers.
    const siteIds = new Set(sites.map((s) => s.id))
    const siteOrder = new Map(sites.map((s, i) => [s.id, i]))
    const pickedSiteId = (pos: Cartesian2): string | undefined => {
      const picked = scene.pick(pos)
      const id = defined(picked) && picked.id instanceof Entity ? picked.id.id : undefined
      return id !== undefined && siteIds.has(id) ? id : undefined
    }
    const pickedSiteIds = (pos: Cartesian2): string[] => {
      const ids: string[] = []
      for (const picked of scene.drillPick(pos, 100, PICK_SIZE_PX, PICK_SIZE_PX)) {
        const id = defined(picked) && picked.id instanceof Entity ? picked.id.id : undefined
        if (id !== undefined && siteIds.has(id) && !ids.includes(id)) ids.push(id)
      }
      // In site-list order, like the list under the globe (not the order the picks came back in).
      return ids.sort((a, b) => (siteOrder.get(a) ?? 0) - (siteOrder.get(b) ?? 0))
    }
    const handler = v.screenSpaceEventHandler
    handler.removeInputAction(ScreenSpaceEventType.LEFT_DOUBLE_CLICK) // no entity tracking
    handler.setInputAction((e: { position: Cartesian2 }) => {
      const ids = pickedSiteIds(e.position)
      if (ids.length > 1) {
        onSelectRef.current(null)
        setChooser({
          x: e.position.x,
          y: e.position.y,
          ids,
          flipX: e.position.x > v.canvas.clientWidth / 2,
          flipY: e.position.y > v.canvas.clientHeight / 2,
        })
      } else {
        setChooser(null)
        onSelectRef.current(ids[0] ?? null)
      }
    }, ScreenSpaceEventType.LEFT_CLICK)
    handler.setInputAction((e: { endPosition: Cartesian2 }) => {
      v.canvas.style.cursor = pickedSiteId(e.endPosition) ? 'pointer' : ''
    }, ScreenSpaceEventType.MOUSE_MOVE)

    controls.current.setPinned(pinnedRef.current)

    // Deep link to a site's panel: start zoomed toward it.
    if (focusRef.current) controls.current.focusSite(focusRef.current, true)

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

  // Escape closes the chooser.
  useEffect(() => {
    if (!chooser) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setChooser(null)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [chooser])

  // Selection: re-place the card; bring a hidden site into view (e.g. picked from the list).
  useEffect(() => {
    selectedRef.current = selectedSiteId
    if (selectedSiteId) controls.current?.showSite(selectedSiteId)
    controls.current?.refresh()
  }, [selectedSiteId, card])

  // Pinned sites: restyle their markers whenever the pins change.
  const pinnedKey = pinnedSiteIds.join('\n')
  useEffect(() => {
    pinnedRef.current = pinnedKey ? pinnedKey.split('\n') : []
    controls.current?.setPinned(pinnedRef.current)
  }, [pinnedKey])

  // Side panel: zoom toward its site when it opens or changes; back to the whole Moon when it closes.
  useEffect(() => {
    const previous = focusRef.current
    focusRef.current = focusSiteId
    if (focusSiteId && focusSiteId !== previous) controls.current?.focusSite(focusSiteId)
    else if (!focusSiteId && previous) controls.current?.reset()
  }, [focusSiteId])

  return (
    <div className="globe">
      <div ref={container} className="globe-canvas" />
      <div ref={cardAnchor} className="globe-card-anchor" hidden={!card || status.kind === 'error'}>
        {status.kind !== 'error' && card}
      </div>
      {chooser && (
        <div
          className={`globe-chooser${chooser.flipX ? ' flip-x' : ''}${chooser.flipY ? ' flip-y' : ''}`}
          style={{ left: chooser.x, top: chooser.y }}
          role="dialog"
          aria-label={`${chooser.ids.length} sites here`}
        >
          <div className="globe-chooser-head">
            {chooser.ids.length} sites here
            <button type="button" aria-label="Close" title="Close" onClick={() => setChooser(null)}>
              ✕
            </button>
          </div>
          <ul>
            {chooser.ids.map((id) => (
              <li key={id}>
                <button
                  type="button"
                  className="link-button"
                  onClick={() => {
                    setChooser(null)
                    onSelectRef.current(id)
                  }}
                >
                  {(() => {
                    const s = sites.find((x) => x.id === id)
                    return s ? displayName(s) : id
                  })()}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
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
      {status.kind === 'error' && card && <div className="globe-card-static">{card}</div>}
    </div>
  )
}
