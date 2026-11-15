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
on the same frame. The near/far transition distances and the maximum ray range are set in section 3 by a
convergence test, not assumed _(to do, step 4.5)_.

Site01 lies at PS (−11.31, −12.26) km, at least 7.7 km from every edge of its 5 m tile.

## 2. Frames, time scales and topocentric geometry

Implemented in `lss/ephem/core.py`; tested in `tests/engine/test_ephem.py`.

- **Frame.** All geometry is in `MOON_ME_DE421`, the Mean Earth / polar axis frame of DE421 (named explicitly in
  code; `MOON_ME` is an alias for it). It is a fixed rotation of the DE421 principal-axis frame.
- **Coordinates.** Planetocentric latitude and east-positive longitude on the 1737.4 km reference sphere, the
  same sphere the PGDA maps use. On a sphere planetocentric and "geodetic" latitude are the same.
- **Observer.** On the sphere's normal (the radial direction) at radius 1737.4 km + h, where h = DEM surface
  height at the site + the unit height. For Site01 the 5 m map gives a surface height of 1954.60 m (bilinear
  between pixel centres). The 80 m map gives 0.26 m less; the 240 m map 4.1 m less, because its pixels
  average over the ridge.
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

## 3. Horizon _(to do, step 4.5)_

## 4. Validation references

### 4.1 Barker et al. (2021): the served result

- Same terrain: the PGDA product 78 Site01 5 m map. Same unit height: **1 m** (Kaitlin's choice; Barker also
  reports 5 m).
- Barker's method: horizon from every pixel along 720 sight lines (0.5° apart); nested grids as above; 1 h
  steps from 2024-01-01 to 2026-01-01. The Sun is an extended disc with limb darkening at 550 nm. Its visible
  fraction is computed by cutting the disc horizontally at the horizon elevation found at the disc centre's azimuth.
- Barker's definitions: "average illumination" = the time-averaged visible fraction of the solar disc;
  LCIP/LCSP = longest continuous period with any / no part of the Sun visible.
- Published numbers usable for comparison: Table 2 gives, for seven regions of interest (RoIs) at Site01, the
  centroids (PS km) and the **1st/99th percentiles over 100 DEM clones**, not the nominal-DEM values. Barker
  notes that the nominal DEM tends to give *better* illumination than the clone median, so the 1st percentile
  is a lower bound for the nominal value, not a target. The RoI outlines are in `Site01_ROIs.tgz` (product 78).

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

## 5. Metric definitions _(to do, step 4.6 / C2)_

## 6. Validation results _(to do, step 4.7)_

## References

- Barker, M. K., et al. (2021). Improved LOLA elevation maps for south pole landing sites: Error estimates and
  their impact on illumination conditions. *Planetary and Space Science* 203, 105119. doi:10.1016/j.pss.2020.105119
- Barker, M. K., et al. (2023). *Planetary Science Journal* 4, 183. doi:10.3847/PSJ/acf3e1
- Gläser, P., et al. (2018). Illumination conditions at the lunar poles: Implications for future exploration.
  *Planetary and Space Science* 162. doi:10.1016/j.pss.2017.07.006
- Mazarico, E., et al. (2011). Illumination conditions of the lunar polar regions using LOLA topography.
  *Icarus* 211, 1066–1081. doi:10.1016/j.icarus.2010.10.030
- Folkner, W. M., et al. (2008). The Planetary and Lunar Ephemeris DE 421. JPL IOM 343R-08-003.
