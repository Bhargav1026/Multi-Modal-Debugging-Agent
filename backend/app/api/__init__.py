from fastapi import APIRouter

from .routes_items import router as items_router
from .routes_incidents import router as incidents_router
from .routes_runner import router as runner_router

# Top-level API router that main.py imports as `api_router`
api_router = APIRouter()

@api_router.get("/ping")
def ping():
    return {"ok": True, "service": "ourproject-1"}

# Mount feature routers
api_router.include_router(items_router, prefix="/items", tags=["items"])
api_router.include_router(incidents_router, prefix="/incidents", tags=["incidents"])
api_router.include_router(runner_router)