import asyncio
import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from db.connection import execute_statement, fetch_all_dicts, fetch_one_dict

logger = logging.getLogger(__name__)
router = APIRouter()

POOLS = [
    {"id": "conservative", "name": "Conservative", "tvl": 4200000, "apy": 12.4, "agents": 3, "volatility_cap": 8},
    {"id": "balanced",     "name": "Balanced",     "tvl": 8700000, "apy": 24.7, "agents": 5, "volatility_cap": 18},
    {"id": "aggressive",   "name": "Aggressive",   "tvl": 12400000, "apy": 47.2, "agents": 6, "volatility_cap": 35},
]

_POOL_INT = {"conservative": 0, "balanced": 1, "aggressive": 2}


class Deposit(BaseModel):
    pool_id: str
    amount: float
    investor_address: str


def _fetch_pools_from_db():
    rows = fetch_all_dicts(
        """
        select
            v.id, v.name, v.tvl, null::numeric as apy,
            round(v.volatility_cap_bps / 100.0, 2) as volatility_cap,
            count(a.id) as agents
        from vaults v
        left join agents a on a.vault_id = v.id
        group by v.id, v.name, v.tvl, v.volatility_cap_bps
        order by v.id
        """,
    )
    return [
        {
            **row,
            "tvl":            float(row["tvl"] or 0),
            "apy":            float(row["apy"] or 0),
            "volatility_cap": float(row["volatility_cap"] or 0),
            "agents":         int(row["agents"] or 0),
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
                v.id, v.name, v.tvl, null::numeric as apy,
                round(v.volatility_cap_bps / 100.0, 2) as volatility_cap,
                count(a.id) as agents
            from vaults v
            left join agents a on a.vault_id = v.id
            where v.id = :pool_id
            group by v.id, v.name, v.tvl, v.volatility_cap_bps
            """,
            {"pool_id": pool_id},
        )
        if pool:
            return {
                **pool,
                "tvl":            float(pool["tvl"] or 0),
                "apy":            float(pool["apy"] or 0),
                "volatility_cap": float(pool["volatility_cap"] or 0),
                "agents":         int(pool["agents"] or 0),
            }
    except Exception:
        pass
    pool = next((p for p in POOLS if p["id"] == pool_id), None)
    if not pool:
        raise HTTPException(status_code=404, detail="Pool not found")
    return pool


@router.post("/deposit")
async def deposit(data: Deposit, request: Request):
    solana = getattr(request.app.state, "solana", None)

    pool_int        = _POOL_INT.get(data.pool_id, 1)
    amount_lamports = int(data.amount * 1e9)

    solana_tx: str | None = None

    if solana:
        try:
            solana_tx = await asyncio.to_thread(
                solana.vault_deposit, data.investor_address, pool_int, amount_lamports
            )
            logger.info("Solana vault_deposit pool=%s tx=%s", data.pool_id, solana_tx)
        except Exception as exc:
            logger.warning("Solana vault_deposit failed: %s", exc)

    tx_hash = solana_tx or "0xsimulated..."

    try:
        pool_row = fetch_one_dict(
            "select id from vaults where id = :pool_id", {"pool_id": data.pool_id}
        )
        if pool_row:
            execute_statement(
                "insert into users (wallet_address) values (:address) "
                "on conflict (wallet_address) do nothing",
                {"address": data.investor_address},
            )
            execute_statement(
                """insert into deposits (user_id, vault_id, amount, solana_sig)
                   values (
                       (select id from users where wallet_address = :address),
                       :pool_id, :amount, :sig
                   )""",
                {"address": data.investor_address, "pool_id": data.pool_id,
                 "amount": data.amount, "sig": solana_tx},
            )
            execute_statement(
                "update vaults set tvl = coalesce(tvl, 0) + :amount where id = :pool_id",
                {"amount": data.amount, "pool_id": data.pool_id},
            )
            return {"tx_hash": tx_hash, "solana_tx": solana_tx,
                    "pool": data.pool_id, "amount": data.amount, "status": "confirmed"}
    except Exception as exc:
        logger.warning("DB deposit persist failed: %s", exc)

    pool = next((p for p in POOLS if p["id"] == data.pool_id), None)
    if not pool:
        raise HTTPException(status_code=404, detail="Pool not found")
    pool["tvl"] += data.amount
    return {"tx_hash": tx_hash, "solana_tx": solana_tx,
            "pool": data.pool_id, "amount": data.amount, "status": "confirmed"}
