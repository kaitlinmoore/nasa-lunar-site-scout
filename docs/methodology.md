<!-- SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage". -->
# Methodology

_Owned by stream A (engine and science). Other streams link to this page but do not edit it._

Status: **draft, C1 thin slice in progress.** Sections marked _(to do)_ are filled in as each engine step lands.
Every convention here is also stated in the code that implements it and covered by a test.

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
- **Apparent disc sizes.** Angular radius = asin(R / distance). Sun: R = 696,000 km (`pck00010`), giving about
  0.26–0.27°. Earth: R = 6371.0 km, the volumetric mean radius of `pck00010`'s Earth ellipsoid
  (6378.1366 / 6356.7519 km), giving 0.90–1.02° (a disc of about 1.8–2.05°, the "~2° Earth disc" of the plan).
  Using a sphere for Earth instead of its ellipsoid changes the disc edge by under 0.003°.
- **Independent check.** For every test site and epoch, azimuth, elevation and range agree with SPICE's own
  constant-position az/el routine (`azlcpo`, same frame and corrections) to better than 10⁻⁶°. The comparison
  against JPL Horizons, an independent ephemeris service, is in section 6 _(to do, step 4.7)_.

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
  layer (5 m site map, then the 80 m map, then the 240 m map; section 1.2). If that layer has no data at a
  sample, the next coarser layer is used. Samples that no layer covers are counted and reported, never
  silently dropped. At Site01 there are none.

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

**Accepted:** horizon errors of at most about 0.01°, about 2% of the Sun's apparent diameter (0.53°). How such an
error carries into illumination metrics is measured with the series in step 4.7.

**Limits of this study:**
- It covers Site01 only (two points, two heights).
- Distant terrain does not set the horizon here (400 km and 800 km agree exactly; 200 km also did at these
  points). 400 km is kept because other sites can see farther terrain, and the extra range is cheap.
- C3 repeats the study for other site types.

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
- **The check is a bound, not a match.**
  - We compute the RoI 4 area average on the nominal DEM: the same quantities, averaged over every 5 m pixel in
    the RoI 4 outline, at 1 m, over Barker's period of 2024-01-01 to 2026-01-01.
  - We require it to be at least Barker's 1st percentile (Table 2, RoI 4, A rows), within a tolerance stated
    with the result _(to do, step 4.7)_.
  - For RoI 4 at z = 1 m, those values are: average illumination 69.61%, LCIP 136.49 days, and LCSP 13.27 days,
    where LCSP is a 99th percentile, so the expected direction is reversed (our value at most 13.27 days).
- **No nominal-DEM values are tabulated.**
  - Barker's Fig. 19 plots them (open circles). He notes they "tend to be better than the mean/median of the
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
| Averaging dates | **Not stated** anywhere | Assumed; the sensitivity to the start date is measured (two start dates) _(to do, step 4.7)_ |

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
The code that computes them is step 4.6 _(to do)_. The measured numbers below are preliminary: computed with a
scratch script from the step 4.3 ephemeris and the step 4.5 horizon before the 4.6 code existed, and re-measured
with it.

### 5.1 Visible fraction of a disc at one instant

- **Disc.** Centre at the apparent azimuth and elevation, angular radius asin(R / distance) (section 2).
- **Against the real horizon profile.** A point of the disc is visible if it is above the terrain horizon at
  *its own* azimuth (section 3, interpolated linearly between the 0.1° horizon azimuths, so about 5 horizon
  values span the 0.53° solar disc). Barker et al. (2021) instead cut the disc with a flat line at the
  horizon elevation found at the disc centre's azimuth. Measured at the served point, 1 m, 2024–2025
  (10 min samples): the time-mean solar fraction is the same to 0.0001 either way, but the flat cut produces
  3 shadow periods shorter than 1 h where the real profile produces 1.
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
  - **Measured effect.** At the served point, 1 m, 2024–2025: time-mean fraction 0.8234 limb-darkened vs
    0.8232 geometric. The law moves the result by 0.0002, so any gap from Barker in step 4.7 is not
    explained by the choice of law.
- **Earth: a geometric fraction.** `f_earth` is the visible share of the Earth disc's area, unweighted.
  Radius 6371.0 km (section 2).

### 5.2 Visibility, periods and clipping

- **Sunlit** = any part of the solar disc visible (`f_sun > 0`). **Shadow** = no part visible (`f_sun = 0`).
  This is product 69's convention for illumination and Barker's for LCIP/LCSP. Sunlit and shadow periods
  tile the window: every instant is in exactly one of them.
- **Partial loss of the disc is not a shadow.** It shows up only in `mean_visible_disk_fraction`.
- **No minimum duration.** Every shadow period counts, however short. At the served point over 2024–2025,
  only 1 of 49 shadow periods is shorter than 1 h (20 min), so horizon flickers do not inflate the count there.
- **Clipped to the window.** A period that starts before `window_start` or runs past `window_end` is cut at
  the window edge and still counted, with its clipped length. `longest_shadow_clipped` says whether the
  longest shadow period was cut, in which case its full length is longer than reported.
- **Earth visible** = any part of the Earth disc visible (`f_earth > 0`). An **Earth gap** = no part
  visible. Same rules: no minimum duration, clipped to the window.
- **Resolution.** Periods and events are found on a fine internal time grid and refined by root-finding
  between samples, independent of the scenario's `step`, which sets only the series returned _(grid spacing
  and refinement tolerance: step 4.6)_.

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
| `shadow_count` | Number of shadow periods in W, including clipped ones; no minimum duration. |
| `sun_elevation_deg` | Apparent elevation of the disc centre above the local horizontal plane (section 2; not the terrain horizon): min, max and time mean over all of W, whether or not the Sun is visible. |
| `sun_azimuth_deg` | Apparent azimuth of the disc centre, clockwise from north, over all of W, whether or not the Sun is visible. `min` and `max` are the ends of the smallest arc containing the track, read clockwise from `min` to `max`; when the arc crosses north, `min` > `max` (e.g. 300 → 40). A track covering the full circle reports `min` 0, `max` 360. `mean` is always null: a linear mean of azimuths depends on where 0° is put, and a circular mean is undefined for a full circle, which is what the Sun does at Site01. The series carries the full track. |
| `time_to_sunset_h` | From `window_start` to the first sunset (the last visible part of the solar disc going below the terrain horizon), h. |

The azimuth arc is found from the continuous track (unwrapped azimuth). It is a full circle if the
unwrapped azimuth spans 360° or more; otherwise its ends are the unwrapped minimum and maximum, modulo 360°.
If other bodies get azimuth statistics, the same rule applies.

### 5.4 Communications (F4): `CommsMetrics`

| Field | Definition |
|---|---|
| `earth_visibility_fraction` | Time in W with any part of the Earth disc visible, divided by T. |
| `earth_full_disc_fraction` | Time in W with the whole Earth disc above the terrain horizon (`f_earth = 1`), divided by T. |
| `longest_earth_gap_h` | Longest continuous period with no part of the Earth disc visible, clipped to W, h. |
| `earth_elevation_deg` | Apparent elevation of the Earth's disc centre above the local horizontal plane: min, max and time mean over all of W, whether or not the Earth is visible. |
| `earth_clearance_deg` | Earth disc centre elevation minus the terrain horizon elevation at its azimuth: min, max and time mean over all of W. |
| `sun_earth_overlap_fraction` | Time in W with any part of both discs visible, divided by T. |
| `time_to_earthset_h` | From `window_start` to the first Earthset (the last visible part of the Earth disc going below the terrain horizon), h. |

## 6. Validation results _(to do, step 4.7)_

## References

- Allen, C. W. (1973). *Astrophysical Quantities*, 3rd edition. Athlone Press, London. §81, p. 171.
- Barker, M. K., et al. (2021). Improved LOLA elevation maps for south pole landing sites: Error estimates and
  their impact on illumination conditions. *Planetary and Space Science* 203, 105119. doi:10.1016/j.pss.2020.105119
- Barker, M. K., et al. (2023). *Planetary Science Journal* 4, 183. doi:10.3847/PSJ/acf3e1
- Gläser, P., et al. (2018). Illumination conditions at the lunar poles: Implications for future exploration.
  *Planetary and Space Science* 162. doi:10.1016/j.pss.2017.07.006
- Mazarico, E., et al. (2011). Illumination conditions of the lunar polar regions using LOLA topography.
  *Icarus* 211, 1066–1081. doi:10.1016/j.icarus.2010.10.030
- Folkner, W. M., et al. (2008). The Planetary and Lunar Ephemeris DE 421. JPL IOM 343R-08-003.
