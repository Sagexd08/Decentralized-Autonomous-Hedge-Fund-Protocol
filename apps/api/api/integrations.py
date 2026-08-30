import httpx
from fastapi import APIRouter, HTTPException, Query

from core.supabase import fetch_table_rows, get_supabase_status

router = APIRouter()

@router.get("/supabase/status")
def supabase_status():
    return get_supabase_status()

@router.get("/supabase/table/{table_name}")
def supabase_table_rows(table_name: str, limit: int = Query(default=20, ge=1, le=200)):
    try:
        rows = fetch_table_rows(table_name, limit=limit)
        return {
            "table": table_name,
            "count": len(rows),
            "data": rows,
        }
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text.strip() or exc.response.reason_phrase
        raise HTTPException(
            status_code=502,
            detail=f"Supabase returned {exc.response.status_code}: {detail}",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
