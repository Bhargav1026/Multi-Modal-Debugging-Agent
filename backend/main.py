from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import api_router

import os
from pathlib import Path
try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    load_dotenv = None  # dotenv is optional

# Load environment from the repo root .env (…/backend/.. = project root)
try:
    if load_dotenv:
        env_loaded = load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")
        print(f"[backend] .env loaded: {bool(env_loaded)}")
except Exception as e:
    print(f"[backend] .env load skipped: {e}")

# Read optional CORS origins from env (comma-separated) or fall back to '*'
_origins_env = os.getenv("CORS_ALLOW_ORIGINS", "*").strip()
_allow_origins = ["*"] if _origins_env == "*" else [o.strip() for o in _origins_env.split(",") if o.strip()]

# Log non-sensitive runtime choices
print("[backend] LLM_BACKEND =", os.getenv("LLM_BACKEND", "<unset>"))
print("[backend] GEMINI_MODEL =", os.getenv("GEMINI_MODEL", "<unset>"))


app = FastAPI(title="Multi-Modal Debugging Agent")

# Dev CORS: allow VS Code webview / localhost to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Multi-Modal Debugging Agent Backend Running 🚀"}

app.include_router(api_router, prefix="/api/v1")

@app.get("/healthz")
def health():
    return {"ok": True}