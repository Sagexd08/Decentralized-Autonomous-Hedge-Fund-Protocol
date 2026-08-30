from __future__ import annotations

from pathlib import Path
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

def ensure_storage_bucket(bucket_name: str, public: bool = False) -> dict[str, Any]:
    if not bucket_name.strip():
        raise RuntimeError("A Supabase storage bucket name is required.")

    base_url = settings.supabase_url.rstrip("/")

    with httpx.Client(timeout=_SUPABASE_TIMEOUT, follow_redirects=True) as client:
        response = client.get(f"{base_url}/storage/v1/bucket", headers=_service_headers())
        response.raise_for_status()
        buckets = response.json()

        if any(bucket.get("id") == bucket_name for bucket in buckets if isinstance(bucket, dict)):
            return {"id": bucket_name, "created": False}

        create_response = client.post(
            f"{base_url}/storage/v1/bucket",
            headers={**_service_headers(), "Content-Type": "application/json"},
            json={"id": bucket_name, "name": bucket_name, "public": public},
        )
        create_response.raise_for_status()
        created_bucket = create_response.json()

    return {"id": created_bucket.get("id", bucket_name), "created": True}

def upload_storage_bytes(
    bucket_name: str,
    object_path: str,
    data: bytes,
    content_type: str = "application/octet-stream",
    upsert: bool = True,
) -> dict[str, Any]:
    if not object_path.strip():
        raise RuntimeError("A Supabase storage object path is required.")

    ensure_storage_bucket(bucket_name)
    base_url = settings.supabase_url.rstrip("/")
    object_key = quote(object_path.strip(), safe="/")

    headers = {
        **_service_headers(),
        "Content-Type": content_type,
        "x-upsert": "true" if upsert else "false",
    }

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        response = client.post(
            f"{base_url}/storage/v1/object/{bucket_name}/{object_key}",
            headers=headers,
            content=data,
        )
        response.raise_for_status()
        payload = response.json()

    return {
        "bucket": bucket_name,
        "path": object_path,
        "key": payload.get("Key") or payload.get("key") or f"{bucket_name}/{object_path}",
    }

def upload_storage_file(
    local_path: str | Path,
    bucket_name: str,
    object_path: str,
    content_type: str = "application/octet-stream",
    upsert: bool = True,
) -> dict[str, Any]:
    path = Path(local_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    return upload_storage_bytes(
        bucket_name=bucket_name,
        object_path=object_path,
        data=path.read_bytes(),
        content_type=content_type,
        upsert=upsert,
    )

def download_storage_file(bucket_name: str, object_path: str, destination: str | Path) -> Path:
    if not object_path.strip():
        raise RuntimeError("A Supabase storage object path is required.")

    base_url = settings.supabase_url.rstrip("/")
    object_key = quote(object_path.strip(), safe="/")
    dest = Path(destination)
    dest.parent.mkdir(parents=True, exist_ok=True)

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        response = client.get(
            f"{base_url}/storage/v1/object/{bucket_name}/{object_key}",
            headers=_service_headers(),
        )
        response.raise_for_status()
        dest.write_bytes(response.content)

    return dest
