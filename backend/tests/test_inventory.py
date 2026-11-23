import pytest


def test_list_materials(client, auth_headers):
    res = client.get("/api/inventory/materials?page=1&page_size=15", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 6624
    assert len(data["items"]) == 15
    first = data["items"][0]
    assert "material_id" in first
    assert "on_hand_qty" in first
    assert "available_qty" in first
    assert first["available_qty"] >= 0


def test_list_materials_filtering(client, auth_headers):
    res = client.get("/api/inventory/materials?plant_id=IN-TN-01&page_size=5", headers=auth_headers)
    assert res.status_code == 200
    for item in res.json()["items"]:
        assert item["plant_id"] == "IN-TN-01"


def test_get_material_summary(client, auth_headers):
    res = client.get("/api/inventory/materials/MAT-SOC-001/summary", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["material_id"] == "MAT-SOC-001"
    assert data["total_on_hand"] >= 0
    assert len(data["plants"]) > 0

