import os, json, time, pathlib, requests

# Config
BASE_URL = os.environ.get("MMD_AGENT_BASE_URL", "http://127.0.0.1:8000")
# Set to your actual run endpoint; you can change this once if your router differs.
RUN_ENDPOINT = os.environ.get("MMD_AGENT_RUN_ENDPOINT", "/api/v1/incidents/rca")
RUN_URL = BASE_URL.rstrip("/") + RUN_ENDPOINT

DEMO_DIR = pathlib.Path("examples/demo_incident")
REQ_PATH = DEMO_DIR / "incident_request.json"
OUT_DIR = DEMO_DIR / "output"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_REPORT = OUT_DIR / "incident_report.md"

def main():
    assert REQ_PATH.exists(), f"Missing {REQ_PATH}"
    with open(REQ_PATH, "r") as f:
        payload = json.load(f)

    print(f"[demo] POST {RUN_URL}")
    resp = requests.post(RUN_URL, json=payload, timeout=120)
    if resp.status_code >= 400:
        raise SystemExit(f"Request failed: {resp.status_code} {resp.text[:2000]}")

    data = resp.json()
    # Be flexible: accept either direct markdown or a nested field
    report_md = data.get("report_markdown") or data.get("report") or data.get("result") or ""
    if not report_md:
        # fallback: stringify JSON for visibility
        report_md = f"# Incident Report (raw)\n\n```json\n{json.dumps(data, indent=2)}\n```"

    OUT_REPORT.write_text(report_md)
    print(f"[demo] Wrote {OUT_REPORT.resolve()}")
    print("[demo] Done ✅")

if __name__ == "__main__":
    main()