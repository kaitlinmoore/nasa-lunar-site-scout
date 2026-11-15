# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
from fastapi.testclient import TestClient

from lss.api.app import app
from lss.contract import CONTRACT_VERSION

client = TestClient(app)


def test_health_returns_contract_version():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["contract_version"] == CONTRACT_VERSION


def test_sites_serves_fixture():
    r = client.get("/api/sites")
    assert r.status_code == 200
    body = r.json()
    assert body["_placeholder"] is False
    site = body["sites"][0]
    assert site["id"] == "pgda-site01"
    assert (site["location"]["lat"], site["location"]["lon"]) == (-89.452675, -137.148653)
    assert site["name"] == "Site01 Connecting ridge (Barker 2021 RoI 4)"
    assert "Barker" in site["source"] and "Table 2" in site["source"]


def test_sites_category_filter():
    assert client.get("/api/sites", params={"category": "apollo"}).json()["sites"] == []


def test_cors_allows_dev_origin():
    r = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"
