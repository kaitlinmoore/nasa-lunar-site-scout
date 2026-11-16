// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// 2D site view (C5, Phase 2 step 3.6): stream A's terrain images for the site, hillshade with the
// slope classes on top, in a plain card (layout waits for Kaitlin's layout pass). A separate chunk,
// so OpenLayers and proj4 load only when this card is shown.
import { useEffect, useMemo, useState } from 'react'
import type { Site } from '../api/client'
import TerrainMap, { DEFAULT_SLOPE_OPACITY, type PointerInfo } from './TerrainMap'
import {
  loadView,
  loadViews,
  release,
  slopeClassAt,
  slopePalette,
  type TerrainView,
  type TerrainViewMeta,
} from './viewData'

type Load<T> = { kind: 'loading' } | { kind: 'ok'; data: T } | { kind: 'error'; message: string }

const message = (e: unknown) => (e instanceof Error ? e.message : String(e))

/** "2 × 2 km, 5 m pixels", from the description itself. */
function viewLabel(m: TerrainViewMeta): string {
  const [l, b, r, t] = m.bounds_ps_m
  return `${(r - l) / 1000} × ${(t - b) / 1000} km, ${m.pixel_m} m pixels`
}

/** "89.4527° S, 137.1487° W" for the pointer position (converted here, so rounded). */
function pointerLatLon(lat: number, lon: number): string {
  return `${Math.abs(lat).toFixed(4)}° ${lat < 0 ? 'S' : 'N'}, ${Math.abs(lon).toFixed(4)}° ${lon < 0 ? 'W' : 'E'}`
}

export default function TerrainSection({ site }: { site: Site }) {
  const [metas, setMetas] = useState<Load<TerrainViewMeta[]>>({ kind: 'loading' })
  const [viewId, setViewId] = useState<string | null>(null)
  // The loaded view, tagged with the description it's for (a different one means: still loading).
  const [loadedView, setLoadedView] = useState<{ meta: TerrainViewMeta; load: Load<TerrainView> } | null>(
    null,
  )
  const [showSlope, setShowSlope] = useState(true)
  const [slopeOpacity, setSlopeOpacity] = useState(DEFAULT_SLOPE_OPACITY)

  useEffect(() => {
    let cancelled = false
    loadViews(site.id)
      .then((list) => {
        if (cancelled) return
        setMetas({ kind: 'ok', data: list })
        setViewId(list[0]?.view ?? null) // the smallest extent first
      })
      .catch((e: unknown) => !cancelled && setMetas({ kind: 'error', message: message(e) }))
    return () => {
      cancelled = true
    }
  }, [site.id])

  const views = metas.kind === 'ok' ? metas.data : []
  const meta = views.find((m) => m.view === viewId)
  useEffect(() => {
    if (!meta) return
    let cancelled = false
    let loaded: TerrainView | null = null
    loadView(meta)
      .then((v) => {
        if (cancelled) return release(v)
        loaded = v
        setLoadedView({ meta, load: { kind: 'ok', data: v } })
      })
      .catch(
        (e: unknown) => !cancelled && setLoadedView({ meta, load: { kind: 'error', message: message(e) } }),
      )
    return () => {
      cancelled = true
      if (loaded) release(loaded)
    }
  }, [meta])

  const view = loadedView && loadedView.meta === meta ? loadedView.load : null
  const data = view?.kind === 'ok' ? view.data : null
  // The site's point (from the site list) in the images' grid; the images must be centred on it.
  const placed = useMemo(() => {
    if (!data) return null
    const point = data.grid.fromLatLon(site.location.lat, site.location.lon)
    const [cx, cy] = data.meta.center_ps_m
    const offset = Math.hypot(point[0] - cx, point[1] - cy)
    return { point, offset, ok: offset <= data.meta.pixel_m }
  }, [data, site.location.lat, site.location.lon])

  let body
  if (metas.kind === 'loading') body = <p className="muted">Loading the terrain images…</p>
  else if (metas.kind === 'error') body = <TerrainError message={metas.message} />
  else if (views.length === 0) {
    body = <p className="muted">No terrain images for this site yet.</p>
  } else if (!view || view.kind === 'loading') body = <p className="muted">Loading the terrain images…</p>
  else if (view.kind === 'error') body = <TerrainError message={view.message} />
  else if (placed && !placed.ok) {
    body = (
      <TerrainError
        message={`these images are centred ${placed.offset.toFixed(1)} m from this site's location (more than one ${view.data.meta.pixel_m} m pixel), so they aren't shown`}
      />
    )
  } else if (data && placed) {
    body = (
      <TerrainBody
        key={data.meta.view}
        view={data}
        sitePoint={placed.point}
        showSlope={showSlope}
        slopeOpacity={slopeOpacity}
      />
    )
  }

  return (
    <section className="card terrain-view">
      <h2>Terrain map</h2>
      <div className="banner notice" role="note">
        Pilot terrain images from stream A, read from the local data folder by the dev server. The API doesn't
        serve them yet.
      </div>
      {views.length > 0 && (
        <div className="terrain-controls">
          <fieldset>
            <legend className="visually-hidden">Map extent</legend>
            {views.map((m) => (
              <label key={m.view}>
                <input
                  type="radio"
                  name={`terrain-view-${site.id}`}
                  checked={viewId === m.view}
                  onChange={() => setViewId(m.view)}
                />{' '}
                {viewLabel(m)}
              </label>
            ))}
          </fieldset>
          <label>
            <input type="checkbox" checked={showSlope} onChange={(e) => setShowSlope(e.target.checked)} />{' '}
            Slope classes
          </label>
          <label>
            Opacity{' '}
            <input
              type="range"
              min={10}
              max={100}
              step={10}
              value={Math.round(slopeOpacity * 100)}
              disabled={!showSlope}
              onChange={(e) => setSlopeOpacity(Number(e.target.value) / 100)}
            />{' '}
            {Math.round(slopeOpacity * 100)} %
          </label>
        </div>
      )}
      {body}
    </section>
  )
}

function TerrainError({ message }: { message: string }) {
  return (
    <div className="banner error" role="alert">
      <strong>Can't draw the terrain map:</strong> {message}.
    </div>
  )
}

function TerrainBody({
  view,
  sitePoint,
  showSlope,
  slopeOpacity,
}: {
  view: TerrainView
  sitePoint: [number, number]
  showSlope: boolean
  slopeOpacity: number
}) {
  const [pointer, setPointer] = useState<PointerInfo>(null)
  const { meta, grid } = view
  const palette = slopePalette(meta)
  // True north at the map centre, degrees clockwise from up (grid north): straight away from the
  // south pole, which is the grid origin.
  const [cx, cy] = meta.center_ps_m
  const northDeg = (Math.atan2(cx, cy) * 180) / Math.PI
  const cls = pointer ? slopeClassAt(view, pointer.x, pointer.y) : null
  const [lat, lon] = pointer && cls !== null ? grid.toLatLon(pointer.x, pointer.y) : [0, 0]

  return (
    <>
      <div className="terrain-map-wrap">
        <TerrainMap
          view={view}
          sitePoint={sitePoint}
          showSlope={showSlope}
          slopeOpacity={slopeOpacity}
          onPointer={setPointer}
        />
        <div
          className="terrain-north"
          title="True north (the south pole is the opposite way)"
          aria-hidden="true"
        >
          <span style={{ transform: `rotate(${northDeg}deg)` }}>↑</span>
          <small>N</small>
        </div>
      </div>
      <p className="terrain-pointer muted" aria-live="off">
        {pointer && cls !== null ? (
          <>
            Pointer: {pointerLatLon(lat, lon)} · slope{' '}
            {cls === meta.slope.nodata ? 'no data' : meta.slope.class_labels[cls]}
          </>
        ) : (
          'Point at the map to read the slope class there. Drag to move; Ctrl + wheel or + / − to zoom.'
        )}
      </p>
      <ul className="legend">
        <li>Slope{showSlope ? '' : ' (hidden)'}:</li>
        {meta.slope.class_labels.map((label, i) => (
          <li key={label}>
            <span
              className="legend-swatch terrain-swatch"
              style={{ background: palette[i], opacity: slopeOpacity }}
              aria-hidden="true"
            />{' '}
            {label}
          </li>
        ))}
        <li>
          <span className="terrain-site-swatch" aria-hidden="true" /> Site point
        </li>
      </ul>
      <div className="definition">
        <p>
          Up is grid north: {meta.map_up}. The N arrow shows true north at the map's centre; the south pole
          lies the opposite way. Grid: south polar stereographic on the {grid.radiusM / 1000} km lunar sphere.
        </p>
        <p>
          Shading: {meta.hillshade.note} (light from {meta.hillshade.light_azimuth_map_deg}° on the map,{' '}
          {meta.hillshade.light_altitude_deg}° high). Slope: {meta.slope.definition}.
        </p>
        <p>
          Source: <a href={meta.source.url}>{meta.source.dataset_id}</a> ({meta.source.file_id}),{' '}
          {meta.pixel_m} m pixels, {meta.width} × {meta.height} px.
        </p>
      </div>
    </>
  )
}
