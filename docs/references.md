<!-- SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage". -->
# References

Every external dataset, paper, book, software package and service this project uses.

- **Datasets:** the dataset registry, [`lss/registry/datasets.yaml`](../lss/registry/datasets.yaml), is the
  source of truth. This list is checked against it. Each entry gives its registry id so the two can be
  cross-checked. The API serves the registry at `GET /api/datasets`.
- **Method details:** see [`methodology.md`](methodology.md). Papers are cited here the way the methodology
  cites them.
- **Checks.** Paper DOIs were checked against Crossref. Dataset pages, data DOIs and terms were checked on the
  providers' sites. Package licenses were read from the installed package metadata. First checks were made on
  2026-11-15, and the list was re-checked against the registry, the methodology and the dependency files on
  2026-11-16. `VERIFY:` marks anything not yet checked.

## 1. Data

**NASA data used:** every dataset in 1.1 is a NASA data source.

### 1.1 Used

#### NASA GSFC PGDA product 78: High-Resolution LOLA Topography for South Pole Sites (`pgda_78_site_dems`) — NASA

- **Provider:** NASA GSFC Planetary Geodesy Data Archive (PGDA), M. K. Barker.
- **URL:** https://pgda.gsfc.nasa.gov/products/78
- **Used for:**
  - near-field terrain (5 m) for the horizons of the eight curated sites: the `*_final_adj_5mpp_surf.tif` maps
    of Site01, 04, 06, 07, 11, 20, 23 and 42; also the 1 km slope statistics around them;
  - the region-of-interest outlines `Site01_ROIs.tgz`, `Site04_ROIs.tgz`, `Site07_ROIs.tgz` and
    `Site11_ROIs.tgz`, which give the served points of those four sites and the Site01 validation area
    (methodology sections 1.3, 1.4, 6.2);
  - Barker's Site01 slope map, `Site01_final_adj_5mpp_slp.tif`, as a check of the slope calculation
    (methodology section 5.6).
  - The RoI archives are PGDA product 78 files. The paper's own supplementary material is a separate document
    of figures (section 3).
- **Cite:** Barker, M. K., Mazarico, E., Neumann, G. A., Smith, D. E., Zuber, M. T., & Head, J. W. (2021).
  Improved LOLA elevation maps for south pole landing sites: Error estimates and their impact on illumination
  conditions. *Planetary and Space Science* 203, 105119. https://doi.org/10.1016/j.pss.2020.105119
- **Terms:** NASA-produced data. The product page's Data Usage Policy asks users to cite Barker et al. (2021).
  No license is stated on the page.

#### NASA GSFC PGDA product 90: A New View of the Lunar South Pole from LOLA (`pgda_90_south_pole_dems`) — NASA

- **Provider:** NASA GSFC PGDA, M. K. Barker.
- **URL:** https://pgda.gsfc.nasa.gov/products/90. Data DOI: https://doi.org/10.60903/gsfcpgda-lola-spole
- **Used for:**
  - far-field terrain: `LDEM_80S_80MPP_ADJ` (80 m) and `LDEM_60S_240MPP_ADJ` (240 m);
  - `LDEM_83S_10MPP_ADJ` (10 m): the 10 km slope statistics around the curated sites, and a near-field cost
    test at Site01 (methodology sections 3.2, 5.6);
  - a window of `LDEM_60S_60MPP_ADJ` (60 m), only for the internal product 69 comparison.
- **Cite:** Barker, M. K., Mazarico, E., Neumann, G. A., Smith, D. E., Zuber, M. T., Head, J. W., & Sun, X.
  (2023). A New View of the Lunar South Pole from the Lunar Orbiter Laser Altimeter (LOLA). *The Planetary
  Science Journal* 4(9), 183. https://doi.org/10.3847/PSJ/acf3e1
- **Terms:** NASA-produced data. The product page's Data Usage Policy asks users to cite Barker et al. (2023).
  No license is stated on the page. The paper is open access under CC BY 4.0 (Crossref).

#### NASA GSFC PGDA product 69: Lunar Polar Illumination (`pgda_69_polar_illumination`) — NASA

- **Provider:** NASA GSFC PGDA, E. Mazarico.
- **URL:** https://pgda.gsfc.nasa.gov/products/69
- **Used for:** validation only (internal; never served): the average solar illumination and Earth visibility
  maps (2016 release, 60 m, from `LDEM_85S_060M`) and their PDS labels.
- **Cite:** Mazarico, E., Neumann, G. A., Smith, D. E., Zuber, M. T., & Torrence, M. H. (2011). Illumination
  conditions of the lunar polar regions using LOLA topography. *Icarus* 211(2), 1066–1081.
  https://doi.org/10.1016/j.icarus.2010.10.030
- **Terms:** NASA-produced data. The product page asks users to cite Mazarico et al. (2011) when using the
  LOLA illumination maps. No license is stated on the page.

#### PDS LOLA gridded polar map `LDEM_75S_60M` (no registry entry of its own) — NASA

- **Provider:** NASA LRO LOLA team (producer D. E. Smith, NASA GSFC), PDS Geosciences Node.
- **URL:** https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/polar/img/
  (`ldem_75s_60m.img` and `.lbl`; product version V2.0, created 2017-06-15, per the label).
- **Used for:** validation only: the terrain of the internal product 69 rerun, standing in for product 69's own
  terrain map, which is not public (methodology section 6.3). A ±150 km window around Site01.
- **Cite:** the data set's PDS catalog citation, as written there: Neumann, G.A., 2009 Lunar Orbiter Laser
  Altimeter Raw Data Set, LRO-L-LOLA-4-GDR-V1.0, NASA Planetary Data System, 2010. The bundle that now holds it
  has a DOI: Smith, D. E., & Neumann, G. A. (2023). Lunar Reconnaissance Orbiter LOLA Processed (RDR) Data
  Products. NASA Planetary Data System. https://doi.org/10.17189/tnyt-7007
- **Terms:** NASA PDS data (U.S. Government work).
- **Registry:** the data file catalog (`lss/datafiles.py`) files it under `pgda_69_polar_illumination`;
  the registry has no entry for it yet (requested from stream A).

#### NAIF SPICE generic kernels, DE421 era (`spice_de421`) — NASA

- **Provider:** NASA JPL Navigation and Ancillary Information Facility (NAIF).
- **URL:** https://naif.jpl.nasa.gov/pub/naif/generic_kernels/
- **Files:** `de421.bsp`, `moon_pa_de421_1900-2050.bpc`, `moon_080317.tf`, `moon_assoc_me.tf`, `naif0012.tls`,
  `pck00010.tpc`.
- **Used for:** Sun and Earth positions, lunar orientation (`MOON_ME_DE421`), time scales and body radii.
- **Cite (ephemeris):** Folkner, W. M., Williams, J. G., & Boggs, D. H. (2008). The Planetary and Lunar Ephemeris
  DE 421. JPL Interoffice Memorandum IOM 343R-08-003, 31 March 2008. Copy served by NAIF:
  https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/a_old_versions/de421_announcement.pdf
- **Cite (SPICE):** the two references NAIF asks users to cite (https://naif.jpl.nasa.gov/naif/credit.html):
  - Acton, C. H. (1996). Ancillary data services of NASA's Navigation and Ancillary Information Facility.
    *Planetary and Space Science* 44(1), 65–70. https://doi.org/10.1016/0032-0633(95)00107-7
  - Acton, C., Bachman, N., Semenov, B., & Wright, E. (2018). A look towards the future in the handling of
    space science mission geometry. *Planetary and Space Science* 150, 9–12.
    https://doi.org/10.1016/j.pss.2017.02.013
- **Terms:** per NAIF's rules (https://naif.jpl.nasa.gov/naif/rules.html), kernels on the NAIF server "may be
  downloaded and used by anyone", and unmodified kernels may be redistributed. This project uses them
  unmodified and does not redistribute them (they are downloaded by `scripts/fetch_data.py`).

### 1.2 Planned (in the registry, not yet used)

Listed so the registry and this page stay in step. Each moves to 1.1 when its registry `status` becomes `used`.
The registry's non-dataset entry `lss_tool_capabilities` (the tool's own limits) is not listed.

| Registry id | Dataset | NASA? | Citation |
|---|---|---|---|
| `pgda_81_mosaic_5m` | South Pole LOLA 5 m/pix DEM mosaic, 87–90 S (PGDA product 81) | NASA | Barker et al. (2021), above. The product page asks for this citation. |
| `pgda_98_polar_roughness` | Large-Scale Roughness Properties of the Lunar Poles (PGDA product 98) | NASA | Barker, M. K., Mazarico, E., Neumann, G. A., Smith, D. E., Zuber, M. T., Head, J. W., & Sun, X. (2025). Large-scale Roughness Properties of the Lunar North and South Polar Regions as Measured by the Lunar Orbiter Laser Altimeter (LOLA). *The Planetary Science Journal* 6(4), 83. https://doi.org/10.3847/PSJ/adbc9d. Data: https://doi.org/10.60903/gsfcpgda-lola-poles |
| `lola_ldem_128` | LOLA global gridded DEM, LDEM_128 (PDS Geosciences Node) | NASA | Smith, D. E., et al. (2010). Initial observations from the Lunar Orbiter Laser Altimeter (LOLA). *Geophysical Research Letters* 37(18). https://doi.org/10.1029/2010GL043751. `VERIFY:` the article id (Crossref gives 2010GL043751; L18204 is not confirmed) and the preferred citation for LDEM_128. |
| `sldem2015` | SLDEM2015, LOLA + SELENE Terrain Camera merged DEM (PGDA product 54) | NASA (with JAXA SELENE data) | Barker, M. K., Mazarico, E., Neumann, G. A., Zuber, M. T., Haruyama, J., & Smith, D. E. (2016). A new lunar digital elevation model from the Lunar Orbiter Laser Altimeter and SELENE Terrain Camera. *Icarus* 273, 346–355. https://doi.org/10.1016/j.icarus.2015.07.039. The product page asks for this citation. |
| `diviner_polar_temperature` | LRO Diviner polar temperature products (PDS Geosciences Node) | NASA | Williams, J.-P., Greenhagen, B. T., Paige, D. A., Schorghofer, N., Sefton-Nash, E., Hayne, P. O., Lucey, P. G., Siegler, M. A., & Aye, K. M. (2019). Seasonal polar temperatures on the Moon. *JGR Planets* 124(10), 2505–2521. https://doi.org/10.1029/2019JE006028. `VERIFY:` product names. |
| `robbins_craters` | Robbins global lunar crater database (USGS Astrogeology) | No (USGS) | Robbins, S. J. (2019). A new global database of lunar impact craters >1–2 km: 1. Crater locations and sizes, comparisons with published databases, and global analysis. *JGR Planets* 124(4), 871–892. https://doi.org/10.1029/2018JE005592. `VERIFY:` USGS distribution terms (the USGS page refused automated access). |
| `m3_surface_ice` | M3 surface-exposed water ice detections | Data from NASA's M3 instrument on ISRO's Chandrayaan-1 | Li, S., Lucey, P. G., Milliken, R. E., Hayne, P. O., Fisher, E., Williams, J.-P., Hurley, D. M., & Elphic, R. C. (2018). Direct evidence of surface exposed water ice in the lunar polar regions. *PNAS* 115(36), 8907–8912. https://doi.org/10.1073/pnas.1802345115. The article is CC BY-NC-ND 4.0 (Crossref). `VERIFY:` terms of the supplementary data. |
| `aussel_2025_boulders` | Global lunar boulder map from LRO NAC images | No (University of Münster; LRO NAC images are NASA data) | Aussel, B., Rüsch, O., Gundlach, B., Bickel, V. T., Kruk, S., & Sefton-Nash, E. (2025). Global Lunar Boulder Map From LRO NAC Optical Images Using Deep Learning: Implications for Regolith and Protolith. *JGR Planets* 130(7), e2025JE008981. https://doi.org/10.1029/2025JE008981. Data: Aussel, B. (2025), Zenodo, v3, https://doi.org/10.5281/zenodo.15520275, CC BY 4.0. |

### 1.3 Cited for a limit, not used (registry status `dropped`)

#### Orbital neutron hydrogen maps (`orbital_neutron_hydrogen`) — NASA

- **What:** Lunar Prospector Neutron Spectrometer and LRO LEND hydrogen maps. Not integrated: the tool cites
  them to explain why it can't give hydrogen at landing-site scale. The registry's resolution note relies on
  the two Eke / Teodoro papers below.
- **URL (registry):** https://ode.rsl.wustl.edu/moon/pagehelp/Content/Missions_Instruments/LRO/LEND/Intro.htm.
  `VERIFY:` the PDS product pages for both instruments (also open in the registry).
- **Cite:**
  - Feldman, W. C., Maurice, S., Binder, A. B., Barraclough, B. L., Elphic, R. C., & Lawrence, D. J. (1998).
    Fluxes of fast and epithermal neutrons from Lunar Prospector: Evidence for water ice at the lunar poles.
    *Science* 281(5382), 1496–1500. https://doi.org/10.1126/science.281.5382.1496
  - Mitrofanov, I. G., et al. (2010). Hydrogen mapping of the lunar south pole using the LRO neutron detector
    experiment LEND. *Science* 330(6003), 483–486. https://doi.org/10.1126/science.1185696
  - Eke, V. R., Teodoro, L. F. A., & Elphic, R. C. (2009). The spatial distribution of polar hydrogen deposits
    on the Moon. *Icarus* 200(1), 12–18. https://doi.org/10.1016/j.icarus.2008.10.013 (arXiv:0810.2478)
  - Teodoro, L. F. A., Eke, V. R., Elphic, R. C., Feldman, W. C., & Lawrence, D. J. (2014). How well do we know
    the polar hydrogen distribution on the Moon? *JGR Planets* 119(3), 574–593.
    https://doi.org/10.1002/2013JE004421 (arXiv:1304.8123)
- **Terms:** NASA PDS data (U.S. Government work).

### 1.4 Services and display assets

#### Cesium Moon (Cesium ion asset 2684829)

- **What:** the 3D Moon tileset (imagery + terrain) shown on the globe. Display only: no number in the tool
  comes from it.
- **URL:** https://cesium.com/platform/cesium-ion/content/cesium-moon-terrain/
- **Sources, per the product page's Sources table:** Moon LRO LROC WAC Global Morphology Mosaic 100m; WAC
  Global Morphologic Map - 100 meters per pixel; LRO-L-LROC-5-RDR-V1.0 NAC_POLE_NORTH and NAC_POLE_SOUTH;
  lro-l-lola-3-rdr-v1 polar/jp2 (60–90° terrain); Moon LRO LOLA - SELENE Kaguya TC DEM Merge 60N60S 59m. The
  table's Attribution column gives "NASA and the USGS Astrogeology Science Center" for each.
- **Terms:** Cesium ion Terms of Service (https://cesium.com/legal/terms-of-service/), Cesium Global 3D
  Content terms (https://cesium.com/legal/cesium-global-3d-content-tos/), and the Content Usage and
  Attribution Guide (https://cesium.com/learn/ion/content-usage-and-attribution-guide/). Requires a Cesium ion
  account and access token.

#### JPL Horizons — NASA

- **What:** NASA JPL's on-line ephemeris service (a challenge starter resource). Used as the independent check
  of the engine's Sun and Earth directions: queried through its API (https://ssd.jpl.nasa.gov/api/horizons.api)
  for the Connecting Ridge served point at 25 epochs. Horizons uses DE441 and its own lunar frame, so it is
  independent of the DE421 kernels (methodology sections 2, 6.1). The responses are stored in
  `tests/engine/fixtures/horizons_site01_roi4.json`, retrieved 2026-11-15.
- **URL:** https://ssd.jpl.nasa.gov/horizons/
- **Cite:** the Horizons manual (https://ssd.jpl.nasa.gov/horizons/manual.html, "References for the Horizons
  system") asks for the system and its retrieval date, and lists the paper the methodology cites:
  - Giorgini, J. D., & JPL Solar System Dynamics Group. NASA/JPL Horizons On-Line Ephemeris System,
    https://ssd.jpl.nasa.gov/horizons/, data retrieved 2026-11-15.
  - Giorgini, J. D., Yeomans, D. K., Chamberlin, A. B., Chodas, P. W., Jacobson, R. A., Keesey, M. S.,
    Lieske, J. H., Ostro, S. J., Standish, E. M., & Wimberly, R. N. (1996). JPL's On-Line Solar System Data
    Service. *Bulletin of the American Astronomical Society* 28(3), 1158.

## 2. Credits that must be shown

| Credit | Where it must appear | Status |
|---|---|---|
| "Data provided by: NASA and the USGS Astrogeology Science Center" (Cesium Moon) | With the globe, and in this list | CesiumJS shows data attribution by default (behind a "Data attribution" link) and the app does not hide it. On-screen wording checked against this list at the G1 deploy (2026-11-15): matches. |
| Cesium ion logo | With the globe | The guide requires it to be shown prominently. CesiumJS shows it by default and the app does not hide it. |
| Citation of Barker et al. (2021), Barker et al. (2023), Mazarico et al. (2011) | Wherever results from PGDA products 78, 90 and 69 are presented | Section 1.1 |
| Citation of the PDS LOLA data set (Neumann 2010; bundle DOI 10.17189/tnyt-7007) | Wherever the product 69 rerun is presented | Section 1.1 |
| Horizons system citation with retrieval date | Wherever the Horizons comparison is presented | Section 1.4 |
| Acknowledgment of SPICE / NAIF (Acton 1996; Acton et al. 2018) | Publications and tools that use SPICE | Section 1.1 |

## 3. Papers and books

Cited by [`methodology.md`](methodology.md) (section numbers refer to it). Data citations in section 1 are
not repeated.

- Allen, C. W. (1973). *Astrophysical Quantities*, 3rd edition. Athlone Press, London (University of London).
  ISBN 0-485-11150-0. §81 "Solar limb darkening", p. 171, row λ = 0.55 µm: source of the 550 nm limb-darkening
  law (sections 4.1, 5.1).
- Barker, M. K., et al. (2021): see section 1.1. Terrain, method, published results (Table 2), the region of
  interest definition and outlines, the slope definition and slope error (sections 1.2–1.4, 3.2, 4.1, 5.1,
  5.2, 5.6, 6.2–6.4, 6.6).
- Barker, M. K., et al. (2021), Appendix A. Supplementary data: "Supplementary Online Material", figures S1–S19
  for Sites 4, 7 and 11 (LDEM close-ups, clone errors, illumination, LCIP and LCSP maps with region-of-interest
  boundaries and centroids, per-RoI box plots). Figures only, no numeric tables. Available with the article,
  https://doi.org/10.1016/j.pss.2020.105119 (the paper's Appendix A gives that link). Consulted for the
  region-of-interest checks at Site04, 07 and 11 (curated sites, methodology section 1.4); the methodology does
  not cite it yet.
- Barker, M. K., et al. (2023): see section 1.1 (section 1.2).
- Gläser, P., Oberst, J., Neumann, G. A., Mazarico, E., Speyerer, E. J., & Robinson, M. S. (2018). Illumination
  conditions at the lunar poles: Implications for future exploration. *Planetary and Space Science* 162,
  170–178. https://doi.org/10.1016/j.pss.2017.07.006 (sections 4.2, 4.3).
- Mazarico, E., et al. (2011): see section 1.1. Site numbering, the Site01 coordinate, and the Table 3
  coordinates and ranks of Site06, 20, 23 and 42 (sections 1.3, 1.4); product 69 setup and terrain-resolution
  effect (sections 4.2, 4.3).
- Mazarico, E., Barker, M. K., & Nicholas, J. B. (2018). Advanced illumination modeling for data analysis and
  calibration. Application to the Moon. *Advances in Space Research* 62(11), 3214–3228.
  https://doi.org/10.1016/j.asr.2018.08.022 (section 1.2, nested terrain grids; the methodology cites it as
  "Mazarico et al. 2018", and Barker et al. 2021 cite it as 2018b for the same approach).
- Folkner, W. M., et al. (2008): see section 1.1.
- Giorgini, J. D., et al. (1996): see section 1.4, JPL Horizons (section 6.1).

## 4. Software

Direct dependencies. Versions are the ones locked when this list was checked; the lock files `uv.lock` and
`web/package-lock.json` list every transitive dependency with its exact version.

### 4.1 Engine and API (Python, `pyproject.toml`)

| Package | Version | Used for | License | Link |
|---|---|---|---|---|
| anthropic | 2.8.0 | Claude API client (natural-language feature) | Apache-2.0 | https://github.com/anthropics/anthropic-sdk-python |
| FastAPI | 0.163.0 | REST API | MIT | https://fastapi.tiangolo.com |
| Numba | 0.68.1 | Compiled horizon ray caster | BSD-2-Clause | https://numba.pydata.org |
| NumPy | 2.5.4 | Array maths | BSD-3-Clause (with bundled MIT, Zlib, 0BSD, CC0 parts) | https://numpy.org |
| Pydantic | 2.14.3 | API contract models and JSON Schema | MIT | https://docs.pydantic.dev |
| python-dotenv | 1.2.4 | Loading `.env` settings | BSD-3-Clause | https://github.com/theskumar/python-dotenv |
| PyYAML | 6.0.3 | Reading the dataset registry | MIT | https://pyyaml.org |
| rasterio | 1.5.2 | Reading GeoTIFF / cloud-optimized GeoTIFF DEMs | BSD-3-Clause | https://rasterio.readthedocs.io |
| SpiceyPy | 8.4.0 | Python interface to the SPICE Toolkit | MIT | https://github.com/AndrewAnnex/SpiceyPy |
| Uvicorn | 0.54.0 | API server | BSD-3-Clause | https://www.uvicorn.org |
| HTTPX (dev) | 0.28.1 | API test client | BSD-3-Clause | https://www.python-httpx.org |
| pytest (dev) | 9.2.0 | Tests | MIT | https://pytest.org |
| Ruff (dev) | 0.17.5 | Lint and formatting | MIT | https://docs.astral.sh/ruff |
| uv_build (build) | 0.11.x | Package build backend | MIT OR Apache-2.0 | https://docs.astral.sh/uv |

Libraries bundled inside those packages that do the core work:

- **NAIF SPICE Toolkit (CSPICE N0067)**, bundled in SpiceyPy. NASA JPL NAIF, https://naif.jpl.nasa.gov/naif/toolkit.html.
  Cite Acton (1996) and Acton et al. (2018), section 1.1. NAIF's rules prohibit redistributing the unmodified
  Toolkit from a mirror without clearance; this project does not redistribute it (it is installed from PyPI).
  `VERIFY:` how NAIF's rules apply to the SpiceyPy wheels.
- **GDAL 3.12.2**, bundled in rasterio. https://gdal.org. MIT license. `VERIFY:` license list of the other
  libraries bundled in the rasterio wheel.

### 4.2 Web app (`web/package.json`)

| Package | Version | Used for | License | Link |
|---|---|---|---|---|
| CesiumJS (`cesium`) | 1.147.0 | 3D Moon globe | Apache-2.0 | https://cesium.com/platform/cesiumjs/ |
| React, React DOM | 19.3.1 | User interface | MIT | https://react.dev |
| TypeScript (dev) | 7.0.2 | Type checking and build | Apache-2.0 | https://www.typescriptlang.org |
| Vite (dev) | 8.3.8 | Dev server and bundler | MIT | https://vite.dev |
| @vitejs/plugin-react (dev) | 6.3.0 | React support for Vite | MIT | https://github.com/vitejs/vite-plugin-react |
| vite-plugin-static-copy (dev) | 4.1.1 | Copies Cesium's static assets into the build | MIT | https://github.com/sapphi-red/vite-plugin-static-copy |
| oxlint (dev) | 1.93.0 | Lint | MIT | https://oxc.rs |
| @types/node, @types/react, @types/react-dom (dev) | 24.19.2, 19.3.0, 19.3.0 | Type definitions | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| openapi-typescript (dev tool, run by `npm run gen:types`) | 7.13.0 | Generates TypeScript types from the API schema | MIT | https://openapi-ts.dev |

## 5. Other sources

- Cesium Community forum thread: "Cesium ion Moon terrain appears ~2.5 km higher than LOLA / SLDEM2015 DEM at
  the same lon/lat".
  https://community.cesium.com/t/cesium-ion-moon-terrain-appears-2-5-km-higher-than-lola-sldem2015-dem-at-the-same-lon-lat/46282.
  The reason globe markers are clamped to the rendered surface and no numbers come from Cesium.

## 6. SI (AI) tools

This project was built with SI assistance from Claude models (Anthropic), and its natural-language feature
calls Claude through the `anthropic` package. Which models were used, for what, and what the author changed
are in the README's [AI usage](../README.md#ai-usage) section. `VERIFY:` that section lists the models (it is
a stub as of 2026-11-15).
