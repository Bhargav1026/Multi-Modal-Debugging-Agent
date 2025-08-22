# tests/backend/test_incidents.py
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_rca_stub():
    payload = {"repo": "./", "log": "ValueError: example", "screenshot_b64": None}
    r = client.post("/api/v1/incidents/rca", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert "rca" in body and isinstance(body["rca"], str)
    assert "patch" in body and "test" in body