<!-- SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage". -->
# Methodology

_Owned by stream A (engine and science). Other streams link to this page but do not edit it._

Status: **C1 thin slice complete** (signed off at G1, 2026-11-15; served result validated in section 6). Later
slices (C2 onward) add to it. Every convention here is also stated in the code that implements it and covered
by a test.

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
  layer (5 m site map, then the 80 m map, then the 240 m map; section 1.2). If that layer has no data at a
  sample, the next coarser layer is used. Samples that no layer covers are counted, never silently dropped.
  The count is stored with each cached horizon. A location where a whole azimuth has no data is rejected.
  `scripts/precompute_c1.py` refuses to write a served result whose horizon has any uncovered sample. At Site01
  there are none. Before C3 adds sites, a non-zero count will either fail the request or be carried into the
  fidelity label (to be decided).

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
  A disc point at horizontal offset x is at azimuth az + x / cos(el) (tangent plane on the sky; error below
  1e-4° for these discs). Accuracy against closed-form circular segments: better than 1e-5 (tested). Against a
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
- **Limits (polar geometry).** Two approximations hold for bodies near the horizon, as at the poles. A disc
  point's azimuth az + x / cos(el) degrades as a body nears the zenith. The azimuth arc assumes the azimuth
  moves less than 180° between 60 s samples, which also fails near the zenith. Neither matters at the served
  site, where the Sun and Earth stay within a few degrees of the horizontal. Both get a synthetic
  high-elevation test before mid-latitude sites (C7).
- **Cost.** The served scenario (30 days, both bodies) takes about 2 s with the horizon cached; two years of
  Sun-only visibility take about 35 s (development PC).

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
| Barker RoI 4 average illumination (≥ 1st percentile) | −1.0 pp | 77.46% vs 69.61% | pass |
| Barker RoI 4 LCIP (≥ 1st percentile) | −2 d | 192.2 d vs 136.49 d | pass |
| Barker RoI 4 LCSP (≤ 99th percentile) | +1 d | 10.05 d vs 13.27 d | pass |
| Barker 70% contour, two-sided: inside ≥ 70%, edge neighbours outside ≤ 70% | 0.5 pp | inside min 70.03%, outside max 70.19% | pass |
| Barker Fig. 19 nominal-DEM values (qualitative) | none | read 77.5% / 192 d / 10.1 d; ours 77.46% / 192.2 d / 10.05 d | agrees |
| Product 69, Earth, 5 × 5 pixels: mean \|difference\| | 5 pp | 3.3 pp | pass |
| Product 69, Sun, 5 × 5 pixels: mean \|difference\| | 5 pp | 8.7 pp (no bias: mean −1.7 pp); 7.56 pp without the zero pixel (diagnostic) | **miss**; inconclusive at this resolution; accepted for G1 as a stated difference (section 6.3) |
| Ridge-top: the Sun is seen only below the local horizontal | (stated) | confirmed four ways (section 6.4) | confirmed |

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
- **Limit.** This covers one site, close to the pole. Other sites are checked only against SPICE's own
  `azlcpo` with the same kernels, which tests the ENU algebra but not the frame or the ephemeris. When C3 adds
  sites, the Horizons fixture gets one far from the pole at an eastern longitude.

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
- **Barker's 70% contour, two-sided** (G1 review, finding M1). Barker drew each RoI as the connected pixels with
  average illumination above 70% (1 m, 2024–2025, nominal DEM). So the engine should put the 70% line where
  Barker's outline is: pixels inside above it, and the pixels just outside at or below it.
  - **Set-up.** Stage `barkerring` computes every 5 m pixel outside RoI 4 that touches it: 172 pixels, 114
    sharing an edge with the RoI and 58 touching only a corner. Same quantity, period and grid as the inside
    pixels.
  - **Test, fixed before the run:** inside minimum ≥ 70% − 0.5 pp, and the edge neighbours' maximum
    ≤ 70% + 0.5 pp. Edge neighbours must be at or below 70% whether Barker joined pixels by edges or by corners.
    Corner-only neighbours must be too if corners count, so they are reported but not tested.
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
  - the served result: `LSS_DATA_DIR/cache/served/c1_00010cfa5fef681c.json`, the metrics and series responses
    with their provenance, written by `scripts/precompute_c1.py`;
  - the regression fixture: `tests/engine/fixtures/site01_roi4_c1.json`, the same metrics and every 6th hourly
    sample.
- `tests/engine/test_regression_c1.py` recomputes the scenario and requires fractions to agree to 10⁻⁶, durations
  to 10⁻³ h, angles to 10⁻⁶° and event times to 1 s.
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

### 6.6 Accuracy of the served numbers

The served values are exact for the nominal 5 m map, up to the numerical errors measured in sections 3.2 and
5.5. How far they can be trusted beyond that depends on the terrain map, mostly within a few hundred metres of
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


## References

- Allen, C. W. (1973). *Astrophysical Quantities*, 3rd edition. Athlone Press, London. §81, p. 171.
- Barker, M. K., et al. (2021). Improved LOLA elevation maps for south pole landing sites: Error estimates and
  their impact on illumination conditions. *Planetary and Space Science* 203, 105119. doi:10.1016/j.pss.2020.105119
- Barker, M. K., et al. (2023). A New View of the Lunar South Pole from the Lunar Orbiter Laser Altimeter (LOLA).
  *Planetary Science Journal* 4(9), 183. doi:10.3847/PSJ/acf3e1
- Gläser, P., et al. (2018). Illumination conditions at the lunar poles: Implications for future exploration.
  *Planetary and Space Science* 162, 170–178. doi:10.1016/j.pss.2017.07.006
- Mazarico, E., et al. (2011). Illumination conditions of the lunar polar regions using LOLA topography.
  *Icarus* 211, 1066–1081. doi:10.1016/j.icarus.2010.10.030
- Mazarico, E., Barker, M. K., & Nicholas, J. B. (2018). Advanced illumination modeling for data analysis and
  calibration. Application to the Moon. *Advances in Space Research* 62(11), 3214–3228.
  doi:10.1016/j.asr.2018.08.022
- Giorgini, J. D., et al. (1996). JPL's On-Line Solar System Data Service. *Bulletin of the American
  Astronomical Society* 28(3), 1158. (JPL Horizons, https://ssd.jpl.nasa.gov/horizons/)
- Folkner, W. M., Williams, J. G., & Boggs, D. H. (2008). The Planetary and Lunar Ephemeris DE 421. JPL IOM
  343R-08-003.
