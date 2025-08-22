# tests/backend/test_items.py
from fastapi.testclient import TestClient
from main import app  # thanks to conftest.py path tweak

client = TestClient(app)

def test_ping():
    r = client.get("/api/v1/ping")
    assert r.status_code == 200
    assert r.json()["ok"] is True

def test_items_crud():
    # create
    r = client.post("/api/v1/items/", json={"id": "1", "name": "foo", "description": "demo"})
    assert r.status_code == 201
    assert r.headers["location"].endswith("/api/v1/items/1")

    # list
    r = client.get("/api/v1/items/")
    assert r.status_code == 200
    assert any(i["id"] == "1" for i in r.json())

    # get one
    r = client.get("/api/v1/items/1")
    assert r.status_code == 200
    assert r.json()["name"] == "foo"

    # delete
    r = client.delete("/api/v1/items/1")
    assert r.status_code == 204

    # confirm 404 after delete
    r = client.get("/api/v1/items/1")
    assert r.status_code == 404