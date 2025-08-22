

from typing import Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Response
from pydantic import BaseModel, Field

# Final router for Items API
router = APIRouter(tags=["items"])


class Item(BaseModel):
    id: str = Field(..., min_length=1)
    name: str
    description: Optional[str] = None


# Simple in-memory store (replace with DB later)
_DB: Dict[str, Item] = {}


def index_item(item: Item) -> None:
    """Background hook placeholder (e.g., enqueue to orchestration graph)."""
    return None


@router.post("/", response_model=Item, status_code=201)
def create_item(item: Item, bg: BackgroundTasks, response: Response) -> Item:
    """Create a new item. Returns 201 and sets Location header.
    Raises 409 if the id already exists.
    """
    if item.id in _DB:
        raise HTTPException(status_code=409, detail="Item already exists")
    _DB[item.id] = item
    bg.add_task(index_item, item)
    response.headers["Location"] = f"/api/v1/items/{item.id}"
    return item


@router.get("/", response_model=List[Item])
def list_items() -> List[Item]:
    """List all items in a stable order (by id)."""
    return [_DB[k] for k in sorted(_DB.keys())]


@router.get("/{item_id}", response_model=Item)
def get_item(item_id: str) -> Item:
    """Get one item by id or 404 if missing."""
    item = _DB.get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.delete("/{item_id}", status_code=204)
def delete_item(item_id: str) -> Response:
    """Delete an item by id. Returns 204 on success or 404 if missing."""
    if item_id not in _DB:
        raise HTTPException(status_code=404, detail="Item not found")
    _DB.pop(item_id)
    return Response(status_code=204)