<!-- SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage". -->
# Glossary

The terms this project uses, in alphabetical order. Each entry has a plain-language sentence first, then a
precise one for specialists (*Detail*), then a link to the [methodology](methodology.md) section that uses the
term, where there is one. Field names such as `illumination_fraction` are the API's
(`lss/contract/models.py`). Sources are listed in [references.md](references.md).

[A](#azimuth) · [C](#clipped-period) · [D](#de-gerlache-rim) · [E](#earth-clearance) ·
[F](#far-field-and-near-field) · [G](#geotiff) · [I](#illumination-fraction) · [L](#lcip-and-lcsp) ·
[M](#m3-moon-mineralogy-mapper) · [N](#naif) · [P](#pds-planetary-data-system) · [R](#reference-sphere) ·
[S](#scenario-and-window) · [T](#tdb-and-utc) · [U](#unit-height) · [V](#visible-fraction-f_sun-f_earth) ·
[W](#window)

---

### Azimuth

The compass direction of something in the sky, measured clockwise from north: 0° north, 90° east, 180° south,
270° west.
*Detail:* 0–360°, clockwise from north in the site's [ENU](#enu-east-north-up) frame. At an exact pole every
horizontal direction points away from the pole, so the requested longitude defines which direction is called
north. The `sun_azimuth_deg` statistic reports the smallest arc containing the track, and no mean.
[Methodology §2](methodology.md#2-frames-time-scales-and-topocentric-geometry),
[§5.3](methodology.md#53-power-f3-powermetrics).

### Clipped period

A sunlit, shadow or Earth-gap period that was already under way when the time window opened, or was still
going on when it closed, so only part of it is counted.
*Detail:* periods are cut at `window_start` and `window_end` and counted with their clipped length.
`longest_shadow_clipped` and `longest_earth_gap_clipped` are true when the longest period was cut, in which
case its full length is longer than reported. The UI says "clipped to the window; the full period is longer".
[Methodology §5.2](methodology.md#52-visibility-periods-and-clipping).

### COG (cloud-optimized GeoTIFF)

A map file arranged so a program can download just the part it needs instead of the whole file.
*Detail:* a tiled [GeoTIFF](#geotiff) laid out for partial (windowed) reads over HTTP. The PGDA product 90 maps
are COGs; the engine reads windows of them remotely (registry `pgda_90_south_pole_dems`).

### Compare filter and rank

Ways to narrow down and sort a comparison of several scenarios: keep only those that meet a condition (for
example "at least 60% illumination"), then put them in order by one value.
*Detail:* in `POST /api/compare` (contract 0.10.0), "optional filters and a rank are applied by the API to the
served results, never by the LLM". A filter (`MetricFilter`) keeps "a scenario only if `metric op value`
holds. A null value never passes (it is listed as not computed)." The rank (`CompareRank`) orders "the passing
scenarios by `metric`; equal values keep their request order and are reported in `CompareResponse.rank_ties`";
its `limit` keeps "the first `limit`; the rest are counted". If every served scenario fails the filters, the
result is empty: an answer ("none qualifies"), not an error. `across` adds "one scenario per curated site,
expanded by the API [...]: the sites named, the sites tagged with `region`, or every curated site if neither is
given" (see [Region tag](#region-tag)). In the app these appear through the question box's answers.

### Connecting Ridge

See [Curated sites](#curated-sites).

### Curated sites

The places listed on the globe: south-pole landing-site candidates chosen from published studies, and the
Apollo landing sites. Each south-pole site has one exact point where the tool computes its results (its
[served point](#served-point)).
*Detail:* from the registry's site list (`lss/registry/sites.yaml`), served by `/api/sites`. The UI names each
site by its short name, with a subtitle: for a south-pole site, its [PGDA site
number](#pgda-site-numbers-site01--site42) and where its point comes from; for an Apollo site, the place and
landing date.

**South-pole sites:**

| Short name | PGDA site | Served point | Lat, lon (°) |
|---|---|---|---|
| Connecting Ridge | Site01 | Centroid of Barker et al. (2021) RoI 4 (largest of 7) | −89.452675, −137.148653 |
| Shackleton Rim | Site04 | Centroid of RoI 1 (largest of 4) | −89.761966, −157.067197 |
| Peak near Shackleton | Site07 | Centroid of RoI 2 (largest of 2) | −88.807326, 123.776844 |
| de Gerlache Rim | Site11 | Centroid of RoI 1 (largest of 4) | −88.668256, −68.375764 |
| Nobile Rim | Site06 | Mazarico et al. (2011) Table 3, rank 6 | −85.30, 37.07 |
| Leibnitz Beta Plateau | Site20 | Mazarico et al. (2011) Table 3, rank 20 | −85.43, 31.73 |
| Malapert Massif | Site23 | Mazarico et al. (2011) Table 3, rank 23 | −85.97, −2.30 |
| de Gerlache–Kocher Massif | Site42 | Mazarico et al. (2011) Table 3, rank 42 | −85.83, −116.35 |

**Apollo landing sites:** each point is the Lunar Module's descent stage, "which is still on the surface, as
located in Lunar Reconnaissance Orbiter camera images (Wagner et al. 2017)", in the mean Earth / DE421 frame the
engine uses. Their terrain is the [global coarse layer](#global-coarse-layer-low-fidelity) (methodology §1.4.2),
and they have no slope statistics, which are measured only on the polar maps (§5.6). This version has no
precomputed results for them.

| Short name | Subtitle | Lat, lon (°) |
|---|---|---|
| Apollo 11 | Mare Tranquillitatis · 20 July 1969 | 0.67416, 23.47314 |
| Apollo 12 | Oceanus Procellarum · 19 November 1969 | −3.0128, −23.4219 |
| Apollo 14 | Fra Mauro · 5 February 1971 | −3.64589, −17.47194 |
| Apollo 15 | Hadley Rille / Apennines · 30 July 1971 | 26.13239, 3.6333 |
| Apollo 16 | Descartes · 21 April 1972 | −8.9734, 15.5011 |
| Apollo 17 | Taurus-Littrow · 11 December 1972 | 20.1911, 30.7723 |

Connecting Ridge is the ridge connecting the rims of Shackleton and de Gerlache craters. The four south-pole
points at the Mazarico et al. coordinates lie on slopes of 6.6–8.0° on the 5 m maps, steeper than the RoI points
(1.1–5.1°), because those coordinates were picked on a 240 m map.
[Methodology §1.4](methodology.md#14-curated-sites-c3), [§1.3](methodology.md#13-the-served-site-site01-at-barker-et-al-2021-roi-4).

### de Gerlache Rim

See [Curated sites](#curated-sites).

### de Gerlache–Kocher Massif

See [Curated sites](#curated-sites).

### DE421

The table of Sun, Earth and Moon positions (and of how the Moon is turned) that the tool uses, made by NASA's
Jet Propulsion Laboratory.
*Detail:* JPL planetary and lunar ephemeris DE 421 (Folkner et al. 2008), read through
[SPICE](#spice-and-kernels) kernels. Chosen because the PGDA terrain maps are in the [MOON_ME](#moon_me-and-moon_pa)
frame of DE421, so no frame alignment is needed. The lunar orientation kernel limits the supported span to
2050-12-31 23:58:50 UTC; the planetary ephemeris covers 1899-07-29 to 2053-10-09 TDB.
[Methodology §1.1](methodology.md#11-ephemeris-and-frames-naif-spice-de421-era).

### DEM (digital elevation model)

A map of ground height, stored as a grid of numbers.
*Detail:* the PGDA grids used here are [polar stereographic](#polar-stereographic), float32 heights in metres
above the 1737.4 km [reference sphere](#reference-sphere), NaN for no data. Heights between pixel centres are
interpolated bilinearly. See also [LDEM](#ldem).
[Methodology §1.2](methodology.md#12-terrain-nasa-gsfc-pgda-lola).

### DEM clones

One hundred alternative versions of a site's height map, each with a different random set of plausible height
errors added, so scientists can see how much the results could change.
*Detail:* made by Barker et al. (2021) for the PGDA product 78 sites. Each clone adds one random realization
of the estimated orbital and interpolation errors to the map; together they form an ensemble with about the
same error properties as the data. Barker et al. report results over the clones as percentiles (Table 2),
which this project uses as a validation bound. The tool does not yet compute results on the clones.
[Methodology §4.1](methodology.md#41-barker-et-al-2021-the-served-result).

### Direct-to-Earth (DTE)

A radio link straight from the lander to Earth, with no relay satellite. It needs a clear line of sight to
Earth, so the terrain must not block it.
*Detail:* the tool's communications metrics (`CommsMetrics`, shown under "Comms (direct to Earth)") measure
when any part, or all, of the Earth disc is above the [terrain horizon](#terrain-horizon), and by how much
([Earth clearance](#earth-clearance)).
[Methodology §5.4](methodology.md#54-communications-f4-commsmetrics).

### Diviner

An instrument on NASA's [LRO](#lro-lunar-reconnaissance-orbiter) that measures the temperature of the Moon's
surface.
*Detail:* the Diviner Lunar Radiometer Experiment. The registry lists its polar temperature products,
poleward of 80° (registry `diviner_polar_temperature`, Williams et al. 2019), as planned, not yet used. The
registry's "cannot answer" entries for Diviner are what the tool cites when it explains which temperature
questions it can't answer: no product is integrated equatorward of 80°, and spacecraft heating needs a
thermal model.

### Downsampled series

The plotted curves have been thinned out so they draw quickly; the numbers in the dashboard are not affected.
*Detail:* `downsampled: true` on a series response means the plotted series is thinned for display. Metrics
and events are computed on the engine's internal 60 s grid, independent of the returned series.
[Methodology §5.5](methodology.md#55-computation-and-accuracy-lssseries-lssmetrics).

### Earth clearance

How far above (or below) the surrounding terrain the centre of Earth appears, in degrees.
*Detail:* `earth_clearance_deg` = Earth disc centre elevation minus the terrain horizon elevation at the same
azimuth; positive means the centre is above the terrain. Reported as min, max and time mean over the window.
The series carries it per sample as `clearance_deg`.
[Methodology §5.4](methodology.md#54-communications-f4-commsmetrics).

### Earth gap

A stretch of time when Earth is completely hidden behind terrain (or below the horizon), so a direct link is
impossible.
*Detail:* a period with no part of the Earth disc visible (`f_earth = 0`); no minimum duration; clipped to the
window. `longest_earth_gap_h` is the longest one. As the methodology puts it: "Periods are found
on the 60 s internal grid [...], so a period shorter than 60 s can be missed if it starts and ends
between two grid points; one that contains a grid point is found and refined."
[Methodology §5.2](methodology.md#52-visibility-periods-and-clipping).

### Earthrise and Earthset

The moment Earth starts to appear above the terrain, and the moment it disappears behind it.
*Detail:* Earthrise = the first part of the Earth disc coming above the terrain horizon; Earthset = the last
visible part going below it. Event times are [refined](#refined-event) to 0.5 s.
[Methodology §5.4](methodology.md#54-communications-f4-commsmetrics),
[§5.5](methodology.md#55-computation-and-accuracy-lssseries-lssmetrics).

### Elevation

How high something appears in the sky, as an angle above the flat "level" direction at the site.
*Detail:* the apparent elevation of a disc centre above the [local horizontal plane](#local-horizontal-plane)
(astronomical elevation), not above the terrain; there is no refraction (no atmosphere). Not to be confused
with terrain height, which this project calls height (the DEM's "elevation" layer).
[Methodology §2](methodology.md#2-frames-time-scales-and-topocentric-geometry).

### ENU (east-north-up)

The local set of directions at a site: east, north and straight up.
*Detail:* the topocentric frame built from the normal to the 1737.4 km reference sphere at the site, in
MOON_ME_DE421. The horizon profile and the Sun and Earth tracks use the same frame, so they can be overlaid
directly.
[Methodology §2](methodology.md#2-frames-time-scales-and-topocentric-geometry),
[§5](methodology.md#5-metric-definitions).

### Far field and near field

Nearby terrain is mapped in fine detail; distant terrain uses coarser maps, because far away only the large
shapes affect the skyline.
*Detail:* near field = the finest layer close to the site (PGDA product 78, 5 m, out to 5 km at Site01); far
field = PGDA product 90 maps (80 m out to 100 km, 240 m out to 400 km). Transition distances and the maximum
range were set by a convergence test. The UI shows the near-field and far-field resolutions.
[Methodology §1.2](methodology.md#12-terrain-nasa-gsfc-pgda-lola),
[§3.2](methodology.md#32-numerical-settings-and-convergence).

### Fidelity label

A short tag telling you how detailed the terrain behind a result is: high, medium or low.
*Detail:* `FidelityLabel` = a tier and a summary such as "5 m polar DEM near field". The tier is high when the
near field is 5 m or finer and a far field is present, medium when the near field is 80 m or finer, low
otherwise (`lss/registry/terrain.py`). Locations on the [global coarse layer](#global-coarse-layer-low-fidelity)
are "low" (methodology §3.5).

### GeoTIFF

A common image file format for maps that also stores where on the body the map lies and how it is projected.
*Detail:* all PGDA terrain grids used here are GeoTIFFs (see also [COG](#cog-cloud-optimized-geotiff)); the
projection and no-data value were checked from their headers.
[Methodology §1.2](methodology.md#12-terrain-nasa-gsfc-pgda-lola).

### Global coarse layer (low fidelity)

A coarser height map that covers the whole Moon, used for places outside the detailed south-pole maps, such as
the Apollo sites. Results that use it carry the fidelity label "low".
*Detail:* LOLA `LDEM_128` (registry `lola_ldem_128`): "simple cylindrical, 128 pixels per degree (236.901 m
along a meridian)", in the polar maps' frame and on their reference sphere, "so no alignment is applied". It is
used "only where no polar layer covers the location, as the single layer of the stack, from the observer to the
400 km maximum range. Every location the polar maps cover keeps exactly the stack it had before (tested at all
eight polar sites), so their results are unchanged. The fidelity tier is "low": the resolver gives "low" when the
near field is coarser than 80 m." Checks of frame and datum: against Wagner et al. (2017)'s radii of the six
Apollo descent stages, "LDEM_128 minus Wagner is −8.6, −2.1, +0.1, +6.1, +2.0 and −2.5 m"; against the PGDA
240 m polar map at 12 points from 61° S to 86° S, "mean difference 0.9 m, mean |difference| 2.8 m, maximum
7.0 m". See [simple cylindrical](#simple-cylindrical).
[Methodology §3.5](methodology.md#35-global-coarse-layer-c7-horizons-off-the-polar-maps).

### Illumination fraction

The share of the time window during which at least some of the Sun is visible from the site.
*Detail:* `illumination_fraction` = sunlit time in the window divided by its length, where sunlit means any
part of the solar disc above the terrain horizon (`f_sun > 0`). A partly hidden Sun counts as sunlit; how much
of it is visible is in the [mean visible disc fraction](#mean-visible-disc-fraction).
[Methodology §5.3](methodology.md#53-power-f3-powermetrics).

### LCIP and LCSP

Shorthand from the research literature for the longest stretch of continuous sunlight and the longest stretch
of continuous shadow.
*Detail:* Barker et al. (2021): longest continuous illumination period (any part of the Sun visible) and
longest continuous shadow period (none of it visible). The tool's equivalents are `longest_sunlit_period_h`
and `longest_shadow_h`.
[Methodology §4.1](methodology.md#41-barker-et-al-2021-the-served-result).

### LDEM

The file-name prefix of LOLA height maps; the terrain maps this tool reads are LDEMs.
*Detail:* LOLA-based digital elevation model. From PGDA product 90: the far-field maps `LDEM_80S_80MPP_ADJ`
(80 m) and `LDEM_60S_240MPP_ADJ` (240 m), and `LDEM_83S_10MPP_ADJ` (10 m) for the 10 km slope statistics. The
product 69 maps were made from `LDEM_85S_060M`, which is not public; the internal rerun of product 69 uses the
PDS LOLA map `LDEM_75S_60M` instead. `LDEM_128` (PDS LOLA, 128 pixels per degree) is the
[global coarse layer](#global-coarse-layer-low-fidelity) for locations off the polar maps. "MPP" is metres per
pixel; the `_ADJ` maps are the newer, orbit-adjusted product 90 maps.
[Methodology §1.2](methodology.md#12-terrain-nasa-gsfc-pgda-lola), [§3.5](methodology.md#35-global-coarse-layer-c7-horizons-off-the-polar-maps),
[§5.6](methodology.md#56-slope-lssterrainslope), [§6.3](methodology.md#63-pgda-product-69-internal-pass-never-served).

### Leap second

An extra second occasionally added to clock time (UTC) to keep it in step with Earth's rotation.
*Detail:* UTC is converted to TDB with the `naif0012` leapseconds kernel (last leap second 2016-12-31). No
leap seconds are assumed after that, which affects only the UTC labels of future instants, by whole seconds.
[Methodology §1.1](methodology.md#11-ephemeris-and-frames-naif-spice-de421-era),
[§2](methodology.md#2-frames-time-scales-and-topocentric-geometry).

### Leibnitz Beta Plateau

See [Curated sites](#curated-sites).

### Libration

The Moon's slow rocking as seen from Earth. Seen from the Moon, it means Earth does not sit still in the sky but
moves around it. At the Connecting Ridge site, Earth's elevation goes from −7.4° to +6.0° over the served
window, so near the poles libration can decide whether Earth is above the terrain or hidden behind it.
*Detail:* the combined effect of the Moon's eccentric, inclined orbit (optical libration) and small real
oscillations in its rotation (physical libration). The engine has no separate libration model: libration is
already in every Earth position, via the DE421 ephemeris (the Earth–Moon vector) and the lunar orientation
(PA DE421), because Earth's direction is computed in the Moon's body-fixed frame (MOON_ME_DE421).
[Methodology §2](methodology.md#2-frames-time-scales-and-topocentric-geometry).

### Light time and stellar aberration

Light takes time to arrive (about 8.3 minutes from the Sun), and the observer is moving, so the Sun and Earth
appear slightly displaced from where they really are at that instant. The tool uses where they appear.
*Detail:* apparent directions use the SPICE `LT+S` correction, computed by `spkcpo` for an observer fixed on
the rotating Moon, so the aberration includes the observer's velocity from lunar rotation. In the 8.3 min of
solar light time the Moon turns by about 0.08°.
[Methodology §2](methodology.md#2-frames-time-scales-and-topocentric-geometry).

### Limb darkening

The Sun's disc is not equally bright: its edge (the limb) is dimmer than its centre. So losing the edge of the
Sun behind terrain costs less light than losing the middle.
*Detail:* the visible solar fraction is weighted by Allen's (1973) 550 nm law,
I(μ)/I(1) = 0.30 + 0.93 μ − 0.23 μ²; the limb is 30% as bright as the centre. Barker et al. (2021) also use
limb darkening at 550 nm but name no law. At the served point the choice moves the time-mean fraction by
0.0002.
[Methodology §5.1](methodology.md#51-visible-fraction-of-a-disc-at-one-instant).

### Limitations

Notes that come with a result, saying what it can't tell you or what is missing from it.
*Detail:* the `limitations` lists of terrain and site-summary results. The UI shows them as "Limits of these
values:" under slope statistics and "Not in this summary:" under a site summary. For example, when a summary has
no slope part: "This version has no precomputed slope statistics for this location and radius."

### Local horizontal plane

The perfectly level plane at the observer, ignoring hills; angles in the sky are measured up from it.
*Detail:* the plane through the observer (DEM surface + unit height) normal to the 1737.4 km reference
sphere's radius at the site. The terrain horizon can lie above it (a hill) or below it (on a flat sphere, the
horizon dips below level because of curvature).
[Methodology §2](methodology.md#2-frames-time-scales-and-topocentric-geometry),
[§3.1](methodology.md#31-geometry).

### LOLA (Lunar Orbiter Laser Altimeter)

A laser instrument on NASA's [LRO](#lro-lunar-reconnaissance-orbiter) that measures the height of the Moon's
surface. All the terrain maps the tool uses come from it.
*Detail:* the PGDA products 78, 90 and 69 are built from LOLA altimetry; products 78 and 90 use LOLA tracks
adjusted to reduce orbit errors (Barker et al. 2021, 2023).
[Methodology §1.2](methodology.md#12-terrain-nasa-gsfc-pgda-lola).

### LRO (Lunar Reconnaissance Orbiter)

The NASA spacecraft orbiting the Moon that carries [LOLA](#lola-lunar-orbiter-laser-altimeter) and
[Diviner](#diviner).
*Detail:* the source mission for the terrain data used here and for several planned datasets in the registry.

### LROC and NAC

The camera on NASA's [Lunar Reconnaissance Orbiter](#lro-lunar-reconnaissance-orbiter) (LROC), and its Narrow
Angle Cameras (NAC), which take its most detailed pictures of the surface.
*Detail:* Wagner et al. (2017) located the Apollo [descent stages](#lunar-module-descent-stage) in LROC NAC
images; the positions are read from the LROC PDS archive table (LRO-L-LROC-5-RDR-V1.0,
`ANTHROPOGENIC_OBJECTS`). The Cesium Moon globe's imagery also includes LROC mosaics and NAC images of the poles
(display only). The planned boulder map (registry `aussel_2025_boulders`) is made from NAC images.

### Lunar Module descent stage

The lower half of an Apollo lander. It stayed on the Moon when the astronauts left in the upper half, so it
still marks where each mission landed.
*Detail:* each Apollo site's point is "the lunar module's descent stage, which is still on the surface, as
located in Lunar Reconnaissance Orbiter camera images (Wagner et al. 2017)", within 0.3–3.5 m depending on the
site (registry site list). See [Curated sites](#curated-sites) and [LROC and NAC](#lroc-and-nac).

### M3 (Moon Mineralogy Mapper)

An instrument on India's Chandrayaan-1 spacecraft whose data were used to find water ice exposed at the
surface near the poles.
*Detail:* a NASA imaging spectrometer flown on ISRO's Chandrayaan-1. The registry lists the surface-exposed ice
detections of Li et al. (2018), about 280 m pixels poleward of about 70°, as planned (registry
`m3_surface_ice`): a clearly labeled stand-in for "water", which cannot give ice abundance or depth, or
subsurface hydrogen at kilometre scale.

### Malapert Massif

See [Curated sites](#curated-sites).

### Mean visible disc fraction

On average over the window, how much of the Sun's light reaches the site, from 0 (none) to 1 (the whole disc
all the time).
*Detail:* `mean_visible_disk_fraction` (UI: "Mean visible solar disc") = the time average of
[`f_sun`](#visible-fraction-f_sun-f_earth) over the window. It is light-weighted (limb-darkened), not a
geometric area fraction.
[Methodology §5.3](methodology.md#53-power-f3-powermetrics).

### MOON_ME and MOON_PA

Two standard ways of fixing latitude and longitude lines to the Moon; they differ by a small, fixed rotation.
*Detail:* `MOON_PA_DE421` is the principal-axis frame of the DE421 lunar orientation; `MOON_ME_DE421` (Mean
Earth / polar axis) is a fixed rotation of it, defined by the frame kernel `moon_080317.tf`. All geometry is in
MOON_ME_DE421, the frame of the PGDA maps; `MOON_ME` is an alias for it.
[Methodology §1.1](methodology.md#11-ephemeris-and-frames-naif-spice-de421-era),
[§2](methodology.md#2-frames-time-scales-and-topocentric-geometry).

### NAIF

The group at NASA's Jet Propulsion Laboratory that makes the [SPICE](#spice-and-kernels) toolkit and
publishes the data files the tool uses for Sun, Earth and Moon geometry.
*Detail:* Navigation and Ancillary Information Facility. The kernels are downloaded from its generic-kernels
server (registry `spice_de421`).
[Methodology §1.1](methodology.md#11-ephemeris-and-frames-naif-spice-de421-era).

### Near field

See [Far field and near field](#far-field-and-near-field).

### Nobile Rim

See [Curated sites](#curated-sites).

### Nodal cycle (18.6 years)

The Moon's orbit slowly wobbles, repeating every 18.6 years, so polar lighting patterns also repeat on about
that cycle. Long-term averages are taken over one full cycle.
*Detail:* the precession period of the nodes of the lunar orbit. PGDA product 69 is "averaged over hourly
timesteps spanning 18.6 years"; its start date is not stated.
[Methodology §4.2](methodology.md#42-pgda-product-69-internal-only-reproduction-never-served).

### NSSDCA

NASA's archive for space science data and mission information, at Goddard Space Flight Center.
*Detail:* NASA Space Science Data Coordinated Archive. Its mission pages give the Apollo sites' place names and
landing dates, and its "Apollo Landing Site Coordinates" page lists the same descent-stage positions (in the
mean Earth / polar axis frame, DE421) as Wagner et al. (2017).

### PDS (Planetary Data System)

NASA's long-term archive for planetary mission data.
*Detail:* the product 69 maps are described by PDS labels, which define the quantity mapped. The PDS
Geosciences Node distributes the LOLA map `LDEM_75S_60M` used for the internal product 69 rerun, and the planned
LOLA global grid and Diviner products.
[Methodology §4.2](methodology.md#42-pgda-product-69-internal-only-reproduction-never-served).

### Peak near Shackleton

See [Curated sites](#curated-sites).

### PGDA (Planetary Geodesy Data Archive)

A NASA Goddard Space Flight Center archive of Moon and planet maps; the source of the tool's terrain data.
*Detail:* PGDA products used: 78 (5 m site DEMs), 90 (large-area south polar DEMs) and 69 (polar
illumination, for validation only). See [references.md](references.md#11-used).
[Methodology §1.2](methodology.md#12-terrain-nasa-gsfc-pgda-lola).

### PGDA site numbers (Site01 … Site42)

The numbers in site names such as "Site04" come from a 2011 ranking of the best-lit spots near the south pole.
*Detail:* the ranks in Mazarico et al. (2011, Table 3), the 50 most illuminated spots near each pole on a 240 m
map; PGDA product 78 names its 5 m site maps by them, and Barker et al. (2021) use the same numbers. A site's
subtitle says where its served point comes from: "PGDA Site04 · Barker 2021 RoI 1" is the centroid of that
Barker region of interest; "PGDA Site06 · Mazarico 2011 rank 6" is the Mazarico et al. coordinate.
[Methodology §1.4](methodology.md#14-curated-sites-c3).

### Placeholder data

Example numbers shown while a feature is being built; they are not results.
*Detail:* responses with `_placeholder: true`, such as the committed example responses ("fixtures") the web
app can run on; the UI then shows "Placeholder data, not a computed result."

### Planetocentric latitude and east-positive longitude

The coordinate system used for every location: latitude measured from the Moon's centre, longitude increasing
eastward.
*Detail:* on the 1737.4 km reference sphere, where planetocentric and "geodetic" latitude coincide. The API
takes longitude from −180° to 180°, east positive; for example 222.851347° E is −137.148653°.
[Methodology §1.3](methodology.md#13-the-served-site-site01-at-barker-et-al-2021-roi-4),
[§2](methodology.md#2-frames-time-scales-and-topocentric-geometry).

### Polar stereographic

A way of drawing the area around a pole on a flat map, as if seen from above the pole.
*Detail:* the PGDA grids are south polar stereographic, true to scale at the pole, on the 1737.4 km sphere;
positions are given as PS x, y in km. Scale grows away from the pole (1.4% too large 400 km from Site01), so
horizon rays are traced as great circles on the sphere, not as straight lines on the map.
[Methodology §1.2](methodology.md#12-terrain-nasa-gsfc-pgda-lola), [§3.1](methodology.md#31-geometry).

### Precomputed scenario

A [scenario](#scenario-and-window) whose results were worked out in advance and stored. The live app shows only
these; the site screen's "Time window" and "Unit height" choices list just the ones that exist for that site.
*Detail:* `GET /api/scenarios` returns "every precomputed scenario this API version serves", each with the
curated site it belongs to (matched on its exact location). A request for anything else gets the API's reason:
"This version has precomputed results only for the scenarios listed with this message. A request must match one
of them exactly: the same location, unit height, time window and time step." Which scenarios are served is listed
in the README's Sites section.
[Methodology §5](methodology.md#5-metric-definitions).

### PSR (permanently shadowed region)

Ground near the poles, usually in crater floors, where the Sun never shines.
*Detail:* PGDA product 69 can map PSRs (registry `pgda_69_polar_illumination`), and `psr` is a feature type
in the API contract. Not yet used for results.

### Reference sphere

The perfect sphere, 1737.4 km in radius, that heights and coordinates are measured from.
*Detail:* the same sphere the PGDA maps use. The observer sits on the sphere's radial line at radius
1737.4 km + surface height + unit height.
[Methodology §2](methodology.md#2-frames-time-scales-and-topocentric-geometry).

### Refined event

An event time (such as sunset) that was worked out precisely between the regular time samples, not just
rounded to the nearest sample.
*Detail:* sign changes of the visibility margins between 60 s grid points are refined by bisection to 0.5 s;
such events carry `refined: true`, and the UI marks them "refined".
[Methodology §5.5](methodology.md#55-computation-and-accuracy-lssseries-lssmetrics).

### Region tag

A short label that groups curated sites in the same area, so a question can mean "all the sites around
Shackleton".
*Detail:* `Site.regions`, "region tags, e.g. 'shackleton'" (contract 0.10.0), set in the registry's site list.
A comparison's `across.region` picks every site with that tag (see [Compare filter and
rank](#compare-filter-and-rank)).

### RoI (region of interest)

A small patch of ground singled out in a study; here, well-lit patches on the Site01 ridge.
*Detail:* Barker et al. (2021) define RoIs as connected pixels with average illumination above 70% at 1 m and
area above 2500 m². Site01 has seven (their Table 2). The served point is the centroid of RoI 4.
[Methodology §1.3](methodology.md#13-the-served-site-site01-at-barker-et-al-2021-roi-4).

### Scenario and window

A scenario is one question to the tool: a place, a height above the ground and a span of dates. The window is
that span of dates.
*Detail:* `Scenario` = location, `unit_height_m`, `window_start`, `window_end` (UTC) and `step`. The step sets
only the spacing of the returned series, not the accuracy of metrics or events. Results are keyed by a hash
of the scenario (the "scenario key" in the UI).
[Methodology §5](methodology.md#5-metric-definitions),
[§5.5](methodology.md#55-computation-and-accuracy-lssseries-lssmetrics).

### Served point

The exact spot within a site where the tool computes its results.
*Detail:* the rule: where the PGDA product 78 tile has Barker et al. (2021) regions of
interest, the centroid of the largest [RoI](#roi-region-of-interest); otherwise the Mazarico et al. (2011)
coordinate, checked for slope on the 5 m map. The centroid is the centre of the 5 m pixel that contains the
mean of the RoI's pixel centres; this reproduces all seven of Barker's tabulated Site01 centroids. At Site01 the
served point is not the Mazarico et al. coordinate, which lies on an 8.6° slope on the 5 m map.
[Methodology §1.4](methodology.md#14-curated-sites-c3), [§1.3](methodology.md#13-the-served-site-site01-at-barker-et-al-2021-roi-4).

### Shackleton Rim

See [Curated sites](#curated-sites).

### Shadow period and sunlit period

A shadow period is a stretch of time when none of the Sun can be seen; a sunlit period is when at least part
of it can.
*Detail:* sunlit = `f_sun > 0`, shadow = `f_sun = 0`; together they tile the window. Partial loss of the disc
is not a shadow. There is no minimum duration, and periods are clipped to the window. `shadow_count` counts
shadow periods, including clipped ones. As the methodology puts it: "Periods are found on the
60 s internal grid [...], so a period shorter than 60 s can be missed if it starts and ends between
two grid points; one that contains a grid point is found and refined."
[Methodology §5.2](methodology.md#52-visibility-periods-and-clipping).

### SI

The term the NASA Space Apps Challenge uses for AI tools ("Super Intelligence").
*Detail:* files written with SI assistance carry a header saying so; the README's "AI usage" section
describes how SI was used.

### Simple cylindrical

A map drawn as a plain grid of latitude and longitude, unlike the [polar stereographic](#polar-stereographic)
maps used near the pole.
*Detail:* the projection of the [global coarse layer](#global-coarse-layer-low-fidelity). Rays are still great
circles: "For a lat/lon grid, each sample's latitude is asin(p_z) and its east longitude atan2(p_y, p_x). The
height is bilinear in (longitude, latitude) between the four surrounding pixel centres." Pixels shrink east-west
away from the equator: "an east-west pixel is 236.9 m × cos(latitude)".
[Methodology §3.5](methodology.md#35-global-coarse-layer-c7-horizons-off-the-polar-maps).

### Site summary

One answer that gathers what the tool has for a place: its slope, its Sun and Earth metrics, and nearby
features.
*Detail:* `POST /api/site_summary` (UI: "Summary for … within …"). Its parts are the slope statistics
(`terrain`), the metrics for a scenario (`metrics`) and nearby features (`features`, not available yet in this
version). Each part is null when it was not requested or has no result, and the summary's
[limitations](#limitations) say which and why.

### Slope

How steep the ground is, in degrees from level.
*Detail:* central differences between neighbouring pixels, tan(slope) = hypot(dz/dx, dz/dy): the angle
between the local surface and the plane normal to the sphere's radius. This is the definition of Barker et al.
(2021)'s published 5 m slope maps, which the engine reproduces at Site01. Single-pixel slopes on the 5 m maps
are low confidence, because about 90% of the pixels are interpolated between LOLA tracks. (Site01's 1.4° in
methodology section 1.3 used a ±10 m baseline.) Slope is also a terrain layer in the API (`slope`).
See also [Slope at the point](#slope-at-the-point) and
[Slope statistics and slope layer](#slope-statistics-and-slope-layer).
[Methodology §5.6](methodology.md#56-slope-lssterrainslope).

### Slope at the point

How steep the ground is exactly at the chosen location.
*Detail:* `slope_at_point_deg` (UI: "At the point"): the slope of the pixel containing the location, on the
map named under "Measured on" (see [Slope statistics and slope layer](#slope-statistics-and-slope-layer)).
Single-pixel slopes on the 5 m maps are low confidence (see [Slope](#slope)).
[Methodology §5.6](methodology.md#56-slope-lssterrainslope).

### Slope statistics and slope layer

The gentlest, steepest and average slope inside a circle around the location, and which height map they were
measured on.
*Detail:* `slope_deg` (UI: "Within the radius") = min, max and mean slope over the pixels whose centres lie
within `radius_m` of the point, as ground distance (map distances are corrected for the polar stereographic
scale). `slope_layer` (UI: "Measured on") is "the DEM the slopes were measured on (its resolution sets what
they can show)". 1 km statistics are measured on the 5 m site tile and 10 km statistics on the 10 m polar map
(`LDEM_83S_10MPP_ADJ`), because the 5 m tiles reach only 6–9 km from the served points. Slopes on the 10 m map
are gentler: features smaller than about 20 m are not resolved. The maximum picks out crater walls and the
steepest single pixel, not a typical value. Both maps are polar, so the Apollo sites, on the global coarse
layer, have no slope statistics. The statistics are precomputed; the API serves them only for the
locations and radii it lists.
[Methodology §5.6](methodology.md#56-slope-lssterrainslope).

### SPICE and kernels

NASA's standard software and data files for working out where planets, moons and spacecraft are and how they
are oriented. A kernel is one of those data files.
*Detail:* the NAIF SPICE Toolkit, called through SpiceyPy. Kernels used: `de421.bsp` (positions),
`moon_pa_de421_1900-2050.bpc` (lunar orientation), `moon_080317.tf` and `moon_assoc_me.tf` (frames),
`naif0012.tls` (leap seconds), `pck00010.tpc` (body radii).
[Methodology §1.1](methodology.md#11-ephemeris-and-frames-naif-spice-de421-era).

### Sun + Earth overlap

The share of the window when the site has some sunlight and can also see Earth at the same time.
*Detail:* `sun_earth_overlap_fraction` = time in the window with any part of both discs visible, divided by
the window length.
[Methodology §5.4](methodology.md#54-communications-f4-commsmetrics).

### Sun elevation band

The share of the time window during which the Sun stands between two chosen heights in the sky, for example
between 0° and 5°.
*Detail:* methodology §5.3: "The fraction of the window with the Sun's elevation in [a, b] is taken from a time
histogram stored in each served file". The quantity is "the apparent elevation of the Sun's disc centre above
the local horizontal plane, as in `sun_elevation_deg`, with no refraction. The terrain plays no part, so a band
can include times when the Sun is hidden." The histogram holds "the seconds spent in each 0.1° bin over the
window", from the 60 s internal grid with the elevation linear between grid points. In the API it is the compare
metric `sun_elevation_band_fraction` (`SunElevationBand`; null, not computed, where a result has no histogram).
[Methodology §5.3](methodology.md#53-power-f3-powermetrics).

### Sunrise and sunset

The moment the Sun starts to appear above the terrain, and the moment the last of it disappears behind the
terrain.
*Detail:* sunrise = the first part of the solar disc coming above the terrain horizon; sunset = the last
visible part going below it. Measured against the terrain, not the level horizon. Times are
[refined](#refined-event) to 0.5 s.
[Methodology §5.3](methodology.md#53-power-f3-powermetrics),
[§5.5](methodology.md#55-computation-and-accuracy-lssseries-lssmetrics).

### TDB and UTC

UTC is ordinary clock time, the time you enter. TDB is the steady astronomical time scale used to look up the
positions of the Sun, Earth and Moon.
*Detail:* inputs are UTC; SPICE converts them to TDB (barycentric dynamical time) with the leapseconds kernel.
Requests outside the kernels' coverage are refused, not extrapolated.
[Methodology §2](methodology.md#2-frames-time-scales-and-topocentric-geometry).

### Terrain horizon

The skyline around a site: for each compass direction, how high the surrounding hills and crater rims rise
into the sky.
*Detail:* for each azimuth (every 0.1°), the largest elevation over samples along a great-circle ray out to
400 km, using the exact spherical formula (Moon curvature included) and the near/far terrain layers;
interpolated linearly between azimuths. Depends only on location and unit height, so it is computed once and
cached. The accepted horizon error is at most about 0.01° (convergence study at Site01).
[Methodology §3](methodology.md#3-horizon).

### Time to sunset and time to Earthset

How long from the start of the window until the Sun (or Earth) next disappears behind the terrain.
*Detail:* `time_to_sunset_h` / `time_to_earthset_h` = hours from `window_start` to the first sunset /
Earthset. When there is none in the window they are null and `sunset_in_window` / `earthset_in_window` is
false, and the UI says so ("no sunset in this window").
[Methodology §5.3](methodology.md#53-power-f3-powermetrics),
[§5.4](methodology.md#54-communications-f4-commsmetrics).

### Unit height

How high above the ground the observer is, in metres: for example a rover's camera, a lander's antenna or a
person's eyes.
*Detail:* `unit_height_m`, added to the DEM surface height at the site to place the observer. Must be greater
than 0 in the API. The served result uses 1 m, as Barker et al. (2021) do.
[Methodology §2](methodology.md#2-frames-time-scales-and-topocentric-geometry),
[§4.1](methodology.md#41-barker-et-al-2021-the-served-result).

### Visible fraction (f_sun, f_earth)

At a given moment, how much of the Sun's (or Earth's) disc can be seen above the terrain: 1 is all of it,
0 is none.
*Detail:* each point of the disc is visible if it is above the terrain horizon at its own azimuth.
`f_sun` is weighted by [limb darkening](#limb-darkening) (share of light); `f_earth` is the share of area.
Returned per sample as `visible_fraction`.
[Methodology §5.1](methodology.md#51-visible-fraction-of-a-disc-at-one-instant).

### Window

See [Scenario and window](#scenario-and-window).
