from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

POOLS = [
    {"id": "conservative", "name": "Conservative", "tvl": 4200000, "apy": 12.4, "agents": 3, "volatility_cap": 8},
    {"id": "balanced", "name": "Balanced", "tvl": 8700000, "apy": 24.7, "agents": 5, "volatility_cap": 18},
    {"id": "aggressive", "name": "Aggressive", "tvl": 12400000, "apy": 47.2, "agents": 6, "volatility_cap": 35},
]


class Deposit(BaseModel):
    pool_id: str
    amount: float
    investor_address: str


@router.get("/")
def list_pools():
    return POOLS


@router.get("/{pool_id}")
def get_pool(pool_id: str):
    pool = next((p for p in POOLS if p["id"] == pool_id), None)
    if not pool:
        raise HTTPException(status_code=404, detail="Pool not found")
    return pool


@router.post("/deposit")
def deposit(data: Deposit):
    pool = next((p for p in POOLS if p["id"] == data.pool_id), None)
    if not pool:
        raise HTTPException(status_code=404, detail="Pool not found")
    pool["tvl"] += data.amount
    return {"tx_hash": "0xsimulated...", "pool": data.pool_id, "amount": data.amount, "status": "pending"}
