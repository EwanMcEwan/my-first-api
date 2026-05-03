from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel
from typing import Optional
from starlette.status import HTTP_403_FORBIDDEN

app = FastAPI()

# --- 1. Security Setup ---
API_KEY = "your_secret_token_here"  # <--- Change this to your private key!
API_KEY_NAME = "access_token"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def get_api_key(header_value: str = Security(api_key_header)):
    if header_value == API_KEY:
        return header_value
    raise HTTPException(
        status_code=HTTP_403_FORBIDDEN, detail="Could not validate credentials"
    )

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

# --- GET: Read root (Public - no key needed) ---
@app.get("/")
def read_root():
    return {"Hello": "API World"}

# --- PROTECTED ENDPOINTS (Add Depends(get_api_key)) ---

@app.get("/items/{item_id}")
def read_item(item_id: int, api_key: str = Depends(get_api_key)):
    if item_id not in fake_db:
        raise HTTPException(status_code=404, detail="Item not found")
    return fake_db[item_id]

@app.post("/items/{item_id}", status_code=201)
def create_item(item_id: int, item: Item, api_key: str = Depends(get_api_key)):
    if item_id in fake_db:
        raise HTTPException(status_code=400, detail="Item already exists")
    fake_db[item_id] = item.dict()
    return {"message": "Item created", "item": fake_db[item_id]}

@app.put("/items/{item_id}")
def update_item(item_id: int, item: Item, api_key: str = Depends(get_api_key)):
    if item_id not in fake_db:
        raise HTTPException(status_code=404, detail="Item not found")
    fake_db[item_id] = item.dict()
    return {"message": "Item replaced", "item": fake_db[item_id]}

@app.patch("/items/{item_id}")
def patch_item(item_id: int, item: ItemUpdate, api_key: str = Depends(get_api_key)):
    if item_id not in fake_db:
        raise HTTPException(status_code=404, detail="Item not found")
    stored = fake_db[item_id]
    updates = item.dict(exclude_unset=True)
    stored.update(updates)
    fake_db[item_id] = stored
    return {"message": "Item updated", "item": fake_db[item_id]}

@app.delete("/items/{item_id}")
def delete_item(item_id: int, api_key: str = Depends(get_api_key)):
    if item_id not in fake_db:
        raise HTTPException(status_code=404, detail="Item not found")
    deleted = fake_db.pop(item_id)
    return {"message": "Item deleted", "item": deleted}
