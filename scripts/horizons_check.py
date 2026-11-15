"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Fetch JPL Horizons reference az/el for the Sun and Earth at the served C1 site (step 4.7).

    uv run python scripts/horizons_check.py          # writes tests/engine/fixtures/horizons_site01_roi4.json

The site is the served scenario's location at the served observer height (DEM surface + unit height,
from the cached horizon), given to Horizons as a user-defined site on the Moon in east longitude,
latitude and altitude above the 1737.4 km sphere. Horizons quantity 4 is the apparent azimuth and
elevation (light-time, stellar aberration and light bending by the Sun and Earth; no refraction on the
Moon) in its MEAN_ME lunar frame from DE441. The fixture is compared with lss.ephem by
tests/engine/test_validation_horizons.py (tolerance and reasons: docs/methodology.md section 6.1).
Only the query and the parsed values are stored, with the header lines that identify the sources.
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

from lss.contract.examples import SCENARIO
from lss.ephem import MOON_RADIUS_M
from lss.horizon import cached_horizon

API = "https://ssd.jpl.nasa.gov/api/horizons.api"
OUT = Path(__file__).resolve().parents[1] / "tests" / "engine" / "fixtures" / "horizons_site01_roi4.json"
BODIES = {"SUN": "10", "EARTH": "399"}
HEADER_KEYS = ("Target body name", "Center body name", "Center geodetic", "Center pole/equ", "Center radii")


def epochs() -> list[datetime]:
    """Eleven epochs across the served window, and one every two years 2024-2050 at varied times."""
    w = [SCENARIO.window_start + timedelta(days=3 * i, hours=5 * i) for i in range(10)]
    w.append(SCENARIO.window_end)
    long = [
        datetime(2024 + 2 * k, 1 + (5 * k) % 12, 1 + (7 * k) % 28, (3 * k) % 24, tzinfo=UTC)
        for k in range(14)
    ]
    return sorted(w + long)


def jd_utc(t: datetime) -> float:
    return 2440587.5 + t.timestamp() / 86400.0


def site() -> tuple[float, float, float]:
    loc = SCENARIO.location
    hz = cached_horizon(loc.lat, loc.lon, SCENARIO.unit_height_m)
    return loc.lon % 360.0, loc.lat, hz.observer_radius_m - MOON_RADIUS_M


def query(body: str, times: list[datetime], east_lon: float, lat: float, alt_m: float) -> dict:
    params = {
        "format": "text",
        "COMMAND": f"'{BODIES[body]}'",
        "OBJ_DATA": "'NO'",
        "MAKE_EPHEM": "'YES'",
        "EPHEM_TYPE": "'OBSERVER'",
        "CENTER": "'coord@301'",
        "COORD_TYPE": "'GEODETIC'",
        "SITE_COORD": f"'{east_lon:.6f},{lat:.6f},{alt_m / 1000.0:.7f}'",
        "TLIST": "'" + " ".join(f"{jd_utc(t):.9f}" for t in times) + "'",
        "TLIST_TYPE": "'JD'",
        "TIME_TYPE": "'UT'",
        "QUANTITIES": "'4,20'",
        "ANG_FORMAT": "'DEG'",
        "EXTRA_PREC": "'YES'",
        "CSV_FORMAT": "'YES'",
    }
    url = API + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=120) as r:
        text = r.read().decode("utf-8")
    return {"params": params, "text": text}


def parse(text: str, times: list[datetime]) -> tuple[dict, list[dict]]:
    if "$$SOE" not in text:
        raise RuntimeError("Horizons returned no ephemeris:\n" + text[:2000])
    header = {}
    for line in text.splitlines():
        for k in HEADER_KEYS:
            if line.startswith(k):
                header[k] = line.split(":", 1)[1].strip()
    body = text.split("$$SOE", 1)[1].split("$$EOE", 1)[0]
    rows = []
    for t, line in zip(times, [x for x in body.strip().splitlines() if x.strip()], strict=True):
        f = [c.strip() for c in line.split(",")]
        rows.append(
            {
                "utc": t.isoformat().replace("+00:00", "Z"),
                "horizons_time": f[0],
                "azimuth_deg": float(f[3]),
                "elevation_deg": float(f[4]),
                "distance_au": float(f[5]),
            }
        )
    return header, rows


def main() -> int:
    times = epochs()
    east_lon, lat, alt_m = site()
    out = {
        "source": API,
        "fetched": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "site": {"east_lon_deg": east_lon, "lat_deg": lat, "altitude_m": alt_m},
        "quantity": "4 (apparent AZ-EL, airless), 20 (observer range)",
        "bodies": {},
    }
    for body in BODIES:
        q = query(body, times, east_lon, lat, alt_m)
        header, rows = parse(q["text"], times)
        out["bodies"][body] = {
            "query": q["params"] | {"TLIST": "(the utc values below)"},
            "header": header,
            "rows": rows,
        }
        print(body, header.get("Center pole/equ"), len(rows), "rows")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"written {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
