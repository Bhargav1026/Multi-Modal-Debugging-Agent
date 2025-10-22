Run the demo end-to-end:

1) Start the backend (choose one):
   - `python main.py`
   - or `uvicorn backend.app.main:app --reload`

2) In another terminal:
   - `python run_demo.py`

The script POSTs `examples/demo_incident/incident_request.json`
to the configured endpoint and saves `examples/demo_incident/output/incident_report.md`.

The output file `examples/demo_incident/output/incident_report.md` contains the generated Root Cause Analysis (RCA) summary with details on the issue, signals, and minimal fix suggestions.