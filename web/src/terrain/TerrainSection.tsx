// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// 2D site view (C5, Phase 2 step 3.6): the site's precomputed terrain images (contract 0.13.0),
// hillshade with the slope classes on top, in a plain card (layout waits for Kaitlin's layout pass).
// A separate chunk, so OpenLayers and proj4 load only with the site panel.
import { useEffect, useMemo, useState } from 'react'
import { ApiError, type Site } from '../api/client'
import type { DataSource } from '../api/source'
import ApiProblemView from '../ApiProblemView'
import TerrainMap, { DEFAULT_SLOPE_OPACITY, type PointerInfo } from './TerrainMap'
import {
  type LoadedView,
  loadView,
  loadViews,
  release,
  type SiteViews,
  slopeClassAt,
  slopePalette,
  type TerrainView,
} from './viewData'
import Section from '../Section'

type Load<T> = { kind: 'loading' } | { kind: 'ok'; data: T } | { kind: 'error'; error: unknown }

const message = (e: unknown) => (e instanceof Error ? e.message : String(e))

/** "2 × 2 km, 5 m pixels", from the view itself. */
function viewLabel(v: TerrainView): string {
  const [l, b, r, t] = v.bounds_ps_m
  return `${(r - l) / 1000} × ${(t - b) / 1000} km, ${v.pixel_m} m pixels`
}

/** "89.4527° S, 137.1487° W" for the pointer position (converted here, so rounded). */
function pointerLatLon(lat: number, lon: number): string {
  return `${Math.abs(lat).toFixed(4)}° ${lat < 0 ? 'S' : 'N'}, ${Math.abs(lon).toFixed(4)}° ${lon < 0 ? 'W' : 'E'}`
}

export default function TerrainSection({ site, source }: { site: Site; source: DataSource }) {
  const [views, setViews] = useState<Load<SiteViews>>({ kind: 'loading' })
  const [viewName, setViewName] = useState<string | null>(null)
  // The loaded view, tagged with the view it's for (a different one means: still loading).
  const [loaded, setLoaded] = useState<{ view: TerrainView; load: Load<LoadedView> } | null>(null)
  const [showSlope, setShowSlope] = useState(true)
  const [slopeOpacity, setSlopeOpacity] = useState(DEFAULT_SLOPE_OPACITY)

  useEffect(() => {
    let cancelled = false
    loadViews(source, site.id)
      .then((data) => {
        if (cancelled) return
        setViews({ kind: 'ok', data })
        setViewName(data.views[0]?.view ?? null) // the smallest extent first
      })
      .catch((error: unknown) => !cancelled && setViews({ kind: 'error', error }))
    return () => {
      cancelled = true
    }
  }, [source, site.id])

  const list = views.kind === 'ok' ? views.data.views : []
  const from = views.kind === 'ok' ? views.data.from : 'live'
  const view = list.find((v) => v.view === viewName)
  useEffect(() => {
    if (!view) return
    let cancelled = false
    let done: LoadedView | null = null
    loadView(from, view)
      .then((l) => {
        if (cancelled) return release(l)
        done = l
        setLoaded({ view, load: { kind: 'ok', data: l } })
      })
      .catch((error: unknown) => !cancelled && setLoaded({ view, load: { kind: 'error', error } }))
    return () => {
      cancelled = true
      if (done) release(done)
    }
  }, [from, view])

  const current = loaded && loaded.view === view ? loaded.load : null
  const data = current?.kind === 'ok' ? current.data : null
  // The site's point (from the site list) in the images' grid; the view must be centred on it.
  const placed = useMemo(() => {
    if (!data) return null
    const point = data.grid.fromLatLon(site.location.lat, site.location.lon)
    const offset = Math.hypot(point[0] - data.centerPs[0], point[1] - data.centerPs[1])
    return { point, offset, ok: offset <= data.view.pixel_m }
  }, [data, site.location.lat, site.location.lon])

  let body
  if (source === 'fixtures') body = <p className="muted">Fixture mode has no terrain images.</p>
  else if (views.kind === 'loading') body = <p className="muted">Loading the terrain images…</p>
  else if (views.kind === 'error') {
    body =
      views.error instanceof ApiError ? (
        <ApiProblemView what="the terrain images" error={views.error} />
      ) : (
        <TerrainError message={message(views.error)} />
      )
  } else if (list.length === 0) body = <p className="muted">No terrain images for this site yet.</p>
  else if (!current || current.kind === 'loading') body = <p className="muted">Loading the terrain images…</p>
  else if (current.kind === 'error') body = <TerrainError message={message(current.error)} />
  else if (placed && !placed.ok && data) {
    body = (
      <TerrainError
        message={`these images are centred ${placed.offset.toFixed(1)} m from this site's location (more than one ${data.view.pixel_m} m pixel), so they aren't shown`}
      />
    )
  } else if (data && placed) {
    body = (
      <TerrainBody
        key={data.view.view}
        loaded={data}
        sitePoint={placed.point}
        showSlope={showSlope}
        slopeOpacity={slopeOpacity}
      />
    )
  }

  return (
    <Section id="terrain" title="Terrain map" className="terrain-view">
      {list.length > 0 && (
        <div className="terrain-controls">
          <fieldset>
            <legend className="visually-hidden">Map extent</legend>
            {list.map((v) => (
              <label key={v.view}>
                <input
                  type="radio"
                  name={`terrain-view-${site.id}`}
                  checked={viewName === v.view}
                  onChange={() => setViewName(v.view)}
                />{' '}
                {viewLabel(v)}
              </label>
            ))}
          </fieldset>
          {data?.slopeUrl && (
            <>
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
            </>
          )}
        </div>
      )}
      {body}
    </Section>
  )
}

function TerrainError({ message }: { message: string }) {
  return (
    <div className="banner error" role="alert">
      <strong>Can't draw the terrain map:</strong> {message}
      {/[.?!)]$/.test(message) ? '' : '.'}
    </div>
  )
}

function TerrainBody({
  loaded,
  sitePoint,
  showSlope,
  slopeOpacity,
}: {
  loaded: LoadedView
  sitePoint: [number, number]
  showSlope: boolean
  slopeOpacity: number
}) {
  const [pointer, setPointer] = useState<PointerInfo>(null)
  const { view, grid, centerPs } = loaded
  const slope = loaded.slopeUrl ? view.slope : null
  const palette = slope ? slopePalette(slope) : []
  // True north at the map centre, degrees clockwise from up (grid north): straight away from the
  // south pole, which is the grid origin.
  const northDeg = (Math.atan2(centerPs[0], centerPs[1]) * 180) / Math.PI
  const [left, bottom, right, top] = view.bounds_ps_m
  const inside = pointer
    ? pointer.x >= left && pointer.x <= right && pointer.y >= bottom && pointer.y <= top
    : false
  const cls = pointer && inside ? slopeClassAt(loaded, pointer.x, pointer.y) : null
  const [lat, lon] = pointer && inside ? grid.toLatLon(pointer.x, pointer.y) : [0, 0]
  const src = view.source

  return (
    <>
      <div className="terrain-map-wrap">
        <TerrainMap
          view={loaded}
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
        {pointer && inside ? (
          <>
            Pointer: {pointerLatLon(lat, lon)}
            {slope && cls !== null && (
              <> · slope {cls === slope.nodata ? 'no data' : slope.class_labels[cls]}</>
            )}
          </>
        ) : (
          'Point at the map to read the slope class there. Drag to move; Ctrl + wheel or + / − to zoom.'
        )}
      </p>
      <ul className="legend">
        {slope ? (
          <>
            <li>Slope{showSlope ? '' : ' (hidden)'}:</li>
            {slope.class_labels.map((label, i) => (
              <li key={label}>
                <span
                  className="legend-swatch terrain-swatch"
                  style={{ background: palette[i], opacity: slopeOpacity }}
                  aria-hidden="true"
                />{' '}
                {label}
              </li>
            ))}
          </>
        ) : (
          <li>This view has no slope image.</li>
        )}
        <li>
          <span className="terrain-site-swatch" aria-hidden="true" /> Site point
        </li>
      </ul>
      <div className="definition">
        <p>
          Up is grid north: {view.map_up}. The N arrow shows true north at the map's centre; the south pole
          lies the opposite way. Grid: south polar stereographic on the {grid.radiusM / 1000} km lunar sphere.
        </p>
        <p>
          {view.hillshade && (
            <>
              Shading: {view.hillshade.note ?? 'cartographic shading'} (light from{' '}
              {view.hillshade.light_azimuth_map_deg}° on the map, {view.hillshade.light_altitude_deg}°
              high).{' '}
            </>
          )}
          {slope && <>Slope: {slope.definition}.</>}
        </p>
        <p>
          Source: <a href={src.url}>{src.dataset_id}</a>
          {src.source_pixel_m != null && <>, {src.source_pixel_m} m pixels</>}
          {src.block_mean != null && src.block_mean > 1 && (
            <>
              {' '}
              (each image pixel the mean of {src.block_mean} × {src.block_mean})
            </>
          )}
          ; image {view.width} × {view.height} px at {view.pixel_m} m.
        </p>
      </div>
    </>
  )
}
