<!-- SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage". -->
# Methodology

_Owned by stream A (engine and science). Other streams link to this page but do not edit it._

Status: **C3 complete** (G1 signed off 2026-11-15; G2 review 2026-11-16). Served: 8 PGDA sites and 6 Apollo
sites, each at 1, 2, 5 and 10 m over three windows (section 6.5). Every convention here is also stated in the
code that implements it and covered by a test.

## 1. Data

All files are fetched by `scripts/fetch_data.py` into `LSS_DATA_DIR`. The file catalog (source URL, local
path, registry id) is `lss/datafiles.py`. `LSS_DATA_DIR/MANIFEST.json` records each file's size, SHA-256 and
retrieval time. Nothing here is committed to the repository.

### 1.1 Ephemeris and frames (NAIF SPICE, DE421 era)

| File | Role |
|---|---|
| `de421.bsp` | Planetary ephemeris DE421 (Sun, Earth, Moon positions). NAIF now serves it from `spk/planets/a_old_versions/`. |
| `moon_pa_de421_1900-2050.bpc` | Lunar orientation (principal-axis frame `MOON_PA_DE421`) from DE421 |
| `moon_080317.tf` | Frame kernel: defines `MOON_ME_DE421` as a fixed rotation from `MOON_PA_DE421` |
| `moon_assoc_me.tf` | Associates the generic name `MOON_ME` with `MOON_ME_DE421` |
| `naif0012.tls` | Leap seconds (the latest NAIF leapseconds kernel; last leap second 2016-12-31) |
| `pck00010.tpc` | Body radii: Sun 696,000 km; Earth 6378.1366 / 6356.7519 km (for apparent disc sizes) |

**Why DE421:** the PGDA elevation maps are in the MOON_ME frame of DE421, so using the same lunar orientation
avoids any frame alignment between terrain and ephemeris (plan section 4.2).

**Coverage (measured from the files, 2026-11-14):**
- Lunar orientation: 1900-01-01 00:00:00 TDB to **2051-01-01 00:00:00 TDB**, which is
  **2050-12-31 23:58:50.816 UTC** if no leap seconds are added after 2016. This is the limiting kernel.
- DE421 ephemeris: 1899-07-29 to 2053-10-09 TDB.
- **Latest supported instant: 2050-12-31 23:58:50 UTC.** A leap second announced in future would move
  the UTC equivalent by one second; the engine checks against the kernel's TDB limit, not a hard-coded date.

### 1.2 Terrain (NASA GSFC PGDA, LOLA)

All PGDA grids used here are south polar stereographic, true scale at the pole, on a 1737.4 km sphere,
in MOON_ME / DE421, float32 heights in metres above the sphere, NaN = no data (checked from the GeoTIFF headers).

| Layer | Product | Resolution | Extent | Used for |
|---|---|---|---|---|
| Near field | PGDA 78, `Site01_final_adj_5mpp_surf.tif` | 5 m | 16 × 16 km tile (PS x −19…−3 km, y −20…−4 km) | Site01 horizon, near range |
| Far field | PGDA 90, `LDEM_80S_80MPP_ADJ.TIF` | 80 m | ±304 km from the pole (80–90°S) | Middle range |
| Far field | PGDA 90, `LDEM_60S_240MPP_ADJ.TIF` | 240 m | ±931 km (60–90°S) | Long range, beyond the 80 m grid |
| Validation only | PGDA 90, `LDEM_60S_60MPP_ADJ.TIF`, ±150 km window around Site01 | 60 m | ±150 km | Internal reproduction of PGDA product 69 (section 4.2) |

**Why this stack:** it mirrors the nested-grid approach used for the PGDA site illumination results (Barker et
al. 2021: 5 m within 5 km, 80 m for 5–100 km, 240 m beyond; following Mazarico et al. 2018). Barker's far-field
grids were the original LOLA polar maps; ours are the newer, orbit-adjusted product 90 maps (Barker et al. 2023)
on the same frame. The near/far transition distances and the maximum ray range were checked by a convergence
test (section 3.2), not assumed.

The served Site01 point (section 1.3) lies at PS (−11.2875, −12.1675) km, at least 7.7 km from every edge of its
5 m tile.

### 1.3 The served site: Site01 at Barker et al. (2021) RoI 4

**Served point:** the centroid of region of interest (RoI) 4 at Site01 (Connecting ridge), from Barker et al.
(2021, Table 2):
- PS (−11.2875, −12.1675) km, which is 89.452675° S, 222.851347° E (−137.148653°) on the 1737.4 km sphere;
- named "Site01 Connecting ridge (Barker 2021 RoI 4)", so it can't be mistaken for the Mazarico point.

The served point result is computed at this centroid. The RoI-area average used for the Barker check
(section 4.1) is a separate, internal result and is never served.

**Why not the Mazarico et al. (2011) coordinate (89.45° S, 222.69° E).** That coordinate was picked on a 240 m
map. On the 5 m map it lies on an **8.6° slope**:
- for a 1 m observer, terrain 15–40 m uphill puts the horizon at 4–4.9° over azimuths 120–200°;
- the Sun's centre never rises above 2.11° there (2.38° for the top of its disc, 2024–2043), so that point
  would be far darker than Barker's results for the ridge;
- this was checked against the ray caster with an independent sampling of the map.

The Mazarico point stays on record and may be added later as a second site.

**Why RoI 4 and not another RoI.** It is the RoI nearest the cited Site01 coordinate (94 m; the next nearest,
RoI 3, is 248 m away), so the served site stays the place the literature calls Site01. It is also the largest
RoI and is nearly flat.

| RoI | Centroid PS x, y (km) | Distance from the Mazarico point | Slope at centroid (5 m map) | Area (m²) |
|---|---|---|---|---|
| 1 | −11.5825, −12.4625 | 342 m | 3.0° | 8,625 |
| 2 | −11.4875, −12.5575 | 348 m | 1.3° | 7,550 |
| 3 | −11.3525, −12.5025 | 248 m | 1.8° | 3,825 |
| **4** | **−11.2875, −12.1675** | **94 m** | **1.4°** | **13,300** |
| 5 | −11.1025, −11.9425 | 377 m | 2.8° | 10,075 |
| 6 | −10.8025, −11.7375 | 726 m | 1.1° | 10,000 |
| 7 | −10.2275, −11.5525 | 1291 m | 1.2° | 7,075 |

Slopes are from central differences over ±10 m on the bilinear 5 m surface.

### 1.4 Curated sites (C3)

The site list is registry data: `lss/registry/sites.yaml`, loaded by `lss/registry/sites.py` as contract
`Site` objects, with coordinates, cited descriptions and sources. `/api/sites` is generated from it.

**Served point rule** (Kaitlin, 2026-11-15):
- **Where the PGDA product 78 tile has Barker et al. (2021) regions of interest:** the centroid of the largest
  RoI. Barker defines an RoI as the connected 5 m pixels ("corners or sides touching") with average
  illumination above 70% at 1 m over 2024–2025 and a total area above 2500 m² (Barker et al. 2021, section 5).
- **Otherwise:** the Mazarico et al. (2011) coordinate, checked for slope on the 5 m map. Steep points are
  flagged to Kaitlin.

**Reading the RoIs** (`lss/registry/rois.py`).
- An outline runs through pixel centres, so an RoI is the pixels inside it or on it.
- Its centroid is the centre of the 5 m pixel that contains the mean of those pixel centres. Barker's
  tabulated centroids are pixel centres, and this rule reproduces all seven at Site01 (Table 2) exactly.
- Barker et al. (2021, Appendix A. Supplementary data) maps illumination, LCIP and LCSP at Site04, 07 and 11
  with the RoI outlines, and box-plots each RoI (Figs. S5–S19). Values read from those figures are used as an
  approximate check in section 6.7.
- Areas match Table 2 for 6 of the 7 Site01 RoIs. RoI 2 comes out two pixels larger (7,600 against 7,550 m²).

**Sites at the centroid of the largest RoI** (all with Barker's 100 DEM clones):

| Site | Largest RoI | Area | PS (km) | Lat, lon | Slope at the point |
|---|---|---|---|---|---|
| Site01 Connecting ridge | 4 (of 7) | 13,300 m² | −11.2875, −12.1675 | −89.452675, −137.148653 | 1.2° |
| Site04 Shackleton rim | 1 (of 4) | 6,975 m² | −2.8125, −6.6475 | −89.761966, −157.067197 | **5.1°** |
| Site07 Peak near Shackleton | 2 (of 2) | 16,550 m² | 30.0625, −20.1075 | −88.807326, 123.776844 | 1.6° |
| Site11 de Gerlache rim | 1 (of 4) | 13,325 m² | −37.5425, 14.8825 | −88.668256, −68.375764 | 1.1° |

Slopes here use the definition of section 5.6 (central differences at 5 m). Site01's 1.4° in section 1.3 used a
±10 m baseline.

**Sites at the Mazarico et al. (2011) coordinate.** These tiles have no published RoIs. Site06's RoI archive
link on the PGDA page returns a "Not Found" page.
- **Source:** Mazarico et al. (2011, Table 3), the 50 most illuminated spots near each pole on a 240 m map.
  Illumination there is the mean visible fraction of the solar disc at surface level, 1970–2044 at 6 h steps.
  The coordinates are given to 0.01°, about 300 m in latitude at these sites, so each point is that precise.
- The product 78 site numbers are the Table 3 ranks.

| Site | Table 3 rank | Average illumination (Table 3, surface) | PS (km) | Lat, lon | Slope at the point |
|---|---|---|---|---|---|
| Site06 Nobile rim 1 | 6 | 85.95% | 85.958, 113.780 | −85.30, 37.07 | **8.0°** |
| Site20 Leibnitz beta plateau | 20 | 82.22% | 72.919, 117.928 | −85.43, 31.73 | **7.2°** (lies off the well-lit ground; section 6.7) |
| Site23 Malapert massif | 23 | 81.76% | −4.906, 122.155 | −85.97, −2.30 | **6.6°** |
| Site42 de Gerlache-Kocher massif | 42 | 79.59% | −113.360, −56.149 | −85.83, −116.35 | **6.8°** |

**Slope check: all four are steeper than the RoI points.** Their slopes are 6.6–8.0° at the point, and the
mean slope within 100 m is 5.0–8.0°. The RoI centroids are at 1.1–5.1°, and Site01's own Mazarico point is on
an 8.6° slope. The coordinates were picked on a 240 m map, where this relief is invisible. Flagged to Kaitlin
(2026-11-15). The points are kept as published, because the rule takes Mazarico's coordinate.

**Left out of C3** (Kaitlin, 2026-11-15): the other 19 product 78 tiles (Haworth, Shoemaker, DM, SL, NP and LM
series). They are not Mazarico sites, so neither rule gives them a point.

#### 1.4.1 Site20: the published coordinate against nearby grid nodes

At 10 m, three of the four Mazarico points reproduce Table 3 within the section 6.7 tolerances (2.86 pp
average illumination, 2.39 pp visibility, Mazarico-matched setting): Site06, Site23 and Site42 differ by
0.0–1.4 pp. Site20's published coordinate differs by 37.7 and 34.4 pp (section 6.7). So Site20 was checked
for a better point, by a rule fixed before any value was computed (Kaitlin, 2026-11-16;
`scripts/mazarico_node.py`):
- **Candidates.** Table 3 rounds to 0.01°, so Mazarico's grid node lies in the cell of values that round to
  31.73 E, 85.43 S: about 303 m north-south but 24 m east-west. Candidates are the points of a 240 m polar
  stereographic lattice in that cell, under both registrations of a 240 m grid (our 240 m map's pixel centres
  and its pixel corners); for a registration with no point in the cell, its point nearest the cell.
- **Values.** Each candidate is run with the section 6.7 Mazarico-matched setting (240 m map to 400 km, first
  ray sample 240 m, 0.5° azimuth step, 1970-01-01 plus 4 × 18.6 years at 6 h, observer at 0 m and 10 m).
- **Selection and acceptance.** The candidate closest to Table 3 at 10 m (mean |difference| over average
  illumination and visibility) replaces the published coordinate only if it is within both 10 m tolerances.
  Otherwise the published coordinate is kept.

Neither registration has a lattice point inside the 24 m-wide cell, so there were two candidates:

| Point | PS (km) | From the published point | 10 m: avg ill / visibility | 0 m: avg ill / visibility |
|---|---|---|---|---|
| Published (31.73 E, 85.43 S) | 72.919, 117.928 | — | 45.58 / 52.23% | 24.62 / 29.16% |
| Pixel-centre lattice | 72.840, 117.960 | 85 m | 47.06 / 53.55% | 27.09 / 32.11% |
| Pixel-corner lattice | 72.960, 118.080 | 158 m | 57.85 / 62.82% | 35.02 / 39.56% |
| Table 3 | | | 83.32 / 86.66% | 82.22 / 85.76% |

**Result: the published coordinate is kept.** The closest candidate (pixel corners) is 25.5 and 23.8 pp below
Table 3 at 10 m. Slope on the 5 m map: 7.2° at the published point, 6.3° at the pixel-corner point. The site's
description says that the point does not reproduce the illumination Mazarico et al. report there.
Section 6.7 compares the published coordinate.

#### 1.4.2 Apollo landing sites

Six entries (`apollo-11`, `-12`, `-14`, `-15`, `-16`, `-17`; Kaitlin, 2026-11-16). Each point is the Lunar
Module descent stage as located in LROC NAC images by Wagner et al. (2017, Icarus 283, 92–103,
doi:10.1016/j.icarus.2016.05.011), read from the LROC PDS archive table (LRO-L-LROC-5-RDR-V1.0,
`EXTRAS/SHAPEFILE/ANTHROPOGENIC_OBJECTS`). The same values are on NASA NSSDCA's Apollo Landing Site
Coordinates page, which gives the frame as the mean Earth/polar axis system of DE421 (the engine's frame).
The table's stated uncertainties are 0.3–3.5 m. Place names and UT landing dates: NSSDCA mission pages.
Terrain there is the global layer (section 3.5).

#### 1.4.3 Artemis III candidate regions

Nine entries (`artemis3-*`, category `artemis_iii`; Kaitlin, 2026-11-16): the regions NASA named on 28 October
2024 (release 24-136), in the release's order. In February 2026 NASA made Artemis III a crewed test flight in
Earth orbit in 2027 and planned the first landing for Artemis IV in 2028 (release 26-022); NASA's Artemis IV
page (updated 16 March 2026) still shows the same nine regions. No newer list was found (checked 2026-11-16).

NASA gives no centre or outline for the regions. The point for each is the centre of the region's 1 km
navigation grid in McClernan (2024), a U.S. Geological Survey data release made for these nine regions: the
extent in each zip's `<region>_PolarLGRS_ACC_1km_S_Grid.shp` header, which equals the extent of the grid's cells
(full rectangles of 1 km cells). The grid's projection file gives a south polar stereographic projection on the
1737.4 km sphere with scale factor 0.994 and false easting and northing of 500 km, so the engine's polar
stereographic metres (scale factor 1, origin at the pole) are (grid metres − 500 km) / 0.994. Each region's
metadata also publishes latitude and longitude bounds to 4 decimals; every one of the 36 values equals a box
corner's latitude or longitude, as converted here, to 0.00005°, which checks the conversion. The release's
metadata gives the datum as "Moon (2015) - Sphere" (semi-axis 1,737,400 m), and each grid's projection file names
the same sphere. That fixes the radius, not the frame: the release does not state the body-fixed frame. The mean
Earth frame is assumed and has not been checked.

The boxes are 17 to 31 km on a side, except Mons Mouton Plateau (78 by 58 km), whose centre represents its region
only loosely. A box centre is a geometric point, not a landing site: the slope at the centre on the finest map
there (section 5.6; 5 m or 80 m) ranges from 1.5° to 16.4° (Nobile Rim 1, on the 5 m map). Three centres lie on 5 m PGDA site maps (Malapert
Massif, Mons Mouton and Nobile Rim 1, 0.3 to 4.4 km from the curated sites there) and get the high-fidelity stack;
the other six use the 80 m and 240 m polar maps (medium). Short names end in "region" so that they stay distinct
from the curated sites. `tests/engine/test_sites_artemis.py` pins each box and bound as published and recomputes
the centres and the distances stated in the descriptions.

## 2. Frames, time scales and topocentric geometry

Implemented in `lss/ephem/core.py`; tested in `tests/engine/test_ephem.py`.

- **Frame.** All geometry is in `MOON_ME_DE421`, the Mean Earth / polar axis frame of DE421 (named explicitly in
  code; `MOON_ME` is an alias for it). It is a fixed rotation of the DE421 principal-axis frame.
- **Coordinates.** Planetocentric latitude and east-positive longitude on the 1737.4 km reference sphere, the
  same sphere the PGDA maps use. On a sphere planetocentric and "geodetic" latitude are the same.
- **Observer.** On the sphere's normal (the radial direction) at radius 1737.4 km + h, where h = DEM surface
  height at the site + the unit height. At the served Site01 point (section 1.3) the 5 m map gives a surface
  height of 1956.39 m (bilinear between pixel centres). The 80 m map gives 1.32 m less and the 240 m map
  6.58 m less, because their pixels average over the ridge.
- **Time.** Inputs are UTC. SPICE converts them to TDB (barycentric dynamical time) using the `naif0012`
  leapseconds kernel. No leap seconds are assumed after 2016-12-31, which only matters for the UTC labels of
  future instants (by whole seconds). The supported span is the kernels' coverage (section 1.1); requests
  outside it are refused, not extrapolated.
- **Local frame.** East-north-up (ENU) at the site, from the sphere normal. Elevation is measured from the
  local horizontal plane of that normal (this is the *astronomical* elevation; the *terrain* horizon is
  section 3). Azimuth is measured clockwise from north, 0–360°. At an exact pole every horizontal direction
  points away from the pole, so the requested longitude defines which one is called north: the limit of north
  when the pole is approached along that meridian (tested).
- **Apparent directions.** Sun and Earth directions are corrected for light time and stellar aberration
  (SPICE `LT+S`), computed by `spkcpo` for an observer fixed on the rotating Moon. The aberration therefore
  includes the observer's velocity from lunar rotation. There is no refraction (no atmosphere). Light time
  matters in the rotating frame: in the ~8.3 min the sunlight travels, the Moon turns by about 0.08°.
- **Libration.** No separate libration model: libration is already in every Earth position, via the DE421
  ephemeris (the Earth–Moon vector) and the lunar orientation (PA DE421), because the Earth's direction is
  computed in the Moon's body-fixed frame. At the served site libration is what moves the Earth in its sky:
  elevation from −7.4° to +6.0° over the served window (section 5.4).
- **Apparent disc sizes.** Angular radius = asin(R / distance). Sun: R = 696,000 km (`pck00010`), giving about
  0.26–0.27°. Earth: R = 6371.0 km, the volumetric mean radius of `pck00010`'s Earth ellipsoid
  (6378.1366 / 6356.7519 km), giving 0.90–1.02° (a disc of about 1.8–2.05°, the "~2° Earth disc" of the plan).
  Using a sphere for Earth instead of its ellipsoid changes the disc edge by under 0.003°.
- **Independent check.** For every test site and epoch, azimuth, elevation and range agree with SPICE's own
  constant-position az/el routine (`azlcpo`, same frame and corrections) to better than 10⁻⁶°. The comparison
  against JPL Horizons, an independent ephemeris service, is in section 6.1 (agreement better than 0.05″).

## 3. Horizon

Implemented in `lss/horizon/core.py` (numba ray caster) and `lss/horizon/cache.py`; tested in
`tests/engine/test_horizon.py`; settings chosen by `scripts/horizon_convergence.py`.

### 3.1 Geometry

- **Observer.** On the sphere normal at the site, at radius r_o = 1737.4 km + surface height + unit height.
  The surface height is taken from the finest terrain layer (the near field).
- **Rays.** The ray at azimuth A is the great circle that leaves the site in direction A. At angular distance θ
  its direction is p = cos θ · up + sin θ · (cos A · north + sin A · east), in the site's ENU frame (section 2).
  The ray distance is the arc length d = R θ on the reference sphere. Rays are not traced as straight lines
  on the polar stereographic map, because that map is not true to scale away from the pole. 400 km from
  Site01 its local scale is 1.4% too large, and map distances out to there are about 0.5% too long. That
  would shift the curvature term by about 0.07°.
- **Elevation of a terrain point.** A point at height h (radius r = R + h) and angular distance θ is seen at
  tan(el) = (r cos θ − r_o) / (r sin θ), measured from the observer's local horizontal plane. This is exact on the sphere. The
  plan's form, atan((Δh − d²/2R)/d), is its small-angle limit. The two differ by about 0.005° at short range
  (the approximation uses R where the geometry has R + h) and about 0.03° for terrain 400 km away (tested).
  The exact form costs nothing extra.
- **Horizon.** For each azimuth, the horizon is the largest elevation over the ray samples. Between computed
  azimuths it is interpolated linearly.
- **Heights along a ray.** Bilinear between pixel centres (section 1.2). Each ray distance has a designated
  layer (5 m site map, then the 80 m map, then the 240 m map; section 1.2; beyond the distance the 240 m map
  holds in every direction, the global map, section 3.5). If that layer has no data at a
  sample, the next coarser layer is used. Samples that no layer covers are counted, never silently dropped.
  The count is stored with each cached horizon. A location where a whole azimuth has no data is rejected.
  `scripts/precompute_c1.py` refuses to write a served result whose horizon has any uncovered sample. At Site01
  there are none. `scripts/precompute_c3.py` likewise refuses one, so no served result has an uncovered
  sample.

### 3.2 Numerical settings and convergence

| Setting | Default (`HorizonParams`, `lss/registry/terrain.py`) | Reference used to judge it |
|---|---|---|
| Azimuth step | 0.1° | 0.05° |
| Ray sample spacing at distance d | min(0.5 × pixel size, 0.002 × d) | min(0.25 × pixel size, 0.0005 × d) |
| First sample | 1 m | 0.5 m |
| 5 m site map used to | 5 km | 7.5 km (the most the tile allows at Site01) |
| 80 m map used to | 100 km | 290 km (the most the map allows) |
| Maximum ray range (240 m map beyond) | 400 km | 800 km |

**Sample spacing near the observer.** The spacing is min(fraction × pixel size, fraction × distance), so it is
geometric close in and uniform further out. Close to the observer, elevation changes with distance like 1/d,
so a spacing tied only to the pixel size misses near-field peaks. The first version of the study found this:
with 2.5 m spacing, peaks about 18 m from the Site01 point were missed by up to **0.19°**, at most azimuths,
because terrain within 15–40 m sets the 1 m horizon there. A synthetic test now pins this down: a single
raised 5 m pixel 18.3 m away must be found within the analytic bound, and pixel-only spacing must visibly fail it.

**Results** (`scripts/horizon_convergence.py`; each variant compared with the reference at every reference
azimuth):

| Case | Default vs reference: max | 99th percentile | RMS | Time per horizon (two runs) |
|---|---|---|---|---|
| Mazarico Site01 point, 1 m (horizon from terrain 15–40 m away) | 0.0088° | 0.0020° | 0.0006° | 4.2–4.5 s |
| Served point (RoI 4 centroid), 1 m | 0.0066° | 0.0035° | 0.0010° | 3.6–4.1 s |
| Mazarico Site01 point, 10 m | 0.0091° | 0.0038° | 0.0011° | 3.6–3.9 s |

Which setting causes how much (max over the three cases, one setting at its default, all others at the
reference):

| Setting at its default | Max change |
|---|---|
| Azimuth step 0.1° | 0.0083° |
| Spacing 0.002 × d | 0.0064° |
| 80 m map handing over to 240 m at 100 km | 0.0056° |
| Spacing 0.5 × pixel | 0.0012° |
| First sample at 1 m | 0.0011° |
| 5 m map handing over at 5 km | 0.0007° |
| Maximum range 400 km (vs 800 km) | 0.0000° |

Coarser settings cost accuracy. A 0.25° azimuth step gives up to 0.025°, and spacing at 0.01 × d gives up
to 0.034°. Barker et al. (2021) used 0.5°.

**Accepted:** horizon errors of at most about 0.01°, about 2% of the Sun's apparent diameter (0.53°). In the
served scenario, an error of that size moves the illumination fraction by about 0.25 percentage points and the
longest shadow by about 0.5 h, and leaves the shadow count unchanged (section 6.6). The terrain data limit the
served numbers far more than these numerical settings do (section 6.6).

**Limits of this study:**
- It covers Site01 only (two points, two heights).
- Distant terrain does not set the horizon here (400 km and 800 km agree exactly; 200 km also did at these
  points). 400 km is kept because other sites can see farther terrain, and the extra range is cheap.
- **Other sites** (G2 review, engine runs at Site06, 07, 20, 23 and 42, 1 m and 10 m): a 700 km range
  changes no azimuth (the farthest horizon-setting terrain is 226 km away) and no ray sample is uncovered. The
  defaults against the reference sampling at 1 m: at most 0.0073–0.0079° at four sites and 0.0141° at Site06
  (99th percentile 0.0025°), just above the accepted 0.01°.

**A 10 m near field** (for locations beyond the 5 m maps; Kaitlin, 2026-11-15: measure first). The served
Site01 point was recomputed with the PGDA product 90 10 m map (`LDEM_83S_10MPP_ADJ`, to 83°S) in place of the
5 m tile, with the same hand-over at 5 km (`scripts/validation_c3.py`, stage `nearfield10m`).
- **Horizon:** median difference 0.008°, 95th percentile 0.37°, maximum 0.60°. The large differences are at
  azimuths whose horizon is set by terrain a few tens of metres away.
- **Metrics:** illumination 68.8% against 69.8%, the same 4 shadow periods, longest shadow 139.7 h against
  132.9 h, Earth metrics unchanged. All within the terrain-error band of section 6.6.
- **Cost:** about 3.5 s per horizon, the same as with the 5 m tile.
- **Data:** the map is 5.1 GB (43,280 × 43,280 float32, 7.5 GB in memory), and its download took 31 minutes
  here. A ±20 km clip is 36 MB.

**Timing:** wall-clock, measured on the development PC (24 logical CPUs, numba parallel over azimuths), with the DEMs
already in memory; reference settings take 34–38 s. The first call in a process also reads the DEMs, about 0.5 GB for the three layers.

### 3.3 Cache

Horizons depend only on location and unit height, not on dates (plan section 4.6), so each is computed once
and stored in `LSS_DATA_DIR/cache/horizon/`. The cache key is a SHA-256 hash of everything that changes the
result:

- the algorithm version;
- latitude, longitude and unit height;
- the numerical settings;
- the terrain stack: file ids, source URLs and ray-distance ranges.

The key does not need the DEM files, so a deployment can serve cached horizons without the DEMs. Each cache
file also records the DEMs' SHA-256 hashes from `MANIFEST.json`, for provenance.

### 3.4 Tests

- **Flat sphere:** the horizon equals the pure curvature dip, −acos(R / r_o), within 10⁻⁵° at every azimuth.
  This is checked for a 1 m and a 1000 m observer, and also with the range cut short of the tangent point.
- **Ring-shaped ridge** (Gaussian profile, at both poles): within 0.001° of the analytic maximum, which is
  computed independently on a 0.5 m grid of distances.
- **Azimuth convention:** separate ridges placed to the north and to the east show up at 0° and 90°, with
  sharp sector edges. The synthetic terrain is built from the standard spherical distance and bearing formulas,
  not from the ray caster's vector maths.
- **Layer fallback:** a hole in the fine layer is filled from the coarse one; samples beyond every layer are counted.
- **Site01, real data:** the numba kernel matches a separate NumPy calculation to 10⁻⁶° on five azimuths. That
  calculation uses the great-circle destination formula and the terrain module's height lookup.
- **Cache:** a second request is read from the file (verified), and a different unit height is a different key.

### 3.5 Global coarse layer (C7): horizons off the polar maps

**Data.** LOLA LDEM_128 (PDS data set LRO-L-LOLA-4-GDR-V1.0, product version 3.0, 2017-09-15; registry
`lola_ldem_128`; `lss/terrain/global_layer.py`). From its PDS3 label, checked field by field before each read:
simple cylindrical, 128 pixels per degree (236.901 m along a meridian), 23040 × 46080 16-bit counts × 0.5 m
above a 1737.4 km sphere, pixel registered, frame "MEAN EARTH/POLAR AXIS OF DE421". This is the PGDA maps' frame
and reference sphere, so no alignment is applied. The 0-based line r is centred at latitude (11519.5 − r)/128
and sample s at east longitude 180 + (s − 23039.5)/128. The image's size is checked against the label.

**Checks of frame and datum** (bilinear heights at points, 2026-11-16):
- Against Wagner et al. (2017)'s NAC-DTM radii of the six Apollo Lunar Module descent stages (independent of
  LOLA gridding): LDEM_128 minus Wagner is −8.6, −2.1, +0.1, +6.1, +2.0 and −2.5 m (Apollo 11, 12, 14, 15, 16,
  17).
- Against the PGDA 240 m polar map at 12 points from 61° S to 86° S: mean difference 0.9 m, mean |difference|
  2.8 m, maximum 7.0 m.

**Where it is used** (`lss/registry/terrain.py`, `GlobalLayerSpec`). Only where no polar layer covers the
location, as the single layer of the stack, from the observer to the 400 km maximum range. Every location the
polar maps cover keeps exactly the stack it had before (tested at all eight polar sites), so their results are
unchanged. The fidelity tier is "low": the resolver gives "low" when the near field is coarser than 80 m. A
location inside the polar maps whose rays leave them (north of about 73° S) keeps its polar near field, and the
global layer is its far field: see "Full ray range" below.

**Full ray range** (2026-11-23). The last polar layer of a stack must hold every point within
the 400 km ray range, at least one pixel inside its edges. Between about 73° S and 60° S the 240 m map does not,
in some directions or all. There the polar layers are used out to the largest distance the 240 m map holds in
every direction, and LDEM_128 from there to 400 km (`full_reach_m`, `resolve`). With the 240 m map used alone to
400 km, as before, 1.5% of the ray samples of a 1 m observer had no terrain at 70° S, 0° E, 7.1% at 65° S and
15.9% at 61° S. Now there are none. Where the old horizon had data it changes by at most 0.0011° (70° S),
0.0007° (65° S) and 0.021° (61° S). The fidelity tier stays "low". A stack without a global layer at such a point
is refused, with the distance at which rays leave the map as the reason.
- **The distance.** Polar stereographic projection maps the cap of points within a ray distance of the location
  to a circle. On the location's meridian the cap spans the colatitudes c − δ to c + δ, so the circle's centre and
  radius follow from ρ(t) = 2R tan(t/2). The map holds the cap if the circle lies inside its bounds. The largest
  such distance is found by bisection to 1 m and rounded down. At 70° S, 0° E it is 303.1 km.
- **Tests** (`tests/engine/test_terrain.py`, `test_global_layer.py`). The distance agrees with rings of
  great-circle destinations at five points: every ring point is on the map at that distance, and some leaves it
  50 m further. The stacks at 70°, 65° and 61° S. The refusal without a global layer. On the real maps: no
  missing sample at 70° S and 65° S, where the old stack had more than 1%.
- **Served results are unchanged.** All 23 curated sites resolve to exactly the stack they had before. Their
  polar maps hold the full ray range, and the Apollo sites use the global layer alone. The regression fixtures
  pass unchanged.

**Reading.** For each location the reader takes a window of the map covering every point within the maximum
ray range: a latitude band of ±400 km and the longitude span that band needs, asin(sin δ / cos φ) each way
for a range of δ radians at latitude φ, plus two pixels. Windows that contain a pole take whole rows, with the
last column next to the first. Windows may straddle the 0/360° meridian.

**How rays are stepped on the lat/lon grid** (`lss/horizon/core.py`, `_height_lonlat`). The geometry of
section 3.1 is unchanged: each ray is a great circle, and its samples are unit vectors p in MOON_ME. For a lat/lon
grid, each sample's latitude is asin(p_z) and its east longitude atan2(p_y, p_x). The height is bilinear in
(longitude, latitude) between the four surrounding pixel centres. Longitude is measured from the window's west
edge modulo 360°. The sample spacing follows section 3.2 with the pixel size set to 236.901 m (the north-south
pixel): at most 118 m far out, finer close to the observer. That is half a pixel north-south and at most one
pixel east-west up to 60° latitude, where an east-west pixel is 236.9 m × cos(latitude). **Step check:** at
all six Apollo sites, halving the spacing changes the horizon by at most 0.0033° (1 m and 10 m observers;
largest at Apollo 16). One horizon takes about 3 s.

**Tests** (`tests/engine/test_horizon_lonlat.py`, `tests/engine/test_global_layer.py`):
- synthetic lat/lon grids built from independent spherical formulas: a flat sphere gives the pure curvature dip
  (10⁻⁵°); a ring ridge matches its analytic maximum (10⁻³°) at the equator, 20° N and 45° S;
- the azimuth convention; a window across 0/360° gives the same horizon as the same terrain at 90° E (10⁻⁴°);
- a whole-row grid over the north pole (0.02°);
- a stack with a polar near field and a lat/lon far field matches a polar-only stack (10⁻³°);
- the reader: pixel mapping from the label, label and size checks, window contents, seam and pole windows;
- on the real map: heights at the six Lunar Modules within 10 m of Wagner et al.; a full horizon at Apollo 11.

**Limits.** The label states that coverage is incomplete (GMT "surface" was used "to compensate for incomplete
coverage") and that there "may be edge artifacts" at its 45° latitude band boundaries. Rays through the half-pixel cap at a pole find no data there
(counted as missing). North of 60° latitude the east-west pixel is smaller than the ray spacing.

## 4. Validation references

### 4.1 Barker et al. (2021): the served result

- Same terrain: the PGDA product 78 Site01 5 m map. Same unit height: **1 m** (Kaitlin's choice; Barker also
  reports 5 m). Same place: the served point is the centroid of Barker's RoI 4 (section 1.3).
- Barker's method: horizon from every pixel along 720 sight lines (0.5° apart); nested grids as above; 1 h
  steps from 2024-01-01 to 2026-01-01. The Sun is an extended disc with limb darkening at 550 nm. Its visible
  fraction is computed by cutting the disc horizontally at the horizon elevation found at the disc centre's azimuth.
- Barker's definitions: "average illumination" = the time-averaged visible fraction of the solar disc;
  LCIP/LCSP = longest continuous period with any / no part of the Sun visible.
- Our definitions match these (section 5). Two method differences remain, both measured (section 5.1):
  we cut the disc with the real horizon profile instead of a flat line, and the limb-darkening law
  (Barker names none) is Allen's 550 nm law. Each moves the time-mean fraction by 0.0002 or less at the
  served point.
- Published numbers usable for comparison: Table 2 gives, for seven regions of interest (RoIs) at Site01, the
  centroids (PS km) and the **1st/99th percentiles over 100 DEM clones**, not the nominal-DEM values. Barker
  notes that the nominal DEM tends to give *better* illumination than the clone median, so the 1st percentile
  is a lower bound for the nominal value, not a target. The RoI outlines are in `Site01_ROIs.tgz` (product 78).
- **The Table 2 check is a bound, not a match** (a two-sided check of Barker's 70% contour is added in section 6.2).
  - We compute the RoI 4 area average on the nominal DEM: the same quantities, averaged over every 5 m pixel in
    the RoI 4 outline, at 1 m, over Barker's period of 2024-01-01 to 2026-01-01.
  - We require it to be at least Barker's 1st percentile (Table 2, RoI 4, A rows), within a tolerance stated
    before the run (section 6.2).
  - For RoI 4 at z = 1 m, those values are: average illumination 69.61%, LCIP 136.49 days, and LCSP 13.27 days,
    where LCSP is a 99th percentile, so the expected direction is reversed (our value at most 13.27 days).
- **No nominal-DEM values are tabulated.**
  - Barker's Fig. 19 plots them (open circles). Barker notes they "tend to be better than the mean/median of the
    clones", because clone height errors are "more likely to raise than lower the horizon elevation".
  - Values read off a figure are too imprecise for a tolerance, so Fig. 19 is used only as a qualitative
    cross-check. Table 2 stays the formal bound.

### 4.2 PGDA product 69: internal-only reproduction (never served)

Product 69's average illumination and Earth-visibility maps (2016 release, 60 m/pix, from the LOLA map
`LDEM_85S_060M`) are compared like with like by rerunning the engine in **their** setup, not ours:

| Setting | Product 69 | Source / status |
|---|---|---|
| Quantity | Fraction of time steps with **any part** of the solar disc visible (Sun map) / any part of the Earth disc (Earth map) | PDS labels `AVGVISIB_85S_060M_201608{,_EARTH}.LBL` |
| Terrain | 60 m LOLA map | PDS labels. Ours: product 90 60 m window (a newer, orbit-adjusted 60 m map; a remaining difference) |
| Observer height | **Not stated** anywhere (page, labels, README). Assumed **surface level (0 m)**: Gläser et al. (2018) describe Mazarico's results as "surface level", and Mazarico et al. (2011) treat ~10 m as a sensitivity case | Assumed |
| Time step | Hourly | Product page: "averaged over hourly timesteps spanning 18.6 years" |
| Averaging span | 18.6 years (one lunar nodal cycle) | Product page (same sentence) |
| Averaging dates | **Not stated** anywhere | Assumed; the sensitivity to the start date is measured with two start dates, 2000-01-01 and 2024-01-01 (section 6.3) |

Note: Mazarico et al. (2011) themselves ran "several 18.6-years lunar precession cycles" at 6 h resolution on
240 m maps; the 2016 maps (60 m, hourly) are a later release by the same team.

The 0 m observer height is accepted by the engine functions for this check only. The API contract requires
`unit_height_m > 0` and the API rejects 0.

### 4.3 Terrain resolution matters (known effect, stated up front)

The same place gives very different long-term numbers on different terrain maps. For Connecting ridge at surface
level, Gläser et al. (2018, Table 1) report a maximum average illumination of **76.0%** with a 20 m map, against
**89.0%** for Mazarico et al. (2011) with a 240 m map. Coarser terrain smooths the near horizon and usually
raises illumination. Expect the 5 m served result and the 60 m product 69 reproduction to differ for this
reason, and compare each only with the reference that uses the same terrain resolution.

## 5. Metric definitions

These are the definitions behind the `PowerMetrics` and `CommsMetrics` fields; the field descriptions in
`lss/contract/models.py` say the same in short. The definitions are fixed here first (Kaitlin, 2026-11-15).
They are computed by `lss.series` (visibility, periods, events) and `lss.metrics` (step 4.6; section 5.5).
The numbers measured below come from that code, through `scripts/series_checks.py`, which writes them to
`LSS_DATA_DIR/cache/series_checks.json`. Preliminary numbers quoted while the definitions were being chosen
(scratch script, 10 min samples) are superseded; where they differed, this says so.

**Served C1 scenario** (`lss.contract.examples.SCENARIO`; the deployed endpoint serves it precomputed and
matches requests on `Scenario.key()`): the RoI 4 point (section 1.3), 1 m, 2028-05-15T00:00Z to
2028-06-14T00:00Z, step 1 h (the plan's hourly default). Kaitlin chose this window (2026-11-15) so it
contains shadow periods: at RoI 4 every 30-day window from mid-July to mid-January 2028 is fully sunlit,
including the first choice, 2028-11-15 to 12-15.

**One frame for horizon and tracks.** The horizon profile (`HorizonProfile`) and the Sun/Earth tracks
(`BodyTrack`) use the same topocentric frame and the same observer (section 2): azimuth 0–360°
clockwise from north, elevation measured from the plane through the observer normal to the 1737.4 km
reference sphere's radius at the site. A track can therefore be overlaid on the horizon directly: the
disc centre is above the terrain where its elevation exceeds the horizon elevation at the same azimuth
(`clearance_deg` is that difference).

### 5.1 Visible fraction of a disc at one instant

- **Disc.** Centre at the apparent azimuth and elevation, angular radius asin(R / distance) (section 2).
- **Against the real horizon profile.** A point of the disc is visible if it is above the terrain horizon at
  *its own* azimuth (section 3, interpolated linearly between the 0.1° horizon azimuths, so about 5 horizon
  values span the 0.53° solar disc). Barker et al. (2021) instead cut the disc with a flat line at the
  horizon elevation found at the disc centre's azimuth. Measured at the served point, 1 m, 2024–2025: the
  time-mean solar fraction is the same to 1e-7 either way (0.823396), and both give 50 shadow periods, 2 of
  them shorter than 1 h. The illumination fraction differs by 0.0002 (0.87194 real profile, 0.87173 flat cut).
  The preliminary finding that the flat cut adds short shadow periods (3 instead of 1) was an artefact of
  the 10 min sampling and is withdrawn. At this site the horizon is smooth on the scale of the disc: its
  largest change between neighbouring 0.1° azimuths is 0.039°.
- **Sun: a light-weighted fraction.** `f_sun` is the visible share of the solar disc's *light*, not of its
  area. Each point of the disc is weighted by the solar limb-darkening law at 550 nm:
  I(μ)/I(1) = 1 − u₂ − v₂ + u₂ μ + v₂ μ² = 0.30 + 0.93 μ − 0.23 μ², with u₂ = 0.93 and v₂ = −0.23.
  Here μ = √(1 − (ρ/r)²) for a point at angular distance ρ from the disc centre, r being the disc's angular
  radius. Source: Allen (1973), *Astrophysical Quantities*, 3rd edition, §81 "Solar limb darkening", p. 171,
  table of limb-darkening constants, row λ = 0.55 µm. The limb is 30% as bright as the centre, and the disc
  as a whole 80.5% (1 − u₂/3 − v₂/2; Allen's table gives 0.803).
  - **Barker et al. (2021) name no law.** They state only that the Sun is "treated as a 2-dimensional
    extended source with limb darkening at 550 nm", with no coefficients or citation. Allen's 550 nm law is
    our choice (Kaitlin, 2026-11-15). The same coefficients are commonly attributed to the 4th edition
    (Cox, 2000); only the 3rd edition was checked.
  - **Measured effect.** At the served point, 1 m, 2024–2025: time-mean fraction 0.82340 limb-darkened vs
    0.82322 geometric (as in the preliminary estimate). The law moves the result by 0.0002, so any gap from
    Barker in step 4.7 is not explained by the choice of law.
- **Earth: a geometric fraction.** `f_earth` is the visible share of the Earth disc's area, unweighted.
  Radius 6371.0 km (section 2).

### 5.2 Visibility, periods and clipping

- **Sunlit** = any part of the solar disc visible (`f_sun > 0`). **Shadow** = no part visible (`f_sun = 0`).
  This is product 69's convention for illumination and Barker's for LCIP/LCSP. Sunlit and shadow periods
  tile the window: every instant is in exactly one of them.
- **Partial loss of the disc is not a shadow.** It shows up only in `mean_visible_disk_fraction`.
- **No minimum duration.** Every shadow period found counts, however short. Periods are found on the 60 s
  internal grid (below), so a period shorter than 60 s can be missed if it starts and ends between two grid
  points; one that contains a grid point is found and refined. At the served point over 2024–2025,
  2 of 50 shadow periods are shorter than 1 h (the shortest 19.5 min) and none is shorter than 10 min, so
  horizon flickers do not inflate the count there. (The preliminary 10 min estimate was 1 of 49: it missed
  one short period.)
- **Clipped to the window.** A period that starts before `window_start` or runs past `window_end` is cut at
  the window edge and still counted, with its clipped length. `longest_shadow_clipped` says whether the
  longest shadow period was cut, in which case its full length is longer than reported;
  `longest_earth_gap_clipped` says the same for the longest Earth gap.
- **Earth visible** = any part of the Earth disc visible (`f_earth > 0`). An **Earth gap** = no part
  visible. Same rules: no minimum duration, clipped to the window.
- **Resolution.** Periods and events are found on a fine internal time grid (60 s) and refined by
  bisection to 0.5 s, independent of the scenario's `step`, which sets only the series returned (section 5.5).

### 5.3 Power (F3): `PowerMetrics`

Window W = [`window_start`, `window_end`], duration T.

| Field | Definition |
|---|---|
| `illumination_fraction` | Sunlit time in W divided by T. |
| `mean_visible_disk_fraction` | Time average of `f_sun` over W (limb-darkened, section 5.1). A light-weighted fraction, not a geometric area fraction. |
| `sunlit_duration_h` | Total sunlit time in W, h (= `illumination_fraction` × T). |
| `longest_sunlit_period_h` | Longest continuous sunlit period, clipped to W, h. |
| `longest_shadow_h` | Longest continuous shadow period, clipped to W, h. 0 if there is none. |
| `longest_shadow_clipped` | True if that period starts before W or runs past it; false if it lies inside W or there is none. |
| `shadow_count` | Number of shadow periods in W, including clipped ones; no minimum duration (periods shorter than the 60 s internal grid can be missed; section 5.2). |
| `sun_elevation_deg` | Apparent elevation of the disc centre above the local horizontal plane (section 2; not the terrain horizon): min, max and time mean over all of W, whether or not the Sun is visible. |
| `sun_azimuth_deg` | Apparent azimuth of the disc centre, clockwise from north, over all of W, whether or not the Sun is visible. `min` and `max` are the ends of the smallest arc containing the track, read clockwise from `min` to `max`; when the arc crosses north, `min` > `max` (e.g. 300 → 40). A track covering the full circle reports `min` 0, `max` 360. `mean` is always null: a linear mean of azimuths depends on where 0° is put, and a circular mean is undefined for a full circle, which is what the Sun does at Site01. The series carries the full track. |
| `time_to_sunset_h` | From `window_start` to the first sunset (the last visible part of the solar disc going below the terrain horizon), h. Null if there is no sunset in the window. |
| `sunset_in_window` | True if at least one sunset occurs in W, false if none does. Null only if not computed, so a null `time_to_sunset_h` is never ambiguous (Kaitlin, 2026-11-15). |

The azimuth arc is found from the continuous track (unwrapped azimuth). It is a full circle if the
unwrapped azimuth spans 360° or more; otherwise its ends are the unwrapped minimum and maximum, modulo 360°.
If other bodies get azimuth statistics, the same rule applies.

**Sun elevation in a band** (`lss.metrics.elevation_band`; C api's request RA7). The fraction of the window
with the Sun's elevation in [a, b] is taken from a time histogram stored in each served file
(`sun_elevation_histogram`, file format 3).
- **Quantity:** the apparent elevation of the Sun's disc centre above the local horizontal plane, as in
  `sun_elevation_deg`, with no refraction. **Terrain is ignored:** a band counts the time whether or not terrain
  hides the Sun. For a low band at a polar site this matters: at Site20, 1 m, the Sun's elevation is between 0°
  and 2° for 15.5% of the 30-day window, and the Sun is never visible then.
- **Histogram:** the seconds spent in each 0.1° bin over the window. They come from the 60 s internal grid, with
  the elevation taken as linear between grid points, so each interval's time is split across the bins it
  crosses. The seconds sum to the window length.
- **Band fraction:** the seconds in the bins inside [a, b], divided by the window length. It is exact for that
  piecewise-linear track when a and b are multiples of 0.1°; otherwise the end bins are prorated linearly,
  as if their time were spread evenly across the bin.
  - At bin edges the fraction equals the exact piecewise-linear value to rounding (checked against brute force
    to 2·10⁻⁵ on a test track).
  - Off the edges the proration adds an error of up to about the time in one bin: 5·10⁻⁴ for 1.03°–3.37° at
    Site20, 1 m, 30 days (0.25343 against 0.25293).

### 5.4 Communications (F4): `CommsMetrics`

These metrics describe the Earth as seen from the site: whether a direct line of sight to the Earth's disc
exists. They do not check whether a ground station on Earth can see the Moon at that time, nor link budgets
or relay satellites. Earth-side ground-station visibility is out of scope. No minimum Earth clearance is
applied by default.

| Field | Definition |
|---|---|
| `earth_visibility_fraction` | Time in W with any part of the Earth disc visible, divided by T. |
| `earth_full_disc_fraction` | Time in W with the whole Earth disc above the terrain horizon (`f_earth = 1`), divided by T. |
| `longest_earth_gap_h` | Longest continuous period with no part of the Earth disc visible, clipped to W, h. 0 if there is none. |
| `longest_earth_gap_clipped` | True if that gap starts before W or runs past it; false if it lies inside W or there is none. |
| `earth_elevation_deg` | Apparent elevation of the Earth's disc centre above the local horizontal plane: min, max and time mean over all of W, whether or not the Earth is visible. |
| `earth_clearance_deg` | Earth disc centre elevation minus the terrain horizon elevation at its azimuth: min, max and time mean over all of W. |
| `sun_earth_overlap_fraction` | Time in W with any part of both discs visible, divided by T. |
| `time_to_earthset_h` | From `window_start` to the first Earthset (the last visible part of the Earth disc going below the terrain horizon), h. Null if there is no Earthset in the window. |
| `earthset_in_window` | True if at least one Earthset occurs in W, false if none does. Null only if not computed. |

### 5.5 Computation and accuracy (`lss.series`, `lss.metrics`)

- **Internal grid.** Each body is sampled every 60 s over the window (`SeriesParams.grid_step_s`). Time axis:
  seconds since `window_start`, ephemeris time = et(`window_start`) + seconds. This assumes no leap second
  inside the window (none is scheduled) and ignores the periodic TDB − UTC terms (< 2 ms).
- **Each body on its own.** A body's visibility depends only on its own ephemeris and the horizon.
  `compute_visibility(..., bodies=("SUN",))` computes the Sun alone: identical to the Sun of a full call
  (every sample, period and event; tested on the served Site01 scenario), in 1.2 s instead of 2.1 s there.
  The Earth can be computed alone the same way. Served results compute both.
- **Visibility margins.** Two continuous functions of time decide visibility, evaluated over 101 columns
  across the disc: *any part* = max over columns of (column top − horizon), positive iff some part is visible;
  *whole disc* = min over columns of (column bottom − horizon), ≥ 0 iff all of it is. Their sign changes
  between grid points are refined by bisection to 0.5 s. The refined times split the window into the periods
  of section 5.2, and rises and sets become the events (`sunrise`, `sunset`, `earthrise`, `earthset`,
  `refined: true`).
- **Visible fraction.** 1 for a whole visible disc and 0 for a hidden one, exactly (from the margins, so
  fractions and periods agree). For a partly hidden disc, integrated column by column: along each column the
  chord above the horizon is integrated in closed form (uniform, or the limb-darkening law); across columns,
  the midpoint rule in φ with x = r sin φ over 192 columns, normalised by the same quadrature of the whole disc.
  A disc point at horizontal offset x is at azimuth az + x / cos(el) (tangent plane on the sky; its error in the
  fraction grows as tan(el), see "High elevations" below). Accuracy of the quadrature against closed-form
  circular segments: better than 1e-5 (tested). Against a
  brute-force 2-D integration: 5e-5 for a horizon rising 4° within one 0.1° azimuth interval, 2e-3 for an
  extreme 20° rise. The served horizon changes by at most 0.039° between neighbouring azimuths.
- **Durations and fractions** (illumination, Earth visibility, whole-disc, overlap, sunlit and longest
  periods) come from the refined periods, so they are not limited by the grid. **Time means** (visible
  fraction, elevations, clearance) integrate the 60 s grid with the trapezoid rule. **Azimuth arcs** come from
  the unwrapped 60 s track (section 5.3).
- **Grid convergence.** The served scenario with a 15 s grid instead of 60 s: every duration and count
  identical (to 1e-9 h), mean visible fraction changed by 6e-10.
- **Tests** (`tests/engine/test_series.py`, `test_metrics.py`): the law is 1 at μ = 1 and 0.30 at the limb,
  and its disc mean is 0.805; fractions against closed-form segments and brute-force integration (flat,
  sloped and jagged horizons, a disc straddling north); margins against brute force; rise and set times on
  synthetic tracks known in closed form (within 1 s), periods tiling the window, clipped edges, a 36 s
  flicker counted; every metric on synthetic series with known answers; on real data, the served scenario's
  responses, fractions against brute force on the real horizon, and grid-step independence.
- **End to end on a synthetic DEM** (`tests/engine/test_synthetic_e2e.py`, C3). A ring ridge around a point at
  88°S gives a horizon that is the same at every azimuth and known analytically (h₀ ≈ 0.16°). The whole engine
  path runs on it with the real ephemeris for 120 days (about four lunar days). That path is the ray caster,
  the disc margins and their refinement, the visible fractions and the metrics.
  - **Expected values** use only the ephemeris and h₀. Any part of a disc is visible iff el + r > h₀, and all
    of it iff el − r ≥ h₀. The Earth's fraction is the circular segment above the horizon line. The Sun's is
    the limb-darkened segment, integrated by brute force.
  - **Results.** The ray caster matches h₀ to 2·10⁻⁵°. There are 7 Sun and 8 Earth rises and sets. Every
    crossing is within |horizon error| / elevation rate + 2 s (at most 3.6 s, at a grazing Sun). The time
    fractions, Earth segment fractions, shadow count, longest shadow and Sun–Earth overlap all match.
- **High elevations, up to the zenith** (`tests/engine/test_high_elevation.py`, 2026-11-23).
  Two approximations were made for bodies near the horizon, as at the poles. A disc point at tangent-plane offset
  (x, y) is put at azimuth az + x / cos(el) and elevation el + y. The azimuth arc unwraps the 60 s track, which
  assumes the azimuth turns the short way between samples. Both are tested against exact geometry on the
  celestial sphere: the disc is the cap of angular radius r around the centre direction, and each point's true
  azimuth and elevation come from its unit vector.
  - **Partly hidden discs.** The tangent-plane model's error in the visible fraction is about 0.1 × r × tan(el),
    r in radians. This holds from 5° to 89° for the Sun (r = 0.27°) and the Earth (0.95°), on flat horizons
    (against an exact ring integral) and jagged ones (against brute force on the sphere). For the Sun it is
    4·10⁻⁵ at 5°, 1.3·10⁻⁴ at 15°, 8·10⁻⁴ at 60° and 0.027 at 89°. For the Earth it is 1.5·10⁻⁴ at 5° and
    4.7·10⁻⁴ at 15°. The cause is the almucantar's curvature across the disc, which the tangent plane leaves out.
  - **Visibility margins.** For a flat horizon the margins are exact, because the disc's top and bottom points
    lie on its vertical through the centre. For sloped horizons their error is at most about r² tan(el) / 2:
    1.7·10⁻⁴° for the Sun at 15°, and 0.0015° for the Earth at 11°. Both are within the accepted horizon error
    of 0.01° (section 3.2).
  - **Near the zenith.** A disc above the terrain is exactly whole (fraction 1, margins positive) at 80°, 89°,
    89.9°, 89.99°, 89.999° and 90°, under horizons up to 30°. This holds even though az + x / cos(el) is far
    from the true azimuth there, and above 89.73° the Sun's disc contains the zenith.
  - **Azimuth arc.** Great-circle passes at the Sun's mean rate, 2°, 0.1°, 0.005° and 10⁻⁴° from the zenith,
    north and south, give the closed-form arc. At 10⁻⁴°, 85 times closer than one 60 s step, the azimuth swings
    by more than 170° between two samples and still turns the short way. End to end, a ten-day pass 0.005° from
    the zenith under a horizon up to 20° gives no events, one visible period and every fraction exactly 1.
  - **Where partly hidden discs occur in the served results.** Only where a body is within its radius of the
    terrain horizon. At the polar sites the Sun stays within about 6° of the horizontal and the Earth within
    about 11° (10.6° at the 85°S sites, where the G2 review's exact-sphere fractions agree with ours), whatever
    the horizon (the highest served one is 15.7°, Artemis III De Gerlache Rim 2). At the Apollo sites the
    highest horizon is 14.2° (Apollo 17; Apollo 15 13.5°), and the Earth stays between
    43.5° and 80° elevation, always wholly above the terrain. In the served Apollo series the partly visible Sun
    samples are at most 7.8° high (Apollo 15). Up to 15° the fraction error is below 1.5·10⁻⁴ (Sun) and
    5·10⁻⁴ (Earth), and only during the minutes a disc is crossing the horizon. Measured on the real ephemeris,
    the Sun's azimuth arc from the 60 s track equals the arc from a 2 s track in all twelve 1 m Apollo scenarios
    of 10 and 30 days. Apollo 11 is among them, where the Sun reaches 89.7°.
- **Cost.** The served scenario (30 days, both bodies) takes about 2 s with the horizon cached; two years of
  Sun-only visibility take about 35 s (development PC).

### 5.6 Slope (`lss.terrain.slope`)

For the `terrain` and `site_summary` operations (C api's request RA4).
- **Slope at a pixel:** central differences, tan(slope) = hypot(dz/dx, dz/dy), with
  dz/dx = (z[col + 1] − z[col − 1]) / (2 Δx), and likewise along rows. It is the angle between the local
  surface and the plane normal to the sphere's radius.
  - It reproduces Barker et al. (2021)'s published 5 m slope maps (product 78 `*_slp.tif`), whose method is
    not stated: Site01's map to a median 0.0001° and a 99th percentile of 0.001° (tested). A 3×3 Horn estimate
    would differ from it by a median 0.10°, up to 17° on crater walls.
  - Chosen for that reason (Kaitlin, 2026-11-15).
- **Ground distances.** The polar stereographic map is conformal and true at the pole, with scale factor
  k = 1 + (ρ / 2R)² at map distance ρ from the pole: 1.0002 at 88°S, 1.0037 at 83°S. A map step Δx is a
  ground step Δx / k.
- **Statistics within a radius:** min, max and mean over the pixels whose centres lie within that ground
  distance of the point. The slope at the point is the slope of the pixel containing it, on that radius's own
  map, so one site has two values: Site07 1.61° on the 5 m map and 0.57° on the 10 m map; Site04 5.07° and
  5.76°.
- **Layers** (Kaitlin, 2026-11-15):
  - 1 km statistics are measured on the 5 m site tile.
  - 10 km statistics are measured on the 10 m polar map over the whole circle, because the 5 m tiles reach only
    6–9 km from the served points. One map per statistic keeps min, max and mean comparable within it.
  - The Artemis III regions (section 1.4.3) follow the same rule: 1 km on the 5 m site map where the region's
    point lies on one (Malapert Massif, Mons Mouton, Nobile Rim 1), otherwise on the 10 m map; 10 km on the
    10 m map. The Apollo sites, off the polar maps, use the 237 m global map at both radii (section 5.6.1).
  - Slopes on a 10 m map are gentler than on a 5 m map: features smaller than about 20 m are not resolved.
- **Limits.**
  - About 90% of 5 m pixels are interpolated between LOLA tracks (Barker et al. 2021). Single-pixel slopes are
    therefore low confidence, with a median RMS slope error of 1.9° (Barker et al. 2021, section 4).
  - The maximum within a radius picks out crater walls and the steepest single pixel, not a typical value.

#### 5.6.1 Slope off the polar maps: the global coarse layer (C7)

For sites with no polar map, the Apollo sites (Kaitlin, 2026-11-16), slope is measured on LOLA LDEM_128
(section 3.5) by `lss.terrain.slope.slope_stats_lonlat`, through `lss.terrain.global_layer.global_slope_stats`.
The polar path above is unchanged.
- **Same definition:** central differences, tan(slope) = hypot(dz/dx, dz/dy), on the simple-cylindrical grid.
- **Ground steps differ by direction.** North–south, a pixel is R Δφ = 236.90 m. East–west, it is R cos φ Δλ at
  each row's own latitude: 236.9 m at the equator, 213 m at Apollo 15 (26.1°N). R is the 1737.4 km sphere the
  heights refer to.
- **Matched east–west baseline.** The east–west difference is taken n columns either side,
  dz/dx = (z[col + n] − z[col − n]) / (2 n R cos φ Δλ), with n = round(1 / cos φ), at least 1
  (`ew_offset_px`). The east–west baseline then stays between 2/3 and 4/3 of the north–south one (474 m) at
  every latitude. n = 1, the plain central difference, wherever |φ| < 48.19°, which includes every Apollo site;
  n is 2 at 60°, 11 at 85°, 29 at 88° and 57 at 89°.
  - Why: with n = 1 the baseline is 2 R cos φ Δλ, 41 m at 85° and 8 m at 89°. The heights are stored in 0.5 m
    steps, so near the poles that step alone made slopes of several degrees. On LDEM_128 at 89° S, the median
    10 km mean slope over 40 random longitudes was 18.2° with n = 1, against 9.7° on the 240 m polar map; with
    the matched baseline it is 9.6°. The same happens near the north pole (the formula is symmetric).
  - The window read for the statistics is widened east and west by n − 1 columns at the circle's most
    poleward latitude, so every pixel within the circle has both neighbours. A pixel whose neighbours fall
    outside the grid has no slope.
- **Same outputs:** the slope of the pixel containing the point, and min, max and mean over the pixels whose
  centres lie within 1 km and within 10 km (great-circle distance). Edge pixels of the window are not used.
  A 1 km circle holds 56–63 pixels at the Apollo sites, and a 10 km circle 5,600–6,240.
- **At the poles:** east and north are undefined at the pole itself, so no slope is computed there. Statistics
  are computed while the circle stays clear of the pixel row next to the pole (centred 0.0039° from it), and
  refused from there on: for a 1 km circle, points within 0.037° of either pole; for 10 km, within 0.334°. A
  window that would span every longitude is refused for the same reason.
- **How to read them: regional slopes, low fidelity.** With ~237 m pixels, each slope is the average gradient
  over about 470 m (two pixels in each direction). Features smaller than about half a kilometre are not
  resolved, and slopes come out gentler than on the 5 m and 10 m maps used at the polar sites, so the two are
  not comparable. As section 3.5 notes, LDEM_128's label says gaps in LOLA coverage were filled by
  interpolation (GMT "surface"); slopes there describe the interpolated surface.
- **Checks** (`tests/engine/test_slope_lonlat.py`):
  - Planes tilted north, east and in other directions at latitudes 0.5–70° give their slope. A plane tilted
    east would come out wrong if the north–south step were used east–west (half the gradient at 60°).
  - A cone's statistics count exactly the pixels within the circle, counted independently.
  - The same cone at 0.05°E, where the window is read in two slices across the 0/360 meridian, and at 90.05°E
    gives identical statistics. So does a point given as −0.02°E or 359.98°E.
  - Where LDEM_128 and the 240 m polar map overlap, the two paths' 10 km mean slopes agree within −2.8% to
    +3.4% at seven points from 65°S to 89°S (2026-11-24; the test allows 5%). With n = 1 everywhere they
    differed by +2% to +4% at 65–70°S, +11% at 85°S, +25% at 88°S and +66% to +140% at 89°S, and the 10 km
    maxima reached 66–88° south of 85°S (now 27–31°, against 23–28° on the polar map).
  - A plane of 5° in the point's tangent frame, with heights rounded to 0.5 m and read through the same
    window code, gives 5 ± 0.15° at every pixel within 1 km and 10 km, and a mean of 5 ± 0.01°, at 85°N, 88°N,
    89°N and 89°S. The 2-pixel difference misses that bound on the same heights.
  - Below 48.19° the slopes are bit for bit those of the plain central difference (tested). The Apollo sites'
    1 km and 10 km statistics recomputed with the matched baseline equal the served values exactly
    (2026-11-24).
  - At the Apollo sites (|latitude| ≤ 26.1°) the east–west step is 0.90–1.00 of the north–south step.
- `SLOPE_VERSION` is unchanged: the polar definition and statistics have not changed, and on LDEM_128 every
  served slope (all at |latitude| < 48.19°) is computed exactly as before.

#### 5.6.2 Aspect and gradient

`lss.terrain.slope` also gives the direction of the slope. Nothing served uses it yet.
- **Same differences as the slope.** `gradient_ps` (polar stereographic maps, along the map's x and y axes)
  and `gradient_lonlat` (latitude/longitude grids, east and north, with the matched east–west baseline of
  section 5.6.1) return the height gradients that `slope_deg` and `slope_deg_lonlat` use. The slopes returned
  by `slope_aspect` and `slope_aspect_lonlat` equal those functions' exactly (tested).
- **Aspect:** the downhill azimuth, clockwise from north, in [0°, 360°): atan2(−∂z/∂east, −∂z/∂north). It is
  undefined (NaN) on a flat pixel.
- **East and north on a polar stereographic map.** At map position (x, y), at distance ρ from the pole, north
  is (x, y)/ρ on the south polar map and −(x, y)/ρ on the north polar map; east is north turned 90° clockwise.
  The map is conformal, so the map gradient turned into those directions gives the aspect. At the pole itself
  (ρ = 0) east and north are undefined and the aspect is NaN; the slope is still defined there.
- **Checks** (`tests/engine/test_aspect.py`). Planes of 7° defined in a point's tangent frame, rising towards
  0°, 75° and 200° (and 300° on the polar grids):
  - on a 5 m polar stereographic grid at 85.3°S, 89.5°S and 86°N, the pixel at the point has the plane's
    aspect within 0.01° and every pixel the slope within 0.01°. Away from the point, the plane's aspect turns
    with the meridians by |Δλ| sin|φ| (0.2° at 89.5°S, 50 m from the point), and every pixel stays within
    that;
  - on latitude/longitude grids at 0.5°, 26.1°, −45°, 70°, 89° and −89°, the pixel at the point has the
    aspect within 0.05° and the slope within 0.01°.

### 5.7 Terrain images for the 2D site view (`lss.terrain.views`)

Georeferenced PNGs on the DEM's own south polar stereographic grid (`scripts/terrain_views.py`; layout and views
decided by Kaitlin, 2026-11-16). "Map up" is the grid's +y axis, not geographic north. For each PGDA site and
each Artemis III region, two square views centred on the served point:
- **2 km:** from the 5 m site map, 400 × 400 px at 5 m. The six Artemis III regions whose point lies on no 5 m
  map get it from the 10 m polar map instead, 200 × 200 px at 10 m.
- **20 km:** from the 10 m polar map averaged over 2 × 2 pixels, 1000 × 1000 px at 20 m.
- None for the Apollo sites, which are off the polar maps.

Two layers per view; `view.json` gives the bounds, projection, pixel size, source and encodings:
- **Hillshade:** cartographic shading for reading the relief, not the real Sun. Light from map azimuth 315° at
  45° elevation, with the gradient by central differences.
- **Slope:** the definition of section 5.6 at the view's own pixel size, in five classes: under 5°, 5–10°,
  10–15°, 15–20°, 20° or more. The image stores the class number; the client chooses the colours. The suggested
  colours are one-hue blue ramps for light and dark surfaces, flattest lightest on light surfaces. Both pass the
  ordinal checks of the dataviz validator (monotone lightness, visible steps, end step at least 2:1 against the
  surface). Slopes at 20 m are gentler than at 5 m, so the two views' classes are not interchangeable.
- A pixel without data, or with a neighbour without data, is marked as no data. In the 20 km view a pixel is
  without data if any of its four 10 m pixels is.

## 6. Validation results (step 4.7)

All numbers below come from committed scripts. Their outputs are committed too and checked by tests:

- `scripts/horizons_check.py` → `tests/engine/fixtures/horizons_site01_roi4.json`, tested by
  `tests/engine/test_validation_horizons.py`;
- `scripts/validation_c1.py` → `tests/engine/fixtures/validation_c1.json`, tested by
  `tests/engine/test_validation_c1.py`;
- `scripts/precompute_c1.py` → the served result and the regression fixture
  `tests/engine/fixtures/site01_roi4_c1.json`, tested by `tests/engine/test_regression_c1.py`.

Every tolerance was fixed before the run it applies to. One comparison misses its tolerance (section 6.3); it
is reported as a miss, with the diagnosis, and the tolerance was not changed afterwards. The repository cannot
show that order: commit `6c26af2` added the tolerances and the results together. The order is recorded, with
dates, in the engine stream's progress log, which is kept outside the repository.

Why each tolerance has its size:

- **JPL Horizons, 1″:** far below anything the results depend on (section 6.1).
- **Barker bound, −1.0 pp, −2 d, +1 d:** small allowances for the method differences that remain, each measured
  as much smaller (the disc cut and the limb-darkening law, at most 0.02 pp, section 5.1; whole-hour sampling of
  LCIP and LCSP). They are not derived from an error model. The margins are 3 to 28 times larger than the
  tolerances, so the choice does not decide the result.
- **Barker 70% contour, 0.5 pp:** suggested by the G1 reviewer, whose sample of the outside pixels came within
  0.08 pp of the contour (section 6.2).
- **Product 69, 5 pp:** had no stated basis. With the measured half-pixel sensitivity (section 6.3) it could
  not tell a correct engine from a wrong one. The C3 rerun gets a tolerance derived from that sensitivity.

| Check | Tolerance | Result | Verdict |
|---|---|---|---|
| Sun and Earth az/el vs JPL Horizons, 25 epochs 2024–2050 | 1″ | ≤ 0.05″ | pass |
| The same at a second site, Site06 (85.3°S, 37°E) | 1″ | ≤ 0.05″ | pass |
| Barker RoI 4 average illumination (≥ 1st percentile) | −1.0 pp | 77.46% vs 69.61% | pass |
| Barker RoI 4 LCIP (≥ 1st percentile) | −2 d | 192.2 d vs 136.49 d | pass |
| Barker RoI 4 LCSP (≤ 99th percentile) | +1 d | 10.05 d vs 13.27 d | pass |
| Barker 70% contour, two-sided: inside ≥ 70%, edge neighbours outside ≤ 70% | 0.5 pp | inside min 70.03%, outside max 70.19% | pass |
| Barker Fig. 19 nominal-DEM values (qualitative) | none | read 77.5% / 192 d / 10.1 d; ours 77.46% / 192.2 d / 10.05 d | agrees |
| Product 69, Earth, 5 × 5 pixels: mean \|difference\| | 5 pp | 3.3 pp | pass |
| Product 69, Sun, 5 × 5 pixels: mean \|difference\| | 5 pp | 8.7 pp (no bias: mean −1.7 pp); 7.56 pp without the zero pixel (diagnostic) | **miss**; inconclusive at this resolution; accepted for G1 as a stated difference (section 6.3) |
| Product 69 rerun (C3), stand-in terrain `LDEM_75S_60M`: Sun at 0 m / 2 m; Earth | Sun 9.6 pp (derived); Earth 5 pp | Sun 7.28 / 17.74 pp; Earth 2.80 / 4.30 pp | Sun pass at 0 m (miss at 2 m); Earth pass |
| Ridge-top: the Sun is seen only below the local horizontal | (stated) | confirmed four ways (section 6.4) | confirmed |
| Barker RoI definition at Site04, 07, 11 (sampled pixels > 70%) | 0.5 pp | Site04 70.02%, Site11 70.01%; Site07 one pixel at 69.03%, enclosed by the outline | pass, pass, **miss** (section 6.7) |
| Mazarico et al. (2011) Table 3, 8 sites, matched method | from 120 m shifts | all four comparisons above tolerance; at 10 m the 7 points other than rank 20 agree within 1.4 pp | **miss** (section 6.7) |

How well the served numbers themselves are known (the terrain map limits them, not the numerics) is in
section 6.6.

### 6.1 Ephemeris vs JPL Horizons

- **Reference.** JPL Horizons (Giorgini et al. 1996), queried through its API for a user-defined site on the
  Moon: the served point (222.851347° E, 89.452675° S) at 1957.39 m above the 1737.4 km sphere (DEM surface
  1956.39 m + 1 m). Horizons uses DE441 and its own lunar mean-Earth frame (`MEAN_ME`, "high precision"), so it
  is independent of our DE421 kernels. Its quantity 4 is the apparent azimuth and elevation: light time,
  stellar aberration and light bending, no refraction.
- **Epochs.** 25 epochs: 11 across the served window and 14 spread over 2024–2050 (one every two years, at
  varied dates and hours). Sun and Earth.
- **Tolerance:** 1″ (0.00028°) in azimuth, in elevation and in angular separation. That is far below anything
  the results depend on: the horizon step is 0.1° (360″) and the Sun's radius is about 0.27°.
- **Result.** The largest separation is 0.044″ for the Sun and 0.050″ for the Earth. The largest azimuth
  difference is 0.02″ and the largest elevation difference 0.05″. Distances agree to 14 m (Sun) and 4 m (Earth).
  The DE421 vs DE441 and frame-realisation differences are invisible at this level. Light bending, which
  Horizons includes and we don't, is far smaller still for these geometries.
- **Second site** (G2 review m3): Site06, 85.30°S 37.07°E at 1 m, far from the pole at an eastern longitude
  (`scripts/horizons_check.py --site pgda-site06`, fixture `horizons_pgda-site06.json`, same epochs). The
  largest separation is 0.044″ for the Sun and 0.050″ for the Earth, with the Earth up to 10.2° high. Other sites
  are checked against SPICE's own `azlcpo` with the same kernels.

### 6.2 Barker et al. (2021): RoI 4 bound

- **Setup** (section 4.1). Every 5 m pixel in Barker's RoI 4 outline (`Site01_ROIs.tgz`, polygon 4). The
  outline runs through pixel centres, so the RoI is the pixels inside it or on it: **532 pixels = 13,300 m²**,
  exactly Barker's Table 2 area, with the centroid at Barker's (−11.2875, −12.1675) km. Each pixel gets its own
  horizon at 1 m (default settings) and two years of Sun visibility, 2024-01-01 to 2026-01-01.
- **Like with like.** Table 2's A rows are, for each DEM clone, the RoI average of the per-pixel values; the
  percentiles are then taken over the 100 clones. (The C rows use the most illuminated pixel at each hour; A
  must be per-pixel averages, because its LCIP differs from C's.) Barker samples hourly, so a shadow shorter
  than about an hour is invisible to Barker's LCIP and LCSP. We therefore compare values computed from **hourly
  samples**: the time-mean visible fraction, and the longest runs of hours with any / no part of the Sun
  visible. Our own definitions (section 5, refined periods) give 77.46%, 191.8 d and 10.04 d, almost the same.
- **Internal grid.** The area run uses a 600 s internal grid instead of 60 s. On 11 of the pixels both grids were
  run: average illumination, LCIP, LCSP and illumination fraction agree to better than 10⁻⁵. At 2 of the 11
  pixels the 60 s grid finds one more short shadow period.
- **Result** (RoI average over 532 pixels, nominal DEM):

  | RoI 4, z = 1 m, 2024–2025 | Ours | Table 2 A (bound) | Tolerance | Margin |
  |---|---|---|---|---|
  | Average illumination | **77.46%** | ≥ 69.61% (1st pct) | −1.0 pp | +7.85 pp |
  | LCIP | **192.2 d** | ≥ 136.49 d (1st pct) | −2 d | +55.7 d |
  | LCSP | **10.05 d** | ≤ 13.27 d (99th pct) | +1 d | 3.22 d |

  All three pass. **This bound is one-sided:** it rules out a result that is too dark, but an engine that
  overestimated sunlight would pass it too. The two-sided check is the contour test below.
- **Barker's 70% contour, two-sided** (G1 review, finding M1). Barker drew each RoI as the connected pixels
  ("corners or sides touching") with average illumination above 70% at 1 m over 2024–2025 on the nominal DEM,
  and a total area above 2500 m² (section 5). So the engine should put the 70% line where
  Barker's outline is: pixels inside above it, and the pixels just outside at or below it.
  - **Set-up.** Stage `barkerring` computes every 5 m pixel outside RoI 4 that touches it: 172 pixels, 114
    sharing an edge with the RoI and 58 touching only a corner. Same quantity, period and grid as the inside
    pixels.
  - **Test, fixed before the run:** inside minimum ≥ 70% − 0.5 pp, and the edge neighbours' maximum
    ≤ 70% + 0.5 pp. Edge neighbours must be at or below 70% whether Barker joined pixels by edges or by corners.
    Corner-only neighbours must be too if corners count. Barker's text says they do ("corners or sides
    touching"; found after the run), so the test now also covers the corner-only neighbours.
  - **Result: pass.** Inside: 70.03–85.12% (532 pixels). Edge neighbours: 55.8–70.19%, median 68.5%; 6 of the
    114 lie between 70.0% and 70.19%. Corner-only neighbours: 49.5–68.7%, none above 70%.
  - The engine places Barker's contour to within 0.2 pp on both sides. That is a much sharper check than the
    bound above, and it is a Sun check on the same ridge as the served point. The G1 reviewer's sample of every
    3rd ring pixel (57 of 58 at or below 70%, the other 70.08%) had been seen before the tolerance was set.
- **Fig. 19, qualitative.** Barker's nominal-DEM values for RoI 4, read from the figure (open circles), are about
  77.5%, 192 d and 10.1 d, with the LCIP running from late September 2024 to late March or early April 2025.
  Ours: 77.46%, 192.2 d and 10.05 d, with the median pixel's LCIP running from 2024-09-07 to 2025-03-27. The
  values agree to the precision of reading the figure.
- **C rows, qualitative** (most illuminated pixel at each hourly step): ours 86.86%, 232.54 d and 4.54 d, against
  Barker's 1st percentiles of 86.81%, 232.50 d and 4.58 d (99th percentile for LCSP).
- **Cost** (the first area measurement, for C3): 532 points × 2 years of Sun took 4,607 s on the development PC,
  a median of 8.0 s per point. Uncontended, that is a 3.7 s horizon plus a 3.0 s series.

### 6.3 PGDA product 69: internal pass (never served)

**Scope: Site01 only.** The comparison covers the 5 × 5 product 69 pixels around Site01's served point. It was
not repeated at the other curated sites (Kaitlin, 2026-11-16); it may be after submission. The other sites
are checked against published numbers in section 6.7.

- **Setup** (section 4.2). The observer is at 0 m on the 60 m map (`LDEM_60S_60MPP_ADJ` to 148 km, then 240 m to
  400 km). The quantity is the share of hourly time steps with any part of the disc visible. Each run covers 18.6
  years, from two start dates (2000-01-01 and 2024-01-01), and is averaged. It is computed at the 5 × 5 product 69
  pixels around the RoI 4 centroid; both maps share the same 60 m pixel grid. Tolerance, set before the run: mean
  |difference| over the 25 pixels ≤ 5 percentage points (pp).
- **Earth: pass.** Mean |difference| 3.3 pp, mean difference +1.5 pp, correlation 0.80. The RoI 4 pixel reads
  57.5% (product 69) and 58.3% (ours). The two start dates differ by at most 0.06 pp.
- **Sun: misses the stated tolerance.** Mean |difference| **8.7 pp** (> 5 pp).
  - There is no overall bias: the mean difference is −1.7 pp, the correlation 0.72, and the RoI 4 pixel itself
    agrees within 2.5 pp (68.5% product 69, 71.0% ours).
  - The two start dates differ by at most 1.0 pp, so the unknown averaging dates do not explain the miss.
  - The miss is pixel-to-pixel scatter. Neighbouring product 69 pixels on this ridge range from 21% to 86%.
- **Diagnosis** (added after the miss, not a re-test).
  - At the 9 central pixels, our value moves by a median of 14 pp (up to 38 pp) when the observer is moved 30 m,
    half a pixel, in any of the four map directions.
  - Product 69's value lies within that range of shifted values at 4 of the 9 pixels.
  - Our 60 m map is a later, orbit-adjusted LOLA product. Product 69 used `LDEM_85S_060M` (2016), so features
    can sit tens of metres apart between the two maps. On a ridge, a shift that small changes 60 m pixel values by
    more than the miss.
  - One product 69 pixel is 0 in both its Sun and Earth maps, where its neighbours are 48–58% for Earth (ours:
    35% Sun, 36% Earth). This looks like an artefact in the product.
  - **Diagnostic: that pixel excluded** (requested after the miss; not a re-test, the tolerance applies to all
    25 pixels). Sun: mean |difference| **7.56 pp** over 24 pixels (still above 5 pp), mean difference −3.25 pp,
    correlation 0.72. Earth: 1.95 pp, mean difference +0.06 pp. So the miss is not caused by that pixel.
  - Conclusion: at 60 m on this ridge, a pixel-by-pixel comparison cannot be tighter than about 10 pp without
    product 69's own terrain. The Earth map, which depends far less on the near horizon, passes.
  - **Status:** accepted for G1 as a stated remaining difference (Kaitlin, 2026-11-15). Queued for C3: a
    like-for-like rerun on product 69's terrain. The map its label names, `LDEM_85S_060M`, is not public. The
    nearest public map is the PDS `LDEM_75S_60M` (version 2.0, 2017), on the same 60 m pixel grid as product
    69. Which map to use is still open.
- **What the Sun comparison shows: it is inconclusive at this resolution, not evidence against the engine.**
  A half-pixel move changes our values by more than the miss, so a mean difference of 8.7 pp can come from a
  correct engine as easily as from a wrong one. The 5 pp tolerance had no stated basis. Three things are still
  not like for like: the terrain map, the observer height (not stated by PGDA) and the averaging dates. The
  sharper Sun checks on this ridge are Barker's 70% contour (section 6.2) and the ridge-top check (section 6.4).
- **Tolerance for the C3 rerun, derived before it runs.** It is set from the half-pixel diagnostic above: the
  mean |change| over the 9 central pixels and the 4 directions is **9.55 pp**, so the tolerance is a mean
  |difference| of **9.6 pp** over the 25 pixels. That is the disagreement a correct engine would show if product
  69's pixel values sit up to half a pixel from where we place them. That uncertainty remains in the rerun,
  because product 69's own map is not public (below) and a stand-in map can place features tens of metres
  apart. The shifts mostly lower our
  values (mean change −7.3 pp), because the central pixels lie on the ridge crest.
  - The unknown observer height is bracketed: the rerun is made at 0 m and at 2 m, and both are reported.
  - The test passes at either height if mean |difference| ≤ 9.6 pp.
  - A tolerance this wide still cannot discriminate well. A sharper version would fit one map offset (two
    parameters) to all 25 pixels and judge the remaining scatter. That costs about 25 runs per trial offset, and
    the choice is Kaitlin's.
- **Terrain resolution** (section 4.3), at the RoI 4 centroid over 18.6 years from 2024. The same quantity on
  the served 5 m stack is 54.8% at 0 m and **87.0% at 1 m**; on the 60 m map at 0 m it is 71.0%. At 0 m on 5 m
  terrain, metre-scale relief blocks the Sun, and 1 m clears it. This is why product 69 (0 m, 60 m) and the served
  result (1 m, 5 m) must not be compared directly.

- **C3 rerun on a stand-in for product 69's terrain** (`scripts/validation_c3.py`, stage `p69`; tolerances
  fixed before the run, above).
  - **Terrain:** the PDS LOLA map `LDEM_75S_60M` (version 2.0, 2017; Neumann 2010, data set
    LRO-L-LOLA-4-GDR-V1.0) to 148 km, then the 240 m map. It stands in for `LDEM_85S_060M`, which is not
    public (Kaitlin, 2026-11-15). It is on product 69's 60 m pixel grid.
    At the 25 pixels its heights differ from the orbit-adjusted 60 m map by a mean of −0.44 m and at most 1.8 m.
  - **Sun at 0 m: pass.** Mean |difference| **7.28 pp** (≤ 9.6), mean difference −1.9 pp, correlation 0.78. The
    C1 run on the adjusted map gave 8.66 pp and 0.72.
  - **Sun at 2 m: miss.** 17.74 pp, and every pixel is brighter than product 69 (mean difference +17.7 pp).
    Product 69 fits a surface-level observer far better than a 2 m one, which supports the 0 m assumption.
  - **Earth: pass at both heights.** 2.80 pp at 0 m, 4.30 pp at 2 m (≤ 5).
  - The start dates change the Sun values by at most 0.9 pp. Without the zero-valued product 69 pixel
    (diagnostic only), the Sun at 0 m is 5.81 pp.
  - **What it shows.** On terrain closer to product 69's own, the engine agrees better, with no bias and the
    right sensitivity to height. The derived tolerance is still wide, so this is a consistency check, not a
    sharp test. The sharp Sun checks remain Barker's contour and the ridge-top check.

### 6.4 Ridge-top check: the Sun is seen below the local horizontal

**Finding.** In the served window the Sun's centre is below the local horizontal plane all the time (−1.56° to
−0.52°), yet some of the Sun is visible 69.8% of the time. Even its upper limb never rises above −0.26°. So all
of that visibility is the Sun seen *below* the local horizontal. A horizon at the local horizontal would give 0%.
This is possible only if the terrain horizon lies lower still, which is what a high ridge gives.

**Geometry.** The observer is 1957.4 m above the reference sphere. From that height, a smooth sphere's horizon
would be at −2.72° (dip = arccos(R / (R + h))). Real terrain only raises the horizon above that line: around
this point it lies between −2.62° and +0.34°.

**The horizon along the Sun's path while the Sun is visible** (served window, 60 s samples; horizon at the
disc centre's azimuth; "distance" is how far away the terrain that sets the horizon is):

| Sun azimuth | Visible (h) | Sun centre elevation | Horizon elevation | Horizon distance (km) |
|---|---|---|---|---|
| 0–30° | 21.4 | −0.85 to −0.80° | −1.08 to −0.54° | < 0.1 |
| 30–60° | 59.1 | −1.08 to −0.52° | −2.34 to −1.08° | < 0.1 |
| 60–90° | 71.6 | −1.14 to −0.52° | −2.43 to −1.22° | 0.0–48 |
| 90–120° | 59.0 | −1.17 to −0.85° | −2.62 to −0.84° | 37–199 |
| 120–150° | 41.7 | −1.43 to −1.17° | −2.23 to −1.07° | 102–143 |
| 150–180° | 30.8 | −1.51 to −1.43° | −2.24 to −1.25° | 0.4–156 |
| 180–210° | 21.5 | −1.56 to −1.53° | −1.82 to −1.30° | 0.6–9 |
| 210–240° | 57.3 | −1.53 to −1.39° | −2.02 to −1.13° | 1.2–42 |
| 240–270° | 58.9 | −1.39 to −1.17° | −2.57 to −1.29° | 37–89 |
| 270–300° | 58.8 | −1.17 to −0.94° | −2.04 to −0.78° | 0.1–60 |
| 300–330° | 22.3 | −0.94 to −0.87° | −0.81 to −0.61° | 0.1 |
| 330–360° | 0 | | | |

- **While the Sun is visible, the horizon at its azimuth ranges from −2.62° to −0.54°.** That is always below
  the local horizontal, and below the Sun's upper limb, whose clearance over the horizon is −0.01° to +2.14°.
  The −0.01° comes from partly visible discs whose centre column is just hidden but whose side columns are not:
  the disc is cut with the real horizon profile (section 5.1).
- Over 300–330° the horizon (−0.81° to −0.61°) is above the Sun's centre. The 22.3 h there are partial-disc
  time: only the top of the disc is in view.

**Four independent confirmations.**

1. **Independent ray scan.** At every 5° of azimuth the Sun visits while visible (53 azimuths), the horizon was
   recomputed by separate code. It reads the DEMs with rasterio, interpolates bilinearly, steps along great
   circles and takes the elevation angle from 3-D vectors. It shares the DEM files, the layer split and the ENU
   basis (`lss.ephem.enu_basis`) with the engine. So it tests the ray caster, not the data or the frame. The G1
   reviewer's separate horizon (PROJ for the map projection, its own ENU and 3-D geometry) agrees with the
   engine to 0.0034° at 360 azimuths, which also checks the projection and the map's orientation. It agrees with the engine to **0.037°** at worst. Only three azimuths differ by more than 0.01°, all
   where the horizon is set by terrain within 50 m, where the two codes sample the 5 m map differently. The
   low horizon is in the terrain data, not an artefact of the horizon code.
2. **Barker et al. (2021) Fig. 15**, Barker's own horizon at the RoI 4 centroid at 1 m, independent code.
   - Barker's horizon panels measure azimuth counter-clockwise from the map's +x axis. In our convention that
     angle a is az = (90° − longitude) − a. We found this mapping by matching the profile's shape, then derived
     it from the projection.
   - Under it, our horizon matches values read from the figure by eye at 16 angles with a median difference
     of 0.06°.
   - Two of those angles differed by about 0.8°. Both are where the horizon changes steeply with azimuth. At
     our azimuth 137° it rises from −2.00° (az 132°) to −0.94° (az 140°), set by terrain about 135 km away, in
     the Earth's direction. At 250° it falls from −1.48° (az 245°) to −2.52° (az 252°). So a reading error of a
     few degrees in angle explains both.
   - **Re-read** (G1 review, finding m3). The far-field line was digitised from a 1200 dpi render, column by
     column within 10° of each of the two angles. At 9 angles around them it agrees with ours to 0.10° at most
     (median 0.03°). Over every digitised column where the line is found, the median difference is 0.02° and
     the maximum 0.12°. The two 0.8° differences were errors in the eye reading.
   - This matters for communications: azimuths 134–142° are where the Earth is partly hidden in the served
     window (section 6.6).
   - Like ours, Barker's horizon at RoI 4 is below −1° over most azimuths.
3. **Barker's Table 2 needs it.** Over Barker's period, a horizon at the local horizontal would allow a
   time-mean visible fraction of at most **51.4%** at RoI 4 (Sun only, from the ephemeris). Barker's *1st
   percentile* for RoI 4 is 69.61%, and the nominal-DEM value (Fig. 19) is about 77.5%. Both are impossible
   unless the Sun is seen below the local horizontal for a large share of the time. Our 77.46% (section 6.2)
   agrees with that value.
4. **Product 69 needs it too.** Over 18.6 years from 2024, a horizon at the local horizontal would show some
   of the Sun 55.6% of the time. Product 69's RoI 4 pixel reads **68.5%**, and five of its neighbours exceed
   70%. Product 69 was computed by other people, with other code, on an older 60 m map, at surface level. It
   too sees the Sun below the local horizontal on this ridge. Our reproduction gives 71.0% there, and 87.0% for
   the served stack at 1 m.

**Verdict: the ridge-top result is confirmed directly.** In the served window the Sun is visible only below the
local horizontal, because the horizon around the ridge top lies lower still, at −2.6° to −0.5° along the Sun's
path. Our horizon code, an independent scan of the same DEMs, Barker's horizon, Barker's tabulated
illumination and product 69 all agree with this.

### 6.5 Served result and regression fixture

- **The served scenario** (key `00010cfa5fef681c`) was computed with the validated code and stored in two places:
  - the served result: `LSS_DATA_DIR/cache/served/c1_00010cfa5fef681c.json`, the metrics, series and horizon
    responses with their provenance, written by `scripts/precompute_c1.py` (file format 3; the horizon is the
    one the metrics were computed with, at every 0.1° azimuth; format 3 adds the Sun-elevation histogram,
    section 5.3);
  - the regression fixture: `tests/engine/fixtures/site01_roi4_c1.json`, the same metrics, every 6th hourly
    sample and every 10th horizon azimuth.
- `tests/engine/test_regression_c1.py` recomputes the scenario and requires fractions to agree to 10⁻⁶, durations
  to 10⁻³ h, angles to 10⁻⁶° and event times to 1 s.
- **Per-site fixtures (C3).** `tests/engine/fixtures/c3/<site id>.json` holds every other curated site's 1 m
  result over the same window. Each is written by `scripts/regression_c3.py` from the served file, so it is
  exactly what the API serves. `tests/engine/test_regression_c3.py` recomputes each with the same tolerances.
  Each fixture keeps the metrics, every 24th hourly sample and every 10th horizon azimuth.
- **Served scenarios (C3).** Every curated site with a PGDA tile (8), every Apollo site (6) and every Artemis III
  region (9), each at 1, 2, 5 and 10 m over three windows: 2028-05-15 + 30 d at PT1H (the C1 window), the year
  2028 at PT6H, and 2028-11-15 + 10 d at PT1H. That is 276 files in `LSS_DATA_DIR/cache/served/` (file format
  3, with the horizon and the Sun-elevation histogram), written by `scripts/precompute_c1.py` and
  `scripts/precompute_c3.py`, which also keeps `cache/served_c3_index.json`. Metrics always come from the 60 s internal grid; the window's step sets
  only the series.
- **Artemis III regions.** The point is the centre of the region's 1 km navigation grid (section 1.4.3), a
  geometric point, not a landing site. Malapert Massif, Mons Mouton and Nobile Rim 1 lie on 5 m site maps (fidelity
  high); the other six use the 80 m and 240 m polar maps (medium). Cost as for the PGDA sites: medians 6.5 s
  (30 days with a new horizon), 33.0 s (one year), 0.9 s (10 days).
- **Apollo sites: low fidelity.** The six Apollo landing sites are served at 1, 2, 5 and 10 m over the three
  standard windows (72 scenarios, `scripts/precompute_c3.py --sites apollo-11 …`). Their results use the
  low-fidelity global layer: the 237 m LOLA map `LDEM_128` is their only terrain, near and far (section 3.5).
  Every result carries the fidelity label "low".
  - At 237 m, relief smaller than a few hundred metres is not in the horizon. The values describe the regional
    setting, not a particular spot on the ground.
  - Their slope statistics are measured on the same 237 m map (section 5.6.1): regional slopes, not comparable
    with the 5 m and 10 m values at the polar sites. At 1 km the mean is 0.7–1.8°; at 10 km 0.6–9.7°.
  - **Cost** (development PC): 30 days with a new horizon, median 5.9 s (1.8–7.3 s); one year, median 32.6 s;
    10 days, median 0.9 s.
- **Final served values** at the 1 h step, alongside the 10-minute previews quoted when window B was chosen:

  | Metric | Served (1 h step; metrics from the 60 s grid, refined) | Preview (10 min) |
  |---|---|---|
  | Sun illumination fraction | 69.77% | 69.7% |
  | Mean visible disc fraction | 60.17% | n/a |
  | Shadow periods | 4 | 4 |
  | Longest shadow | 132.88 h (not clipped) | 132.8 h |
  | Earth visibility fraction | 63.56% | 63.5% |
  | Longest Earth gap | 262.40 h (not clipped) | 262.7 h |
  | Sun and Earth both visible | 45.10% | 45.1% |

  How well these values are known is in section 6.6.

### 6.6 Accuracy of the served numbers at Site01

This section is measured on the served C1 scenario (Site01, 1 m, 2028-05-15 + 30 d). Section 6.6.1 gives the
same measure at every PGDA site. The served values are exact for the nominal 5 m map, up to the numerical errors
measured in sections 3.2 and 5.5. How far they can be trusted beyond that depends on the terrain map, mostly within a few hundred metres of
the site.

**Sensitivity to the horizon** (`scripts/validation_c1.py`, stage `accuracy`). This is the served scenario
recomputed by the engine with its horizon shifted, either everywhere, or only at the azimuths where the horizon
is set by terrain less than 1 km away. The ephemeris, grids and observer are unchanged.

| Horizon change | Illumination | Mean disc fraction | Shadow periods | Longest shadow | Longest sunlit period | Earth visible | Longest Earth gap |
|---|---|---|---|---|---|---|---|
| none (served) | 69.77% | 60.17% | 4 | 132.9 h | 153.3 h | 63.56% | 262.4 h |
| whole horizon −0.01° / +0.01° | 70.01% / 69.51% | 60.52% / 59.82% | 4 / 4 | 132.3 / 133.4 h | 153.5 / 153.2 h | 63.60% / 63.51% | 262.1 / 262.7 h |
| whole horizon −0.05° / +0.05° | 71.05% / 68.35% | 61.94% / 58.42% | 3 / 5 | 130.2 / 135.6 h | 224.7 / 152.9 h | 63.76% / 63.35% | 260.9 / 263.9 h |
| whole horizon −0.10° / +0.10° | 72.40% / 66.54% | 63.72% / 56.68% | 5 / 5 | 127.5 / 138.4 h | 228.9 / 152.5 h | 63.97% / 63.13% | 259.4 / 265.4 h |
| whole horizon −0.20° / +0.20° | 76.58% / 62.22% | 67.23% / 53.08% | 5 / 4 | 118.5 / 164.6 h | 238.8 / 151.7 h | 64.39% / 62.71% | 256.4 / 268.5 h |
| only where set < 1 km away, −0.20° / +0.20° | 74.06% / 64.77% | 64.11% / 56.59% | 6 / 4 | 118.5 / 164.6 h | 153.3 / 153.3 h | unchanged | unchanged |

An independent brute-force calculation by the G1 reviewer (`reference/logs/review-g1.md`, finding M2) gives the
same table to within 0.02 percentage points and 0.1 h.

**What limits it: terrain errors near the site.**

- **Numerical error is small.** The horizon is computed to about 0.01° (section 3.2). That is worth about
  0.25 percentage points of illumination, about 0.5 h on the longest shadow and Earth gap, and no change in the
  shadow count.
- **The map's height error is not small, close to the site.** Barker et al. (2021, section 4) give a median RMS
  height error of **0.37 m** for the 5 m site map, from its 100 clones. A height error of 0.37 m changes the
  horizon by 0.42° for terrain 50 m away, 0.21° at 100 m, 0.02° at 1 km and nothing measurable at 50 km.
- **At the served point, near terrain sets much of the horizon.** It is set by terrain closer than 100 m at 36%
  of azimuths, and closer than 1 km at 53%. For 18% of the window part of the Sun's disc is hidden. During that
  time the horizon at the Sun's azimuth is set by terrain closer than 100 m 41% of the time.
- **So the Sun metrics are DEM-limited.** A ±0.2° near-field error, about Barker's median at 100 m, gives an
  illumination fraction of 64.8–74.1% (served 69.8%), 4–6 shadow periods (served 4) and a longest shadow of
  118.5–164.6 h (served 132.9 h).
- **Not a confidence interval.** The shifts above are uniform. Real errors vary with azimuth and partly average
  out, so the table gives the scale of the effect, not a probability.
- **The likely direction is darker.** Barker notes that the clones' height errors are "more likely to raise
  than lower the horizon elevation", and the nominal-DEM values tend to be better than the clone median. For
  the RoI 4 average over 2024–2025 the nominal value is about 77.5%, against a 1st percentile of 69.61%
  (sections 4.1 and 6.2).
- **The Earth metrics are far less affected.** While the Earth is partly hidden, its horizon is always set by
  terrain 134–140 km away (azimuths 134–142°). A near-field error leaves the Earth metrics unchanged, and even
  a 0.2° whole-horizon shift moves Earth visibility by less than 1 percentage point and the longest gap by
  about 6 h.

**The fragile metrics.**

- `shadow_count` changes with a 0.05° horizon shift. Of the four served shadows, the shortest lasts 1.67 h. A
  lower horizon removes it or splits others, and a higher one adds short shadows.
- `longest_sunlit_period_h` is 153.3 h, but a horizon only 0.05° lower merges two sunlit periods into 224.7 h.
  It is reliable only as "at least about 150 h".
- `longest_shadow_h` (132.9 h): a 0.05° horizon error (a 9 cm height error 100 m away) moves it by about
  3 h, and a 0.2° error (Barker's median height error at 100 m) by −14 to +32 h.

**Not yet done.** Bands from Barker's 100 clones of the 5 m map, which PGDA product 78 provides at Site01, are
planned (S6). They would replace the uniform shifts above with the real error distribution.


#### 6.6.1 Every PGDA site (1 m, 2028)

`scripts/validation_c3.py`, stage `accuracy_sites`: the year 2028 at 1 m with the horizon moved by −0.2° / +0.2°
where terrain closer than 1 km sets it, as in the last row of section 6.6. Each site's shifted runs and their
baseline share a 600 s grid; the baseline equals the served values to 0.1 pp. Illumination here is
`illumination_fraction` (time with any part of the Sun visible).

| Site | Azimuths with the horizon set < 100 m / < 1 km | While the Earth is partly hidden: horizon set < 100 m / < 1 km | Illumination % (−0.2° / +0.2°) | Earth visible % (−0.2° / +0.2°) |
|---|---|---|---|---|
| Site01 | 36% / 53% | 0% / 0% | 87.5 (90.0 / 85.6) | 61.7 (61.7 / 61.7) |
| Site04 | 30% / 38% | 52% / 100% | 74.8 (76.8 / 72.5) | 52.9 (53.8 / 52.0) |
| Site07 | 37% / 71% | 53% / 100% | 82.3 (83.9 / 80.7) | 58.7 (59.6 / 57.7) |
| Site11 | 13% / 38% | 0% / 0% | 85.1 (85.8 / 84.5) | 65.0 (65.0 / 65.0) |
| Site06 | 50% / 93% | 0% / 100% | 46.6 (49.6 / 43.1) | 63.5 (64.4 / 62.5) |
| Site20 | 0% / 75% | 0% / 100% | 17.2 (18.7 / 15.9) | 44.0 (45.0 / 42.9) |
| Site23 | 61% / 66% | 100% / 100% | 52.0 (56.1 / 49.1) | 51.5 (52.4 / 50.5) |
| Site42 | 47% / 48% | 100% / 100% | 47.9 (48.8 / 47.0) | 36.7 (37.8 / 35.5) |

The served values at 1 / 2 / 5 / 10 m (2028):

| Site | Illumination % | Earth visible % |
|---|---|---|
| Site01 | 87.5 / 90.5 / 93.1 / 96.0 | 61.7 / 61.7 / 61.8 / 61.8 |
| Site04 | 74.8 / 83.9 / 86.3 / 88.0 | 52.9 / 54.2 / 55.6 / 57.9 |
| Site07 | 82.3 / 86.2 / 88.8 / 88.9 | 58.7 / 60.5 / 64.0 / 64.6 |
| Site11 | 85.1 / 86.2 / 87.9 / 88.5 | 65.0 / 65.0 / 65.0 / 65.0 |
| Site06 | 46.6 / 61.2 / 87.8 / 90.2 | 63.5 / 64.7 / 67.7 / 72.7 |
| Site20 | 17.2 / 18.9 / 24.7 / 36.0 | 44.0 / 45.0 / 48.1 / 52.4 |
| Site23 | 52.0 / 73.7 / 85.4 / 85.5 | 51.5 / 59.6 / 69.7 / 81.7 |
| Site42 | 47.9 / 51.6 / 72.1 / 81.8 | 36.7 / 42.2 / 56.2 / 64.3 |

- **Sun.** By this measure the other sites are no less certain than Site01. A ±0.2° near-field shift moves the 2028
  illumination by under 1 pp (Site11, Site42) to about 4 pp (Site23). Section 6.6's 64.8–74.1% is the 30-day
  window, when the Sun is low.
- **Earth.** Its metrics are insensitive to near-field terrain only at Site01 and Site11. At the other six sites
  the Earth's horizon is set by terrain closer than 1 km while the Earth is partly hidden, and at Site23 and
  Site42 by terrain closer than 100 m. The same shift moves Earth visibility by about ±1 pp and the longest Earth
  gap by about ±6 h there.
- **±0.2° is a lower bound where terrain is closer than 100 m.** It is Barker's median height error (0.37 m) seen
  from 100 m. The same error is 0.4° from 50 m and 0.7° from 30 m. At Site23 the horizon is set by terrain closer
  than 100 m at 61% of azimuths. The height columns show the scale directly: one metre more moves Site23's 2028
  illumination from 52.0% to 73.7% and its Earth visibility from 51.5% to 59.6%; Site06 goes from 61.2% to 87.8%
  between 2 m and 5 m.
- **So at 1–2 m the Mazarico points and Site04 depend on terrain within tens of metres,** for the Sun and the
  Earth, and the uniform shift understates their uncertainty.
- Barker's height errors (median RMS 0.30–0.50 m) are published for the RoIs at Sites 1, 4, 7 and 11, not for
  Site06, 20, 23 and 42.

### 6.7 The other curated sites against published numbers

`scripts/validation_c3.py`, stages `roisites`, `roifull`, `mazarico` and `maz20`; checked by
`tests/engine/test_validation_c3.py`. Tolerances were fixed before the runs.

**Barker et al. (2021) RoIs at Site04, 07 and 11.** Every 5th pixel of every RoI, plus the largest RoI's
centroid, at 1 m over 2024–2025: the same quantities, grid and hourly sampling as at Site01 (section 6.2).

- **RoI definition** (pixels averaging > 70%; tolerance 0.5 pp, as Site01's contour test).
  - Site04: 139 pixels, 70.02–83.93%. **Pass.**
  - Site11: 194 pixels, 70.01–81.73%. **Pass.**
  - Site07: 163 pixels, 69.03–82.70%. **Miss.** One pixel, inside RoI 2, is at 69.03%, 0.97 pp below 70%;
    the other 162 pass.
  - **What the Site07 miss means.** The pixel is enclosed by RoI 2's outline, at least 3 pixels from it in every
    direction, and its eight neighbours average 70.09–74.23% (G2 review). Barker's RoI is a connected set of
    pixels above 70%, and its outline is the set's outer boundary, so the outline can enclose a pixel below 70%.
    Site01's RoI 2 outline encloses 304 pixels where Table 2 gives 302 (section 1.4). Requiring every enclosed
    pixel to be above 70% is therefore stronger than Barker's definition. The one enclosed pixel at 69.03% is
    not evidence against the engine.
  - **What a pass means.** The sample is every 5th pixel (20% of each RoI, spread evenly). A pass shows that no
    sampled pixel fails, not that every pixel passes.
- **Values read from figures** (Barker et al. 2021, Appendix A. Supplementary data, Figs. S9, S14, S19: the
  nominal-DEM RoI averages, open circles). The circles were digitised from 400 dpi renders against the
  gridlines, to about ±0.15 pp, ±0.6 d and ±0.08 d. Ours are averages over the sampled pixels of each RoI;
  their sampling standard errors (from the pixels' spread) are 0.16–0.87 pp, up to 9.2 d (LCIP) and up to
  0.77 d (LCSP), larger than the reading precision. This is an approximate check, with no tolerance.

  | Site, RoI | Average illumination, ours / figure | LCIP (d), ours / figure | LCSP (d), ours / figure |
  |---|---|---|---|
  | Site04, 1 | 75.1 / 74.7 | 82.9 / 82.8 | 7.1 / 7.3 |
  | Site04, 2 | 72.0 / 72.1 | 110.8 / 112.9 | 10.1 / 10.1 |
  | Site04, 3 | 75.7 / 74.5 | 120.3 / 104.8 | 11.2 / 11.7 |
  | Site04, 4 | 77.1 / 76.6 | 158.2 / 154.8 | 10.4 / 10.7 |
  | Site07, 1 | 73.0 / 72.9 | 166.8 / 165.0 | 15.0 / 15.0 |
  | Site07, 2 | 74.9 / 74.8 | 148.2 / 147.9 | 14.1 / 14.0 |
  | Site11, 1 | 76.7 / 76.5 | 144.0 / 144.9 | 12.6 / 12.9 |
  | Site11, 2 | 71.3 / 71.4 | 146.5 / 146.4 | 15.1 / 15.2 |
  | Site11, 3 | 71.9 / 71.9 | 146.3 / 146.4 | 9.5 / 9.6 |
  | Site11, 4 | 72.4 / 72.3 | 145.4 / 145.7 | 10.0 / 10.1 |

  Average illumination agrees to within 0.6 pp at 9 of the 10 RoIs (Site04 RoI 3: +1.2 pp). LCSP agrees to
  within 0.5 d at all 10, and LCIP to within 3.5 d at 9 (Site04 RoI 3: +15.5 d).
  - **Site04 RoI 3, every pixel** (stage `roifull`, 126 pixels): 74.73%, 104.7 d and 11.59 d, against the
    figure's 74.5%, 104.8 d and 11.68 d. The sampled outlier was sampling scatter: the sampled averages were 1.4
    (illumination) and 1.7 (LCIP) standard errors from the full ones.
- **Barker's text** gives an LCIP of "~150–175 days" at 5 m for the sites other than Site01. At the three
  largest-RoI centroids we get 147 d (Site04), 174 d (Site07) and 146 d (Site11).

**Mazarico et al. (2011) Table 3 at all eight sites.** Their average illumination (mean visible solar-disc
area) and visibility (share of time steps with any part visible) at the surface and at 10 m.
- **Setup:** the Table 3 coordinates (ranks 1, 4, 6, 7, 11, 20, 23, 42), 1970-01-01 plus four 18.6-year cycles,
  6 h steps, on the 240 m map only (their resolution), with the disc as a geometric area.
- **Two settings.** The primary comparison uses a first ray sample at 240 m and a 0.5° azimuth step, to match
  Mazarico's method, which takes the horizon from the other grid elements along 720 lines. The engine's own
  setting (first sample at 1 m, 0.1° step) is also reported.
- **Matched and not matched.** Matched, from the paper (sections 2.2 and 3.3): 720 azimuths, the horizon taken
  as a straight segment between neighbouring azimuths, the Sun as a disc with its visible area fraction, the
  period and step, and visibility as "any part". The first ray sample at 240 m is an assumption: the paper says
  only that the node spacing "increases radially". Not matched:
  - their map is a polar gnomonic 240 m grid from data to January 2010, 37.2% of its pixels filled (Mazarico
    et al. 2011, section 2 and Fig. 1); ours is the 2023 adjusted stereographic map (product 90);
  - their lunar orientation is Seidelmann et al. (2007), ours the DE421 mean-Earth frame;
  - their points are grid elements, published rounded to 0.01°; ours are the rounded coordinates, 42–137 m from
    the nearest of our pixel centres (G2 review).
- **One-sided by construction.** Table 3 lists the 50 highest values of their map, so a recomputation near those
  points is expected to come out lower. All 16 matched-setting differences in average illumination are negative.
- **Tolerance:** for each setting, the mean |change| when every point moves half a pixel (120 m) in the four
  map directions. A setting passes if the mean |difference| over the eight points is within it.
- **Result: every comparison misses its tolerance.**

  | Setting, height, quantity | Tolerance | Mean \|difference\| (8 points) | Without rank 20 (diagnostic) |
  |---|---|---|---|
  | Matched, 0 m, average illumination | 8.6 pp | 14.4 pp | 8.2 pp |
  | Matched, 0 m, visibility | 8.6 pp | 12.8 pp | 6.5 pp |
  | Matched, 10 m, average illumination | 2.9 pp | 5.3 pp | **0.65 pp** (max 1.4) |
  | Matched, 10 m, visibility | 2.4 pp | 4.4 pp | **0.15 pp** (max 0.4) |
  | Engine setting, 0 m, average illumination | 2.9 pp | 45.1 pp | 43.2 pp |
  | Engine setting, 10 m, average illumination | 3.9 pp | 5.4 pp | 0.80 pp |

- **Rank 20 (Site20).** On our 240 m map, its published coordinate lies on the flank of the Leibnitz beta
  plateau: the horizon rises to +5.7° within 0.3–0.5 km to the north and west. We get 24.6% at the surface and
  45.6% at 10 m, against 82.2% and 83.3%. Moving the point 120 m in any map direction gives 21–33% at the surface.
  - **The nearest well-lit ground is outside the rounding.** A coordinate rounded to 0.01° is uncertain by
    ±152 m in latitude and ±12 m in longitude here. With the matched setting at the 49 pixel centres of our
    240 m map within ±720 m (stage `maz20`), the nearest above 65% at the surface is 402 m away and the brightest,
    72.7%, is 650 m away. None reaches Table 3's 82.2%.
  - **Table 3's rank 38** (31.81°E, 85.42°S) is a second point in this cluster, 360 m to the north-north-east,
    at 80.2% (surface) and 82.2% (10 m). With the matched setting we get 57.9% and 77.3% there.
  - **So the two maps differ here.** On Mazarico's 2010 map both points of the cluster were above 80% at the
    surface; on ours neither is, and nothing within 720 m is. Section 1.4.1 records how Site20's served point
    was then chosen.
- **At 10 m the other seven points agree closely:** average illumination within 1.4 pp and visibility within
  0.4 pp with the matched setting.
- **At the surface the differences remain** (ours lower by 6–8 pp on average, up to 17 pp, with the matched
  setting). At 0 m the horizon depends on the terrain closest to the observer, where the two methods differ
  most. With the engine's own setting a 0 m observer on a 240 m surface is shadowed by its own pixel's slope
  (section 6.3), which is why that setting is lower still.
- **Consequence for the four served Mazarico points**, which are the published coordinates (section 1.4). On
  the 5 m maps over 2028 their mean visible disc fraction (Table 3's quantity) is 41.2% at 1 m and 87.5% at 10 m
  (Site06), 45.1% and 82.4% (Site23), 44.1% and 77.9% (Site42), and 13.7% and 30.3% (Site20); the time with any
  part of the Sun visible is 46.6%, 52.0%, 47.9% and 17.2% at 1 m. So at 1–2 m none of the four represents the
  well-lit ground Table 3 describes; Site06, 23 and 42 reach Table 3's level at 5–10 m, Site20 at no height.
  Rank 38, on the same maps, gives 33.4% at 1 m and 75.4% at 10 m.

## References

- Allen, C. W. (1973). *Astrophysical Quantities*, 3rd edition. Athlone Press, London. §81, p. 171.
- Barker, M. K., et al. (2021). Improved LOLA elevation maps for south pole landing sites: Error estimates and
  their impact on illumination conditions. *Planetary and Space Science* 203, 105119. doi:10.1016/j.pss.2020.105119
- Barker, M. K., et al. (2021), Appendix A. Supplementary data (Figs. S1–S19: Sites 4, 7 and 11). Same article,
  doi:10.1016/j.pss.2020.105119
- Barker, M. K., et al. (2023). A New View of the Lunar South Pole from the Lunar Orbiter Laser Altimeter (LOLA).
  *Planetary Science Journal* 4(9), 183. doi:10.3847/PSJ/acf3e1
- Gläser, P., et al. (2018). Illumination conditions at the lunar poles: Implications for future exploration.
  *Planetary and Space Science* 162, 170–178. doi:10.1016/j.pss.2017.07.006
- Mazarico, E., et al. (2011). Illumination conditions of the lunar polar regions using LOLA topography.
  *Icarus* 211, 1066–1081. doi:10.1016/j.icarus.2010.10.030
- Mazarico, E., Barker, M. K., & Nicholas, J. B. (2018). Advanced illumination modeling for data analysis and
  calibration. Application to the Moon. *Advances in Space Research* 62(11), 3214–3228.
  doi:10.1016/j.asr.2018.08.022
- McClernan, M. T. (2024). Down Selected Artemis III Candidate Landing Site Navigational Grids. U.S. Geological
  Survey data release. doi:10.5066/P1MEQ6UK (section 1.4.3)
- NASA (2024). NASA Provides Update on Artemis III Moon Landing Regions. Release 24-136, 28 October 2024.
  https://www.nasa.gov/news-release/nasa-provides-update-on-artemis-iii-moon-landing-regions/ (section 1.4.3)
- NASA (2026). NASA Adds Mission to Artemis Lunar Program, Updates Architecture. Release 26-022, 27 February
  2026. https://www.nasa.gov/news-release/nasa-adds-mission-to-artemis-lunar-program-updates-architecture/
  (section 1.4.3)
- Neumann, G. A. (2010). Lunar Orbiter Laser Altimeter Raw Data Set, LRO-L-LOLA-4-GDR-V1.0. NASA Planetary
  Data System. PDS4 bundle: Smith, D. E., & Neumann, G. A. (2023). Lunar Reconnaissance Orbiter LOLA Processed
  Data (RDR) Bundle. doi:10.17189/tnyt-7007 (`LDEM_75S_60M`, section 6.3)
- Giorgini, J. D., et al. (1996). JPL's On-Line Solar System Data Service. *Bulletin of the American
  Astronomical Society* 28(3), 1158.
- JPL Solar System Dynamics: Horizons On-Line Ephemeris System, https://ssd.jpl.nasa.gov/horizons/, queried
  through its API (https://ssd.jpl.nasa.gov/api/horizons.api) on 2026-11-15 (section 6.1).
- Folkner, W. M., Williams, J. G., & Boggs, D. H. (2008). The Planetary and Lunar Ephemeris DE 421. JPL IOM
  343R-08-003.
