from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

app = FastAPI()

# --- Data Models ---
class Item(BaseModel):
    name: str
    price: float
    in_stock: bool = True

class ItemUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    in_stock: Optional[bool] = None

# --- Fake in-memory database ---
fake_db = {}

# --- GET: Read root ---
@app.get("/")
def read_root():
    return {"Hello": "API World"}

# --- GET: Read a single item ---
@app.get("/items/{item_id}")
def read_item(item_id: int):
    if item_id not in fake_db:
        raise HTTPException(status_code=404, detail="Item not found")
    return fake_db[item_id]

# --- POST: Create a new item ---
@app.post("/items/{item_id}", status_code=201)   # ✅ Fixed - was @[app.post](http://app.post)
def create_item(item_id: int, item: Item):
    if item_id in fake_db:
        raise HTTPException(status_code=400, detail="Item already exists")
    fake_db[item_id] = item.dict()
    return {"message": "Item created", "item": fake_db[item_id]}

# --- PUT: Fully replace an existing item ---
@app.put("/items/{item_id}")
def update_item(item_id: int, item: Item):
    if item_id not in fake_db:
        raise HTTPException(status_code=404, detail="Item not found")
    fake_db[item_id] = item.dict()
    return {"message": "Item replaced", "item": fake_db[item_id]}

# --- PATCH: Partially update an item ---
@app.patch("/items/{item_id}")
def patch_item(item_id: int, item: ItemUpdate):
    if item_id not in fake_db:
        raise HTTPException(status_code=404, detail="Item not found")
    stored = fake_db[item_id]
    updates = item.dict(exclude_unset=True)
    stored.update(updates)
    fake_db[item_id] = stored
    return {"message": "Item updated", "item": fake_db[item_id]}

# --- DELETE: Remove an item ---
@app.delete("/items/{item_id}")
def delete_item(item_id: int):
    if item_id not in fake_db:
        raise HTTPException(status_code=404, detail="Item not found")
    deleted = fake_db.pop(item_id)
    return {"message": "Item deleted", "item": deleted}
