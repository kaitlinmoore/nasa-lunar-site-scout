// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// The 2D map itself (OpenLayers): hillshade, slope classes on top, and the site point, in the images'
// own polar stereographic grid. No reprojection: every image pixel is drawn where view.json puts it.
import 'ol/ol.css'
import { useEffect, useRef } from 'react'
import OlMap from 'ol/Map'
import View from 'ol/View'
import ScaleLine from 'ol/control/ScaleLine'
import { defaults as defaultControls } from 'ol/control/defaults'
import { platformModifierKeyOnly } from 'ol/events/condition'
import Feature from 'ol/Feature'
import Point from 'ol/geom/Point'
import MouseWheelZoom from 'ol/interaction/MouseWheelZoom'
import { defaults as defaultInteractions } from 'ol/interaction/defaults'
import ImageLayer from 'ol/layer/Image'
import VectorLayer from 'ol/layer/Vector'
import Projection from 'ol/proj/Projection'
import ImageStatic from 'ol/source/ImageStatic'
import VectorSource from 'ol/source/Vector'
import { Circle, Fill, Stroke, Style } from 'ol/style'
import type { TerrainView } from './viewData'

/** How far in you can zoom: this many screen pixels per image pixel. */
const MAX_MAGNIFICATION = 8
/** Slope classes start at this opacity over the hillshade, so the relief shows through; the card has a control. */
export const DEFAULT_SLOPE_OPACITY = 0.5

export type PointerInfo = { x: number; y: number } | null

export default function TerrainMap({
  view,
  sitePoint,
  showSlope,
  slopeOpacity,
  onPointer,
}: {
  view: TerrainView
  sitePoint: [number, number]
  showSlope: boolean
  /** 0 to 1. */
  slopeOpacity: number
  onPointer: (p: PointerInfo) => void
}) {
  const target = useRef<HTMLDivElement>(null)
  const slopeLayer = useRef<ImageLayer<ImageStatic> | null>(null)
  const pointer = useRef(onPointer)
  useEffect(() => {
    pointer.current = onPointer
  }, [onPointer])

  useEffect(() => {
    const { meta, grid } = view
    const extent = meta.bounds_ps_m
    // Ground metres per grid metre come from the stereographic scale factor (polarGrid.ts), so the
    // scale bar is right on the Moon; OpenLayers' default would measure on the Earth.
    const projection = new Projection({
      code: `lss-moon-polar-stereographic:${meta.site_id}:${meta.view}`,
      units: 'm',
      extent,
      getPointResolution: (resolution, point) => resolution / grid.scale(point[0], point[1]),
    })
    const hillshade = new ImageLayer({
      source: new ImageStatic({ url: view.hillshadeUrl, imageExtent: extent, projection }),
    })
    const slope = new ImageLayer({
      // Class colours must stay exact: no smoothing between pixels.
      source: new ImageStatic({ url: view.slopeUrl, imageExtent: extent, projection, interpolate: false }),
    })
    slopeLayer.current = slope
    const site = new VectorLayer({
      source: new VectorSource({ features: [new Feature(new Point(sitePoint))] }),
      style: new Style({
        image: new Circle({
          radius: 6,
          fill: new Fill({ color: 'rgba(0, 0, 0, 0)' }),
          stroke: new Stroke({ color: '#ffffff', width: 2.5 }),
        }),
      }),
    })
    const map = new OlMap({
      target: target.current ?? undefined,
      layers: [hillshade, slope, site],
      controls: defaultControls({ attribution: false, rotate: false }).extend([
        new ScaleLine({ units: 'metric' }),
      ]),
      // The map sits in a scrolling panel: the wheel scrolls the panel; Ctrl/Cmd + wheel zooms.
      interactions: defaultInteractions({ mouseWheelZoom: false }).extend([
        new MouseWheelZoom({ condition: platformModifierKeyOnly }),
      ]),
      view: new View({
        projection,
        extent,
        showFullExtent: true,
        constrainOnlyCenter: false,
        minResolution: meta.pixel_m / MAX_MAGNIFICATION,
      }),
    })
    const v = map.getView()
    v.fit(extent)
    v.setMaxZoom(v.getZoomForResolution(meta.pixel_m / MAX_MAGNIFICATION) ?? 28)
    v.setMinZoom(v.getZoom() ?? 0)
    map.on('pointermove', (e) => pointer.current({ x: e.coordinate[0], y: e.coordinate[1] }))
    const leave = () => pointer.current(null)
    const viewport = map.getViewport()
    viewport?.addEventListener('pointerleave', leave)
    return () => {
      viewport?.removeEventListener('pointerleave', leave)
      map.setTarget(undefined)
      slopeLayer.current = null
    }
  }, [view, sitePoint])

  useEffect(() => {
    slopeLayer.current?.setVisible(showSlope)
    slopeLayer.current?.setOpacity(slopeOpacity)
  }, [showSlope, slopeOpacity, view])

  return <div ref={target} className="terrain-map" />
}
