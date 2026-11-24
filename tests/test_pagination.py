"""Tests de la pagination sur /quotes et /fleet-assets."""

from __future__ import annotations

import importlib
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from pricing_engine import api as api_module
    importlib.reload(api_module)
    yield TestClient(api_module.app)


def _login(client, email, mdp):
    r = client.post("/api/v1/auth/login", json={"email": email, "mot_de_passe": mdp})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_fleet_assets_pagination_renvoie_les_headers(client):
    """Headers X-Total-Count, X-Limit, X-Offset présents."""
    r = client.get("/api/v1/catalog/fleet-assets?limit=5&offset=0")
    assert r.status_code == 200
    assert "x-total-count" in r.headers
    assert int(r.headers["x-total-count"]) == 17  # seed Lot 5
    assert r.headers["x-limit"] == "5"
    assert r.headers["x-offset"] == "0"
    data = r.json()
    assert len(data) == 5


def test_fleet_assets_pagination_navigue_les_pages(client):
    """Page 1 (0-5) + page 2 (5-10) + page 3 (10-15) + page 4 (15+)
    donnent les 17 assets sans doublon."""
    tous_asset_numbers = set()
    for offset in [0, 5, 10, 15]:
        r = client.get(f"/api/v1/catalog/fleet-assets?limit=5&offset={offset}")
        for item in r.json():
            tous_asset_numbers.add(item["asset_number"])
    assert len(tous_asset_numbers) == 17


def test_fleet_assets_pagination_bornes_strictes(client):
    """limit max=500, limit min=1, offset min=0 → 422 sinon."""
    r = client.get("/api/v1/catalog/fleet-assets?limit=0")
    assert r.status_code == 422
    r = client.get("/api/v1/catalog/fleet-assets?limit=501")
    assert r.status_code == 422
    r = client.get("/api/v1/catalog/fleet-assets?offset=-1")
    assert r.status_code == 422


def test_quotes_pagination(client):
    auth = _login(client, "admin@akiem.com", "admin")
    # Crée 12 quotes
    for i in range(12):
        client.post("/api/v1/catalog/quotes",
            json={"client_code": f"C{i}", "client_name": f"Client {i}"},
            headers=auth)
    # Page de 5
    r = client.get("/api/v1/catalog/quotes?limit=5&offset=0", headers=auth)
    assert r.status_code == 200
    assert int(r.headers["x-total-count"]) >= 12
    assert len(r.json()) == 5
    # Page suivante
    r = client.get("/api/v1/catalog/quotes?limit=5&offset=5", headers=auth)
    assert len(r.json()) == 5
    # Offset qui dépasse → page vide mais 200
    r = client.get("/api/v1/catalog/quotes?limit=5&offset=999", headers=auth)
    assert r.status_code == 200
    assert r.json() == []
