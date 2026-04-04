from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from db.connection import execute_statement, fetch_all_dicts, fetch_one_dict

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


def _fetch_pools_from_db():
    rows = fetch_all_dicts(
        """
        select
            p.id,
            p.name,
            p.tvl,
            p.apy,
            round(p.volatility_cap_bps / 100.0, 2) as volatility_cap,
            count(a.id) as agents
        from pools p
        left join agents a on a.risk_pool = p.id
        group by p.id, p.name, p.tvl, p.apy, p.volatility_cap_bps
        order by p.id
        """
    )
    return [
        {
            **row,
            "tvl": float(row["tvl"] or 0),
            "apy": float(row["apy"] or 0),
            "volatility_cap": float(row["volatility_cap"] or 0),
            "agents": int(row["agents"] or 0),
        }
        for row in rows
    ]


@router.get("/")
def list_pools():
    try:
        pools = _fetch_pools_from_db()
        if pools:
            return pools
    except Exception:
        pass
    return POOLS


@router.get("/{pool_id}")
def get_pool(pool_id: str):
    try:
        pool = fetch_one_dict(
            """
            select
                p.id,
                p.name,
                p.tvl,
                p.apy,
                round(p.volatility_cap_bps / 100.0, 2) as volatility_cap,
                count(a.id) as agents
            from pools p
            left join agents a on a.risk_pool = p.id
            where p.id = :pool_id
            group by p.id, p.name, p.tvl, p.apy, p.volatility_cap_bps
            """,
            {"pool_id": pool_id},
        )
        if pool:
            return {
                **pool,
                "tvl": float(pool["tvl"] or 0),
                "apy": float(pool["apy"] or 0),
                "volatility_cap": float(pool["volatility_cap"] or 0),
                "agents": int(pool["agents"] or 0),
            }
    except Exception:
        pass

    pool = next((p for p in POOLS if p["id"] == pool_id), None)
    if not pool:
        raise HTTPException(status_code=404, detail="Pool not found")
    return pool


@router.post("/deposit")
def deposit(data: Deposit):
    try:
        pool = fetch_one_dict("select id from pools where id = :pool_id", {"pool_id": data.pool_id})
        if pool:
            execute_statement(
                """
                insert into investors (address)
                values (:address)
                on conflict (address) do nothing
                """,
                {"address": data.investor_address},
            )
            execute_statement(
                """
                insert into deposits (investor_id, pool_id, amount, tx_hash)
                values (
                    (select id from investors where address = :address),
                    :pool_id,
                    :amount,
                    :tx_hash
                )
                """,
                {
                    "address": data.investor_address,
                    "pool_id": data.pool_id,
                    "amount": data.amount,
                    "tx_hash": "0xsimulated...",
                },
            )
            execute_statement(
                """
                update pools
                set tvl = coalesce(tvl, 0) + :amount
                where id = :pool_id
                """,
                {"amount": data.amount, "pool_id": data.pool_id},
            )
            return {"tx_hash": "0xsimulated...", "pool": data.pool_id, "amount": data.amount, "status": "pending"}
    except Exception:
        pass

    pool = next((p for p in POOLS if p["id"] == data.pool_id), None)
    if not pool:
        raise HTTPException(status_code=404, detail="Pool not found")
    pool["tvl"] += data.amount
    return {"tx_hash": "0xsimulated...", "pool": data.pool_id, "amount": data.amount, "status": "pending"}
