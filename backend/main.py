from fastapi import FastAPI
from app.api import router as api_router

app = FastAPI(title="Multi-Modal Debugging Agent")

@app.get("/")
def read_root():
    return {"message": "Multi-Modal Debugging Agent Backend Running 🚀"}

app.include_router(api_router, prefix="/api/v1")

@app.get("/healthz")
def health():
    return {"ok": True}