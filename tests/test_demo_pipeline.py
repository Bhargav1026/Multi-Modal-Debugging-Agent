from pathlib import Path
import json, os, requests

def test_demo_endpoint_runs():
    base = os.environ.get("MMD_AGENT_BASE_URL", "http://127.0.0.1:8000")
    run_ep = os.environ.get("MMD_AGENT_RUN_ENDPOINT", "/api/v1/incidents/rca")
    url = base.rstrip("/") + run_ep

    payload = json.loads(Path("examples/demo_incident/incident_request.json").read_text())
    r = requests.post(url, json=payload, timeout=60)
    assert r.status_code == 200, r.text

    body = r.json()
    assert any(k in body for k in ["report_markdown", "report", "result"]), body