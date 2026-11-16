# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
"""IAU feature names for the globe labels (contract 0.14.0): the loader's checks, the filters, the route, the
static copy. A small synthetic names file in E's format; no real data needed."""

import json
import os
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

import lss.api.app as app_module
from lss.api import static_export
from lss.api.feature_labels import FeatureLabelsError, load_labels, select
from lss.config import get_settings
from lss.contract import FeatureLabelsQuery, FeatureLabelsResponse, StaticIndex
from tests.api.test_thin_slice import write_served

TYPES = {"AA": "Crater, craters", "ME": "Mare, maria", "SF": "Satellite Feature", "MO": "Mons, montes"}
ROWS = [
    [10, "Abbot", "AA", 5.5562, 54.7431, 10.4],
    [11, "Mare Small", "ME", 20.0, -30.0, 300.0],
    [12, "Abbot A", "SF", 5.0, 55.0, 2.0],
    [13, "Mons Mouton", "MO", -84.4, 31.3, 140.0],
    [14, "Daedalus", "AA", -5.9, 179.4, 93.0],
    [15, "Icarus", "AA", -5.3, -173.2, 96.0],
    [16, "Big Crater", "AA", 0.0, 0.0, 300.0],
]


def names_file(directory, **change):
    data = {
        "format": 1,
        "source": {"url": "https://example.test/names.zip"},
        "coordinates": "planetocentric",
        "approval": "Adopted by IAU",
        "satellite_features_included": True,
        "types": TYPES,
        "fields": ["id", "name", "type", "lat", "lon", "diameter_km"],
        "features": ROWS,
    }
    data.update(change)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "iau_names.json").write_text(json.dumps(data), encoding="utf-8")
    return directory


def names(response):
    return [r[1] for r in response.rows]


# ------------------------------------------------------------------------------------ the loader


def test_loader_orders_largest_first_and_no_file_is_no_rows(tmp_path):
    labels = load_labels(names_file(tmp_path))
    assert [r[1] for r in labels.rows][:3] == ["Big Crater", "Mare Small", "Mons Mouton"]  # ties by name
    assert load_labels(tmp_path / "missing") is None
    empty = select(None, FeatureLabelsQuery())
    assert empty.rows == [] and empty.total == 0 and empty.dataset_id == "iau_gazetteer_moon"


@pytest.mark.parametrize(
    "change, why",
    [
        ({"format": 2}, "format 2"),
        ({"fields": ["id", "name"]}, "fields are"),
        ({"approval": "Any"}, "isn't limited"),
        ({"features": [*ROWS, [10, "Again", "AA", 0.0, 0.0, 1.0]]}, "repeats a feature id"),
        ({"features": [[1, "X", "ZZ", 0.0, 0.0, 1.0]]}, "isn't in the file's type list"),
        ({"features": [[1, "X", "AA", 91.0, 0.0, 1.0]]}, "out of range"),
        ({"features": [[1, "X", "AA", 0.0, 0.0]]}, "isn't 6 values"),
        ({"features": []}, "no features"),
    ],
)
def test_loader_refuses_a_file_it_cant_serve(tmp_path, change, why):
    with pytest.raises(FeatureLabelsError, match=why):
        load_labels(names_file(tmp_path, **change))


def test_filters(tmp_path):
    labels = load_labels(names_file(tmp_path))
    assert "Abbot A" not in names(select(labels, FeatureLabelsQuery()))  # satellite features off by default
    assert "Abbot A" in names(select(labels, FeatureLabelsQuery(include_satellite=True)))
    assert names(select(labels, FeatureLabelsQuery(types=["SF"]))) == ["Abbot A"]  # naming SF includes them
    assert names(select(labels, FeatureLabelsQuery(types=["ME", "MO"]))) == ["Mare Small", "Mons Mouton"]
    assert names(select(labels, FeatureLabelsQuery(min_diameter_km=140))) == [
        "Big Crater",
        "Mare Small",
        "Mons Mouton",
    ]
    assert names(select(labels, FeatureLabelsQuery(limit=2))) == ["Big Crater", "Mare Small"]
    polar = {"lat_min": -90, "lat_max": -80, "lon_min": -180, "lon_max": 180}
    assert names(select(labels, FeatureLabelsQuery(bbox=polar))) == ["Mons Mouton"]
    across = {"lat_min": -10, "lat_max": 10, "lon_min": 170, "lon_max": -170}  # crosses ±180°
    assert names(select(labels, FeatureLabelsQuery(bbox=across))) == ["Icarus", "Daedalus"]
    body = select(labels, FeatureLabelsQuery())
    assert body.total == len(ROWS) and body.types == dict(sorted(TYPES.items()))
    assert body.fields == ["id", "name", "type", "lat", "lon", "diameter_km"]


# ------------------------------------------------------------------------------------- the route


@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("LSS_DATA_DIR", str(tmp_path))
    caches = (
        get_settings,
        app_module._served,
        app_module._terrain,
        app_module._terrain_views,
        app_module._labels,
    )
    for f in caches:
        f.cache_clear()
    write_served(tmp_path / "cache" / "served")
    names_file(tmp_path / "cache" / "features")
    yield tmp_path
    for f in caches:
        f.cache_clear()


def test_route_filters_and_validates(data_dir):
    c = TestClient(app_module.create_app())
    params = {"types": ["AA", "SF"], "min_diameter_km": 50, "bbox": "-10,10,170,-170", "limit": 1}
    body = FeatureLabelsResponse.model_validate(c.get("/api/features/labels", params=params).json())
    assert names(body) == ["Icarus"]
    for bad in (
        {"bbox": "1,2"},
        {"bbox": "10,-10,0,1"},
        {"bbox": "0,1,0,x"},
        {"limit": 0},
        {"min_diameter_km": -1},
    ):
        r = c.get("/api/features/labels", params=bad)
        assert r.status_code == 422 and isinstance(r.json()["detail"], list), bad


def test_route_compresses_and_503s_an_unusable_file(data_dir):
    many = [*ROWS, *([100 + i, f"Abbot {i}", "SF", 5.0, 55.0, 1.0] for i in range(100))]
    names_file(data_dir / "cache" / "features", features=many)  # over the 1 KB compression threshold
    c = TestClient(app_module.create_app())
    r = c.get(
        "/api/features/labels", params={"include_satellite": "true"}, headers={"Accept-Encoding": "gzip"}
    )
    assert r.headers.get("content-encoding") == "gzip" and len(r.json()["rows"]) == len(many)
    names_file(data_dir / "cache" / "features", format=9)
    app_module._labels.cache_clear()
    assert c.get("/api/features/labels").status_code == 503


def test_static_copy_has_every_name_and_checks_the_route(data_dir, monkeypatch):
    client = TestClient(app_module.create_app())

    def fake_get_json(url, body=None):
        path = url.removeprefix("https://api.example")
        r = client.post(path, json=body) if body is not None else client.get(path)
        r.raise_for_status()
        return r.json()

    monkeypatch.setattr(static_export, "_get_json", fake_get_json)
    out = data_dir / "static"
    assert static_export.main([str(out), "--check-api", "https://api.example"]) == 0
    index = StaticIndex.model_validate(json.loads((out / "index.json").read_text(encoding="utf-8")))
    assert index.feature_labels == "feature_labels.json"
    static = json.loads((out / "feature_labels.json").read_text(encoding="utf-8"))
    assert len(static["rows"]) == len(ROWS)
    assert static == client.get("/api/features/labels", params={"include_satellite": "true"}).json()


def test_route_needs_no_engine(data_dir):
    code = (
        "import sys\n"
        "from fastapi.testclient import TestClient\n"
        "from lss.api.app import app\n"
        "assert TestClient(app).get('/api/features/labels').status_code == 200\n"
        "print(sorted(m for m in ('spiceypy', 'rasterio', 'numba') if m in sys.modules))\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env={**os.environ, "LSS_DATA_DIR": str(data_dir)},
        check=True,
    )
    assert out.stdout.strip() == "[]"
