from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from core.settings import settings

_SUPABASE_TIMEOUT = 8.0


def _project_ref_from_url(url: str) -> str:
    host = url.removeprefix("https://").removeprefix("http://").split("/")[0]
    return host.split(".")[0] if host else ""


def _uses_supabase_database(database_url: str) -> bool:
    return "supabase.co" in database_url or "pooler.supabase.com" in database_url


def _service_headers() -> dict[str, str]:
    token = settings.supabase_secret_key or settings.supabase_publishable_key
    if not settings.supabase_url or not token:
        raise RuntimeError("Supabase is not configured. Set SUPABASE_URL and SUPABASE_SECRET_KEY.")

    return {
        "apikey": token,
        "Authorization": f"Bearer {token}",
    }


def _auth_headers() -> dict[str, str]:
    token = settings.supabase_publishable_key or settings.supabase_secret_key
    if not settings.supabase_url or not token:
        raise RuntimeError("Supabase is not configured. Set SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY.")

    return {"apikey": token}


def get_supabase_status() -> dict[str, Any]:
    configured = bool(settings.supabase_url and (settings.supabase_secret_key or settings.supabase_publishable_key))
    status = {
        "configured": configured,
        "project_url": settings.supabase_url,
        "project_ref": _project_ref_from_url(settings.supabase_url),
        "using_supabase_database": _uses_supabase_database(settings.database_url),
        "auth_reachable": False,
        "storage_reachable": False,
        "error": None,
    }

    if not configured:
        status["error"] = "Missing SUPABASE_URL or SUPABASE credentials."
        return status

    base_url = settings.supabase_url.rstrip("/")

    try:
        with httpx.Client(timeout=_SUPABASE_TIMEOUT, follow_redirects=True) as client:
            auth_response = client.get(f"{base_url}/auth/v1/settings", headers=_auth_headers())
            auth_response.raise_for_status()

            storage_response = client.get(f"{base_url}/storage/v1/bucket", headers=_service_headers())
            storage_response.raise_for_status()

        status["auth_reachable"] = True
        status["storage_reachable"] = True
        return status
    except httpx.HTTPStatusError as exc:
        status["error"] = f"Supabase returned {exc.response.status_code} for {exc.request.url.path}"
        return status
    except httpx.HTTPError as exc:
        status["error"] = str(exc)
        return status


def fetch_table_rows(table_name: str, limit: int = 20) -> list[dict[str, Any]]:
    if not table_name.strip():
        raise RuntimeError("A Supabase table name is required.")

    base_url = settings.supabase_url.rstrip("/")
    table_path = quote(table_name.strip(), safe="")
    params = {"select": "*", "limit": str(limit)}

    with httpx.Client(timeout=_SUPABASE_TIMEOUT, follow_redirects=True) as client:
        response = client.get(
            f"{base_url}/rest/v1/{table_path}",
            headers=_service_headers(),
            params=params,
        )
        response.raise_for_status()
        data = response.json()

    if not isinstance(data, list):
        raise RuntimeError("Supabase returned an unexpected response shape.")

    return data
