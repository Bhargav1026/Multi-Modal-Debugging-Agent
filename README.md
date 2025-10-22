# Multi-Modal Debugging Agent

## Quickstart Demo


# 1) create & activate venv
python -m venv .venv && source .venv/bin/activate

# 2) install deps
pip install -r requirements.txt

# 3) start backend (choose one)
python main.py
# or
uvicorn backend.app.main:app --reload

# 4) run the demo (new terminal, same venv)
python run_demo.py


## Overview
The Multi-Modal Debugging Agent is a project designed to facilitate debugging across multiple modalities. It provides a backend service that handles API requests, orchestrates various components, and manages data models and worker processes. Additionally, it includes a VS Code extension to enhance the debugging experience.

## Project Structure
The project is organized into several key directories:

- **backend/**: Contains the backend application code.
  - **app/**: The main application logic, including:
    - **api/**: Modules for handling API requests and responses.
    - **orchestration/**: Logic for coordinating different components.
    - **models/**: Data models defining the structure of the application data.
    - **workers/**: Background tasks and asynchronous processing.
  - **tests/**: Unit and integration tests for the backend application.
  - **main.py**: The entry point for the backend application.
  - **requirements.txt**: Lists dependencies required for the backend.
  - **.env.example**: Example environment variables for configuration.

- **extension/**: Contains the VS Code extension code.
  - **src/**: The source code for the extension.
  - **package.json**: Configuration file for the extension.
  - **tsconfig.json**: TypeScript configuration file.
  - **README.md**: Documentation specific to the extension.

- **sandbox/**: Contains files for Docker containerization.
  - **Dockerfile**: Instructions for building the Docker image.
  - **entrypoint.sh**: Shell script for the Docker container entry point.

- **docs/**: Documentation files.
  - **API.md**: API documentation detailing endpoints and usage.
  - **INCIDENT_REPORT_TEMPLATE.md**: Template for reporting incidents.

## Getting Started
To get started with the Multi-Modal Debugging Agent, follow these steps:

1. **Clone the Repository**
   ```
   git clone <repository-url>
   cd Multi-Modal-Debugging-Agent
   ```

2. **Set Up the Backend**
   - Navigate to the `backend` directory.
   - Install the required dependencies:
     ```
     pip install -r requirements.txt
     ```
   - Configure environment variables by copying `.env.example` to `.env` and updating the values as needed.

3. **Run the Backend**
   ```
   python main.py
   ```

4. **Set Up the Extension**
   - Navigate to the `extension` directory.
   - Install the necessary dependencies:
     ```
     npm install
     ```
   - Open the extension in your preferred code editor and follow the instructions in `README.md` for usage.

5. **Run the Sandbox**
   - Build the Docker image:
     ```
     docker build -t multi-modal-debugging-agent .
     ```
   - Run the Docker container:
     ```
     docker run multi-modal-debugging-agent
     ```

## Contributing
Contributions are welcome! Please read the [CONTRIBUTING.md](docs/CONTRIBUTING.md) for guidelines on how to contribute to this project.

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
# Multi‑Modal Debugging Agent

**VS Code side‑chat + FastAPI backend** that turns logs/stacktraces into an actionable incident report with:
- RCA summary (Exception • Location • Context)
- Suggested **patch** (unified diff) and **test** snippet
- One‑click **Open Location**, **Preview Report**, **Save Patch/Test**, **Copy RCA/Analysis**
- Works with either **file content** or **file path** (server reads file, with `.ipynb` cell extraction)

---

## Project Structure
```
Multi-Modal-Debugging-Agent/
├── backend/
│   ├── app/
│   │   ├── api/                # FastAPI routes (incidents RCA)
│   │   ├── models/             # Pydantic schemas
│   │   ├── orchestration/      # Heuristic graph: RCA → patch → test
│   │   └── service/            # Optional shims (normalizers, file reader)
│   ├── main.py                 # Uvicorn entry (FastAPI app)
│   ├── requirements.txt
│   └── tests/                  # Backend tests (pytest)
├── extension/
│   ├── src/                    # VS Code extension (TypeScript)
│   ├── out/                    # Compiled JS (tsc output)
│   ├── package.json            # Commands, menus, keybindings, settings
│   └── tsconfig.json
└── docs/                       # API docs, templates
```

> **Note**: The folders `models/`, `orchestration/`, `workers/`, and `tests/` are **directories**, not single files. If you see a file with one of those names, rename it to a folder.

---

## Requirements
- **VS Code** ≥ 1.85
- **Node.js** ≥ 18 (for the extension)
- **Python** ≥ 3.10 (for the backend)
- macOS, Linux, or Windows

> Optional (not required for current flow): Docker, Redis, PostgreSQL. We don’t use them yet.

---

## Quick Start (Two Terminals)

### Terminal A — Backend (FastAPI)
```bash
cd backend
python -m venv .venv                    # create a virtual env (Windows: python -m venv .venv)
source .venv/bin/activate               # activate (Windows: .venv\\Scripts\\activate)
pip install -r requirements.txt

# run the API with auto‑reload on code changes
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
- Open Swagger UI at **http://127.0.0.1:8000/docs** to see `/api/v1/incidents/rca`.
- If the port is busy, pick another (e.g., `--port 8080`) and update the extension setting `multiModalDebug.backendBase` accordingly.

### Terminal B — Extension (VS Code)
```bash
cd extension
npm install           # installs dependencies listed in package.json
npm run compile       # compiles TypeScript → out/extension.js (via tsc)
```
- Press **F5** to launch the **Extension Development Host**.
  - On some Macs, F5 triggers VoiceOver; use **fn+F5** or click **Run and Debug ▶**.
- A **status‑bar** icon “OurProject‑1” opens the side chat.

> **What does `npm run compile` do?** It runs the TypeScript compiler using `tsconfig.json` and outputs JavaScript into `extension/out/`. The Dev Host runs `out/extension.js`.

---

## Extension Usage
Open the side chat (status‑bar button or Command Palette: **OurProject‑1: Open Side Chat**). You’ll see these controls:

- **Read File** / **Write File** / **Overwrite File** — simple file helpers.
- **Analyze via Backend** (picker) — choose a file. If the toggle below is **on**, the extension sends **{ path }** and the server reads the file (handles large files, converts `.ipynb` cells to text). If the toggle is **off**, the extension sends the **file content**.
- **Analyze Active Editor** — analyzes the current editor. If you have a selection, it analyzes the selection; otherwise, the whole file. With the toggle **on** and no selection, it sends **{ path }**.
- **Server reads file (send path)** — toggle for the two Analyze buttons described above. The choice is remembered.
- **Open Location** — jumps to `file:line` if present in the analysis.
- **Preview Report** — opens a Markdown report (Timestamp, Source, Summary, RCA, Context, Patch, Test).
- **Save Patch / Save Test** — saves to `patches/` and `tests/` in your workspace (or prompts for a path).
- **Copy Analysis** — copies the full JSON.
- **Copy RCA** — copies just the RCA text.
- **◀ ▶** — navigate analysis history in the panel.
- **Clear** — clears the panel output **and history**.

### Keybindings (Mac / Windows‑Linux)
- Open Side Chat — `⇧⌘⌥O` / `Shift+Ctrl+Alt+O`
- Analyze Active Editor — `⇧⌘⌥A` / `Shift+Ctrl+Alt+A`
- Analyze via Backend — `⇧⌘⌥L` / `Shift+Ctrl+Alt+L`
- Preview Report — `⇧⌘⌥P` / `Shift+Ctrl+Alt+P`
- Open Location — `⇧⌘⌥G` / `Shift+Ctrl+Alt+G`
- Save Patch — `⇧⌘⌥1` / `Shift+Ctrl+Alt+1`
- Save Test — `⇧⌘⌥2` / `Shift+Ctrl+Alt+2`
- Copy RCA — `⇧⌘⌥X` / `Shift+Ctrl+Alt+X`
- Copy Analysis — `⇧⌘⌥C` / `Shift+Ctrl+Alt+C`
- Save Report — `⇧⌘⌥R` / `Shift+Ctrl+Alt+R`
- Clear History — `⇧⌘⌥⌫` / `Shift+Ctrl+Alt+Backspace`

### Extension Settings
**File → Preferences → Settings → “Multi‑Modal Debugging Agent”**
- `multiModalDebug.backendBase` — FastAPI base URL (default `http://127.0.0.1:8000`).
- `multiModalDebug.maxPayload` — client‑side payload clamp (bytes) when sending content.
- `multiModalDebug.notebookStrategy` — `cells` (extract code/markdown cells) or `raw` for `.ipynb` files.

---

## Backend API
**POST** `/api/v1/incidents/rca`

**Request JSON**
```json
{
  "repo": ".",
  "path": "/abs/or/relative/file.log",   // optional — if present, server reads file
  "log": "...raw text...",                 // optional — used when path is not provided
  "screenshot_b64": null,                  // optional
  "id": null                               // optional — server derives one if missing
}
```

**Response JSON**
```json
{
  "rca": "Initial RCA based on provided logs...",
  "patch": "--- a/file.py\n+++ b/file.py\n@@\n+...suggestion...",
  "test": "...pytest or mocha skeleton...",
  "exception": "KeyError: 'id'",
  "file": "backend/app/service/core.py:118",
  "context": ["... lines around the error ..."],
  "note": "Converted from .ipynb; Truncated large input for performance"
}
```

### Try it with curl
```bash
# 1) Analyze raw text
curl -X POST http://127.0.0.1:8000/api/v1/incidents/rca \
  -H 'Content-Type: application/json' \
  -d '{
        "repo": ".",
        "log": "ERROR: Traceback... KeyError: \"id\""
      }'

# 2) Ask server to read a file
curl -X POST http://127.0.0.1:8000/api/v1/incidents/rca \
  -H 'Content-Type: application/json' \
  -d '{
        "repo": ".",
        "path": "./sample.log"
      }'
```

---

## Common Commands Explained
- **`npm install`** — installs Node dependencies from `package.json` into `node_modules/`.
- **`npm run compile`** — runs the TypeScript compiler (`tsc`) using `tsconfig.json` to build `out/extension.js`.
- **F5 / Run and Debug ▶** — launches a temporary VS Code window (**Extension Development Host**) with your extension loaded.
- **`python -m venv .venv`** — creates an isolated Python environment in `.venv/`.
- **`source .venv/bin/activate`** — activates that environment (use `.venv\\Scripts\\activate` on Windows).
- **`pip install -r requirements.txt`** — installs backend Python dependencies.
- **`uvicorn app.main:app --reload`** — runs the FastAPI server and reloads on code changes.

> **Do I need Redis/Postgres/Docker?** No. The current flow is file/text → RCA. Those services are reserved for future features.

---

## Troubleshooting
- **No endpoints in Swagger** — make sure `app.include_router(...)` is called in `backend/app/main.py` and files are saved.
- **Analyze Active says “No active editor”** — click inside an editor or use the panel’s **Read File** first; we also fall back to the last cached file.
- **Nothing happens on Analyze** — verify backend is running on `backendBase`. Try `curl` as above.
- **Port already in use** — change the port in the Uvicorn command *and* in the extension setting.
- **F5 triggers VoiceOver on macOS** — press **fn+F5** or click **Run and Debug ▶**.
- **TypeScript red squiggles** — run `npm install`, then `npm run compile`. Ensure VS Code uses the workspace TypeScript version.

---

## Testing
- **Backend**: add tests under `backend/tests/` and run `pytest` inside the virtualenv.
- **Extension**: `npm run compile` (or `npm run watch`) while using the Dev Host.

---

## Release (optional)
- Bump `version` in `extension/package.json`.
- Package VSIX (requires `vsce`):
  ```bash
  npm i -g @vscode/vsce
  vsce package
  ```
- Attach screenshots/GIFs to this README (UI & Swagger) before publishing on GitHub.

---

## License
MIT — see [LICENSE](LICENSE).