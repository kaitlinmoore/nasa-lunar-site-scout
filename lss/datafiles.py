"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Catalog of every external data file the engine reads: source URL, local path under
`LSS_DATA_DIR`, and how to check that a download is the real file.

One source of truth for both `scripts/fetch_data.py` (downloads) and the engine
(`lss.ephem`, `lss.terrain`), so local paths are never hard-coded twice.

Files are either downloaded whole (`url`) or, for very large cloud-optimized GeoTIFFs,
clipped to a square window around a point (`clip`), read remotely by window.

Coordinates for clips are south polar stereographic metres on the 1737.4 km sphere
(the PGDA grids' native projection; MOON_ME / DE421).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from lss.config import get_settings


class Group(StrEnum):
    kernels = "kernels"
    site01 = "site01"
    sites = "sites"  # the other PGDA product 78 site tiles
    farfield = "farfield"
    validation = "validation"
    global_ = "global"  # the global coarse layer (LOLA LDEM_128, 2.1 GB), for points off the polar maps


class Kind(StrEnum):
    """What the file must look like; checked on its leading bytes after download."""

    daf = "daf"  # binary SPICE kernel (SPK/PCK): starts with "DAF/"
    text_kernel = "text_kernel"  # SPICE text kernel: starts with "KPL/"
    tiff = "tiff"  # (Big)TIFF / GeoTIFF / COG
    gzip = "gzip"  # .tgz archive
    pds3_label = "pds3_label"  # detached PDS3 label (text): starts with "PDS_VERSION_ID"
    # Raw binary image with no header (e.g. a PDS3 .IMG): nothing to check in its leading bytes. Its reader
    # checks the exact byte size against the label instead (lss.terrain.global_layer).
    raw = "raw"


MAGIC: dict[Kind, tuple[bytes, ...]] = {
    Kind.daf: (b"DAF/",),
    Kind.text_kernel: (b"KPL/",),
    Kind.tiff: (b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+"),
    Kind.gzip: (b"\x1f\x8b",),
    Kind.pds3_label: (b"PDS_VERSION_ID",),
    Kind.raw: (b"",),
}


@dataclass(frozen=True)
class Clip:
    """Square window centred on (x, y) with the given half-width, all in PS metres.

    `max_nodata_fraction`: the clip fails if more of it is no-data. 0 for the fully interpolated
    LOLA polar maps, where any no-data near the pole means a failed read.

    `label_url`: set when the source is a PDS3 image with a detached label (raw integers, no magic
    bytes); the label is downloaded beside it and opened instead. `scale`: metres per stored count,
    applied when the clip is written as float32 (PDS LOLA heights are counts x 0.5 m).
    """

    x_m: float
    y_m: float
    half_width_m: float
    max_nodata_fraction: float = 0.0
    label_url: str | None = None
    scale: float = 1.0


@dataclass(frozen=True)
class DataFile:
    id: str
    group: Group
    kind: Kind
    url: str
    relpath: str  # relative to LSS_DATA_DIR
    dataset_id: str  # registry id in lss/registry/datasets.yaml
    note: str = ""
    clip: Clip | None = None

    @property
    def path(self) -> Path:
        return get_settings().data_dir / self.relpath


NAIF = "https://naif.jpl.nasa.gov/pub/naif/generic_kernels"
PGDA = "https://pgda.gsfc.nasa.gov/data"
PDS_LOLA_POLAR = (
    "https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/polar/img"
)
PDS_LOLA_CYL = (
    "https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/img"
)

# Centre of the Site01 validation clip, PS metres, rounded: within 1.2 m of Site01 (Connecting ridge,
# exact PS -11308.19, -12258.86; see lss/contract/examples.py). Kept fixed because it is part of the
# clip's identity in MANIFEST.json (changing it re-fetches the clip).
SITE01_PS = (-11309.0, -12258.0)

FILES: tuple[DataFile, ...] = (
    # --- SPICE, DE421 era (matches the DEMs' MOON_ME / DE421 frame)
    DataFile(
        "de421_spk",
        Group.kernels,
        Kind.daf,
        f"{NAIF}/spk/planets/a_old_versions/de421.bsp",
        "kernels/de421.bsp",
        "spice_de421",
        "Planetary ephemeris DE421 (NAIF moved it to a_old_versions/).",
    ),
    DataFile(
        "moon_pa_de421",
        Group.kernels,
        Kind.daf,
        f"{NAIF}/pck/moon_pa_de421_1900-2050.bpc",
        "kernels/moon_pa_de421_1900-2050.bpc",
        "spice_de421",
        "Lunar orientation (PA frame) from DE421.",
    ),
    DataFile(
        "moon_fk",
        Group.kernels,
        Kind.text_kernel,
        f"{NAIF}/fk/satellites/moon_080317.tf",
        "kernels/moon_080317.tf",
        "spice_de421",
        "Frame kernel: MOON_PA_DE421 and MOON_ME_DE421 (fixed rotation PA -> ME).",
    ),
    DataFile(
        "moon_assoc_me",
        Group.kernels,
        Kind.text_kernel,
        f"{NAIF}/fk/satellites/moon_assoc_me.tf",
        "kernels/moon_assoc_me.tf",
        "spice_de421",
        "Aliases MOON_ME -> MOON_ME_DE421.",
    ),
    DataFile(
        "naif0012",
        Group.kernels,
        Kind.text_kernel,
        f"{NAIF}/lsk/naif0012.tls",
        "kernels/naif0012.tls",
        "spice_de421",
        "Leapseconds (latest NAIF LSK; no leap second after 2016-12-31).",
    ),
    DataFile(
        "pck00010",
        Group.kernels,
        Kind.text_kernel,
        f"{NAIF}/pck/pck00010.tpc",
        "kernels/pck00010.tpc",
        "spice_de421",
        "Body radii (Sun, Earth) for apparent disc sizes. DE421-era PCK.",
    ),
    # --- Site01 near field (PGDA product 78)
    DataFile(
        "site01_dem",
        Group.site01,
        Kind.tiff,
        f"{PGDA}/LOLA_5mpp/Site01/Site01_final_adj_5mpp_surf.tif",
        "data/pgda78/Site01/Site01_final_adj_5mpp_surf.tif",
        "pgda_78_site_dems",
        "5 m/pix LDEM, 16 x 16 km tile.",
    ),
    DataFile(
        "site01_rois",
        Group.site01,
        Kind.gzip,
        f"{PGDA}/LOLA_5mpp/Site01/Site01_ROIs.tgz",
        "data/pgda78/Site01/Site01_ROIs.tgz",
        "pgda_78_site_dems",
        "Barker et al. 2021 RoI shapefiles, for the validation comparison.",
    ),
    # --- Other PGDA product 78 sites; Site06's RoI archive link is dead (2026-11-15)
    DataFile(
        "site04_dem",
        Group.sites,
        Kind.tiff,
        f"{PGDA}/LOLA_5mpp/Site04/Site04_final_adj_5mpp_surf.tif",
        "data/pgda78/Site04/Site04_final_adj_5mpp_surf.tif",
        "pgda_78_site_dems",
        "5 m/pix LDEM, Site04 (Shackleton rim).",
    ),
    DataFile(
        "site04_rois",
        Group.sites,
        Kind.gzip,
        f"{PGDA}/LOLA_5mpp/Site04/Site04_ROIs.tgz",
        "data/pgda78/Site04/Site04_ROIs.tgz",
        "pgda_78_site_dems",
        "Barker et al. 2021 RoI shapefiles: the served point is the largest RoI's centroid.",
    ),
    DataFile(
        "site07_dem",
        Group.sites,
        Kind.tiff,
        f"{PGDA}/LOLA_5mpp/Site07/Site07_final_adj_5mpp_surf.tif",
        "data/pgda78/Site07/Site07_final_adj_5mpp_surf.tif",
        "pgda_78_site_dems",
        "5 m/pix LDEM, Site07 (Peak near Shackleton).",
    ),
    DataFile(
        "site07_rois",
        Group.sites,
        Kind.gzip,
        f"{PGDA}/LOLA_5mpp/Site07/Site07_ROIs.tgz",
        "data/pgda78/Site07/Site07_ROIs.tgz",
        "pgda_78_site_dems",
        "Barker et al. 2021 RoI shapefiles: the served point is the largest RoI's centroid.",
    ),
    DataFile(
        "site11_dem",
        Group.sites,
        Kind.tiff,
        f"{PGDA}/LOLA_5mpp/Site11/Site11_final_adj_5mpp_surf.tif",
        "data/pgda78/Site11/Site11_final_adj_5mpp_surf.tif",
        "pgda_78_site_dems",
        "5 m/pix LDEM, Site11 (de Gerlache rim).",
    ),
    DataFile(
        "site11_rois",
        Group.sites,
        Kind.gzip,
        f"{PGDA}/LOLA_5mpp/Site11/Site11_ROIs.tgz",
        "data/pgda78/Site11/Site11_ROIs.tgz",
        "pgda_78_site_dems",
        "Barker et al. 2021 RoI shapefiles: the served point is the largest RoI's centroid.",
    ),
    # Mazarico et al. (2011) Table 3 sites without RoIs (the project author, 2026-11-15)
    DataFile(
        "site06_dem",
        Group.sites,
        Kind.tiff,
        f"{PGDA}/LOLA_5mpp/Site06/Site06_final_adj_5mpp_surf.tif",
        "data/pgda78/Site06/Site06_final_adj_5mpp_surf.tif",
        "pgda_78_site_dems",
        "5 m/pix LDEM, Site06 (Nobile rim 1).",
    ),
    DataFile(
        "site20_dem",
        Group.sites,
        Kind.tiff,
        f"{PGDA}/LOLA_5mpp/Site20/Site20_final_adj_5mpp_surf.tif",
        "data/pgda78/Site20/Site20_final_adj_5mpp_surf.tif",
        "pgda_78_site_dems",
        "5 m/pix LDEM, Site20 (Leibnitz beta plateau).",
    ),
    DataFile(
        "site23_dem",
        Group.sites,
        Kind.tiff,
        f"{PGDA}/LOLA_5mpp/Site23/Site23_final_adj_5mpp_surf.tif",
        "data/pgda78/Site23/Site23_final_adj_5mpp_surf.tif",
        "pgda_78_site_dems",
        "5 m/pix LDEM, Site23 (Malapert massif).",
    ),
    DataFile(
        "site42_dem",
        Group.sites,
        Kind.tiff,
        f"{PGDA}/LOLA_5mpp/Site42/Site42_final_adj_5mpp_surf.tif",
        "data/pgda78/Site42/Site42_final_adj_5mpp_surf.tif",
        "pgda_78_site_dems",
        "5 m/pix LDEM, Site42 (de Gerlache-Kocher massif).",
    ),
    # --- Far field (PGDA product 90), mirroring Barker et al. 2021's nested grids
    DataFile(
        "ldem_80s_80m",
        Group.farfield,
        Kind.tiff,
        f"{PGDA}/LOLA_20mpp/LDEM_80S_80MPP_ADJ.TIF",
        "data/pgda90/LDEM_80S_80MPP_ADJ.TIF",
        "pgda_90_south_pole_dems",
        "80 m/pix, 80-90 S (+-304 km from the pole).",
    ),
    DataFile(
        "ldem_60s_240m",
        Group.farfield,
        Kind.tiff,
        f"{PGDA}/LOLA_20mpp/LDEM_60S_240MPP_ADJ.TIF",
        "data/pgda90/LDEM_60S_240MPP_ADJ.TIF",
        "pgda_90_south_pole_dems",
        "240 m/pix, 60-90 S (+-931 km).",
    ),
    # --- Validation (internal only): PGDA product 69 maps + 60 m terrain for the like-with-like pass
    DataFile(
        "p69_sun_85s_60m",
        Group.validation,
        Kind.tiff,
        f"{PGDA}/MoonIllumination/AVGVISIB_85S_060M_201608.TIF",
        "data/pgda69/AVGVISIB_85S_060M_201608.TIF",
        "pgda_69_polar_illumination",
        "Average solar illumination, 60 m. Time fraction with any part of the disc visible (PDS label).",
    ),
    DataFile(
        "p69_earth_85s_60m",
        Group.validation,
        Kind.tiff,
        f"{PGDA}/MoonIllumination/AVGVISIB_85S_060M_201608_EARTH.TIF",
        "data/pgda69/AVGVISIB_85S_060M_201608_EARTH.TIF",
        "pgda_69_polar_illumination",
        "Average Earth visibility, 60 m. Any part of the Earth disc (PDS label).",
    ),
    DataFile(
        "ldem_60m_site01_clip",
        Group.validation,
        Kind.tiff,
        f"{PGDA}/LOLA_20mpp/LDEM_60S_60MPP_ADJ.TIF",
        "data/pgda90/clips/LDEM_60S_60MPP_ADJ_site01_150km.tif",
        "pgda_90_south_pole_dems",
        "60 m/pix terrain for the internal product 69 reproduction; +-150 km window of a 2.9 GB COG.",
        clip=Clip(*SITE01_PS, half_width_m=150_000.0),
    ),
    DataFile(
        "site01_slope",
        Group.validation,
        Kind.tiff,
        f"{PGDA}/LOLA_5mpp/Site01/Site01_final_adj_5mpp_slp.tif",
        "data/pgda78/Site01/Site01_final_adj_5mpp_slp.tif",
        "pgda_78_site_dems",
        "Barker et al. 2021 slope map (deg), 5 m: checks lss.terrain.slope (method not stated by Barker).",
    ),
    DataFile(
        "ldem_83s_10m_site01_clip",
        Group.validation,
        Kind.tiff,
        f"{PGDA}/LOLA_20mpp/LDEM_83S_10MPP_ADJ.TIF",
        "data/pgda90/clips/LDEM_83S_10MPP_ADJ_site01_20km.tif",
        "pgda_90_south_pole_dems",
        "10 m/pix near field (83-90 S), +-20 km window of a 5.1 GB COG: measures what a 10 m near field "
        "costs and loses against the 5 m site map at Site01 (the project author, 2026-11-15).",
        clip=Clip(*SITE01_PS, half_width_m=20_000.0),
    ),
    DataFile(
        "ldem_83s_10m_site04_clip",
        Group.sites,
        Kind.tiff,
        f"{PGDA}/LOLA_20mpp/LDEM_83S_10MPP_ADJ.TIF",
        "data/pgda90/clips/LDEM_83S_10MPP_ADJ_site04_12km.tif",
        "pgda_90_south_pole_dems",
        "10 m/pix, +-12 km around the Site04 served point: 10 km slope statistics "
        "(the project author, 2026-11-15).",
        clip=Clip(-2811.156, -6649.704, half_width_m=12_000.0),
    ),
    DataFile(
        "ldem_83s_10m_site07_clip",
        Group.sites,
        Kind.tiff,
        f"{PGDA}/LOLA_20mpp/LDEM_83S_10MPP_ADJ.TIF",
        "data/pgda90/clips/LDEM_83S_10MPP_ADJ_site07_12km.tif",
        "pgda_90_south_pole_dems",
        "10 m/pix, +-12 km around the Site07 served point: 10 km slope statistics "
        "(the project author, 2026-11-15).",
        clip=Clip(30063.429, -20107.659, half_width_m=12_000.0),
    ),
    DataFile(
        "ldem_83s_10m_site11_clip",
        Group.sites,
        Kind.tiff,
        f"{PGDA}/LOLA_20mpp/LDEM_83S_10MPP_ADJ.TIF",
        "data/pgda90/clips/LDEM_83S_10MPP_ADJ_site11_12km.tif",
        "pgda_90_south_pole_dems",
        "10 m/pix, +-12 km around the Site11 served point: 10 km slope statistics "
        "(the project author, 2026-11-15).",
        clip=Clip(-37541.121, 14881.646, half_width_m=12_000.0),
    ),
    DataFile(
        "ldem_83s_10m_site06_clip",
        Group.sites,
        Kind.tiff,
        f"{PGDA}/LOLA_20mpp/LDEM_83S_10MPP_ADJ.TIF",
        "data/pgda90/clips/LDEM_83S_10MPP_ADJ_site06_12km.tif",
        "pgda_90_south_pole_dems",
        "10 m/pix, +-12 km around the Site06 served point: 10 km slope statistics "
        "(the project author, 2026-11-15).",
        clip=Clip(85957.726, 113780.267, half_width_m=12_000.0),
    ),
    DataFile(
        "ldem_83s_10m_site20_clip",
        Group.sites,
        Kind.tiff,
        f"{PGDA}/LOLA_20mpp/LDEM_83S_10MPP_ADJ.TIF",
        "data/pgda90/clips/LDEM_83S_10MPP_ADJ_site20_12km.tif",
        "pgda_90_south_pole_dems",
        "10 m/pix, +-12 km around the Site20 served point: 10 km slope statistics "
        "(the project author, 2026-11-15).",
        clip=Clip(72919.046, 117927.84, half_width_m=12_000.0),
    ),
    DataFile(
        "ldem_83s_10m_site23_clip",
        Group.sites,
        Kind.tiff,
        f"{PGDA}/LOLA_20mpp/LDEM_83S_10MPP_ADJ.TIF",
        "data/pgda90/clips/LDEM_83S_10MPP_ADJ_site23_12km.tif",
        "pgda_90_south_pole_dems",
        "10 m/pix, +-12 km around the Site23 served point: 10 km slope statistics "
        "(the project author, 2026-11-15).",
        clip=Clip(-4906.252, 122155.02, half_width_m=12_000.0),
    ),
    DataFile(
        "ldem_83s_10m_site42_clip",
        Group.sites,
        Kind.tiff,
        f"{PGDA}/LOLA_20mpp/LDEM_83S_10MPP_ADJ.TIF",
        "data/pgda90/clips/LDEM_83S_10MPP_ADJ_site42_12km.tif",
        "pgda_90_south_pole_dems",
        "10 m/pix, +-12 km around the Site42 served point: 10 km slope statistics "
        "(the project author, 2026-11-15).",
        clip=Clip(-113360.357, -56149.321, half_width_m=12_000.0),
    ),
    # Artemis III regions (in the site registry): 10 m clips for their slope statistics
    DataFile(
        "ldem_83s_10m_artemis3_peak_near_cabeus_b_clip",
        Group.sites,
        Kind.tiff,
        f"{PGDA}/LOLA_20mpp/LDEM_83S_10MPP_ADJ.TIF",
        "data/pgda90/clips/LDEM_83S_10MPP_ADJ_artemis3-peak-near-cabeus-b_12km.tif",
        "pgda_90_south_pole_dems",
        "10 m/pix, +-12 km around the artemis3-peak-near-cabeus-b point (Artemis III): slope statistics.",
        clip=Clip(-179577.467, 69919.519, half_width_m=12_000.0),
    ),
    DataFile(
        "ldem_83s_10m_artemis3_haworth_clip",
        Group.sites,
        Kind.tiff,
        f"{PGDA}/LOLA_20mpp/LDEM_83S_10MPP_ADJ.TIF",
        "data/pgda90/clips/LDEM_83S_10MPP_ADJ_artemis3-haworth_12km.tif",
        "pgda_90_south_pole_dems",
        "10 m/pix, +-12 km around the artemis3-haworth point (Artemis III): slope statistics.",
        clip=Clip(-37726.363, 90543.27, half_width_m=12_000.0),
    ),
    DataFile(
        "ldem_83s_10m_artemis3_malapert_massif_clip",
        Group.sites,
        Kind.tiff,
        f"{PGDA}/LOLA_20mpp/LDEM_83S_10MPP_ADJ.TIF",
        "data/pgda90/clips/LDEM_83S_10MPP_ADJ_artemis3-malapert-massif_12km.tif",
        "pgda_90_south_pole_dems",
        "10 m/pix, +-12 km around the artemis3-malapert-massif point (Artemis III): slope statistics.",
        clip=Clip(-503.018, 121730.386, half_width_m=12_000.0),
    ),
    DataFile(
        "ldem_83s_10m_artemis3_mons_mouton_plateau_clip",
        Group.sites,
        Kind.tiff,
        f"{PGDA}/LOLA_20mpp/LDEM_83S_10MPP_ADJ.TIF",
        "data/pgda90/clips/LDEM_83S_10MPP_ADJ_artemis3-mons-mouton-plateau_12km.tif",
        "pgda_90_south_pole_dems",
        "10 m/pix, +-12 km around the artemis3-mons-mouton-plateau point (Artemis III): slope statistics.",
        clip=Clip(87525.153, 147887.331, half_width_m=12_000.0),
    ),
    DataFile(
        "ldem_83s_10m_artemis3_mons_mouton_clip",
        Group.sites,
        Kind.tiff,
        f"{PGDA}/LOLA_20mpp/LDEM_83S_10MPP_ADJ.TIF",
        "data/pgda90/clips/LDEM_83S_10MPP_ADJ_artemis3-mons-mouton_12km.tif",
        "pgda_90_south_pole_dems",
        "10 m/pix, +-12 km around the artemis3-mons-mouton point (Artemis III): slope statistics.",
        clip=Clip(72937.632, 118209.265, half_width_m=12_000.0),
    ),
    DataFile(
        "ldem_83s_10m_artemis3_nobile_rim_1_clip",
        Group.sites,
        Kind.tiff,
        f"{PGDA}/LOLA_20mpp/LDEM_83S_10MPP_ADJ.TIF",
        "data/pgda90/clips/LDEM_83S_10MPP_ADJ_artemis3-nobile-rim-1_12km.tif",
        "pgda_90_south_pole_dems",
        "10 m/pix, +-12 km around the artemis3-nobile-rim-1 point (Artemis III): slope statistics.",
        clip=Clip(84004.02, 110160.962, half_width_m=12_000.0),
    ),
    DataFile(
        "ldem_83s_10m_artemis3_nobile_rim_2_clip",
        Group.sites,
        Kind.tiff,
        f"{PGDA}/LOLA_20mpp/LDEM_83S_10MPP_ADJ.TIF",
        "data/pgda90/clips/LDEM_83S_10MPP_ADJ_artemis3-nobile-rim-2_12km.tif",
        "pgda_90_south_pole_dems",
        "10 m/pix, +-12 km around the artemis3-nobile-rim-2 point (Artemis III): slope statistics.",
        clip=Clip(156941.653, 95070.423, half_width_m=12_000.0),
    ),
    DataFile(
        "ldem_83s_10m_artemis3_de_gerlache_rim_2_clip",
        Group.sites,
        Kind.tiff,
        f"{PGDA}/LOLA_20mpp/LDEM_83S_10MPP_ADJ.TIF",
        "data/pgda90/clips/LDEM_83S_10MPP_ADJ_artemis3-de-gerlache-rim-2_12km.tif",
        "pgda_90_south_pole_dems",
        "10 m/pix, +-12 km around the artemis3-de-gerlache-rim-2 point (Artemis III): slope statistics.",
        clip=Clip(-48792.758, 22635.816, half_width_m=12_000.0),
    ),
    DataFile(
        "ldem_83s_10m_artemis3_slater_plain_clip",
        Group.sites,
        Kind.tiff,
        f"{PGDA}/LOLA_20mpp/LDEM_83S_10MPP_ADJ.TIF",
        "data/pgda90/clips/LDEM_83S_10MPP_ADJ_artemis3-slater-plain_12km.tif",
        "pgda_90_south_pole_dems",
        "10 m/pix, +-12 km around the artemis3-slater-plain point (Artemis III): slope statistics.",
        clip=Clip(69919.505, -49798.784, half_width_m=12_000.0),
    ),
    DataFile(
        "ldem_75s_60m_site01_clip",
        Group.validation,
        Kind.tiff,
        f"{PDS_LOLA_POLAR}/ldem_75s_60m.img",
        "data/pds_lola/clips/LDEM_75S_60M_site01_150km.tif",
        "pds_lola_gdr",
        "PDS LOLA GDR 60 m polar map (V2.0, 2017), stand-in for product 69's own terrain (LDEM_85S_060M, "
        "not public; the project author, 2026-11-15). Same 60 m pixel grid as product 69. +-150 km window, "
        "heights in m above 1737.4 km (counts x 0.5).",
        clip=Clip(
            *SITE01_PS,
            half_width_m=150_000.0,
            label_url=f"{PDS_LOLA_POLAR}/ldem_75s_60m.lbl",
            scale=0.5,
        ),
    ),
    # --- Global coarse layer: LOLA LDEM_128 (LRO-L-LOLA-4-GDR-V1.0, product version 3.0,
    # 2017-09-15), simple cylindrical, 128 px/deg, MEAN EARTH/POLAR AXIS OF DE421, int16 x 0.5 m above
    # 1737.4 km. Used whole (read by window around each point), never clipped.
    DataFile(
        "ldem_128_lbl",
        Group.global_,
        Kind.pds3_label,
        f"{PDS_LOLA_CYL}/ldem_128.lbl",
        "data/pds_lola/cylindrical/LDEM_128.LBL",
        "lola_ldem_128",
        "PDS3 label of LDEM_128: checked field by field (lss.terrain.global_layer) before the image is read.",
    ),
    DataFile(
        "ldem_128_img",
        Group.global_,
        Kind.raw,
        f"{PDS_LOLA_CYL}/ldem_128.img",
        "data/pds_lola/cylindrical/LDEM_128.IMG",
        "lola_ldem_128",
        "LDEM_128 heights, 23040 x 46080 int16 (2,123,366,400 bytes; the reader checks the size).",
    ),
)

BY_ID: dict[str, DataFile] = {f.id: f for f in FILES}


def get(file_id: str) -> DataFile:
    return BY_ID[file_id]


def looks_like(kind: Kind, head: bytes) -> bool:
    """True when `head` (the file's first bytes) matches `kind`."""
    return any(head.startswith(m) for m in MAGIC[kind])
