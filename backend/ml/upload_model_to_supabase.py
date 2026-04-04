from __future__ import annotations

import json
import os
from pathlib import Path
from urllib import request

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"
MODEL_PATH = PROJECT_ROOT / "backend" / "ml" / "model.pkl"
BUCKET_NAME = "models"
OBJECT_PATH = "model.pkl"

def load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)

def supabase_headers(token: str, content_type: str | None = None) -> dict[str, str]:
    headers = {
        "apikey": token,
        "Authorization": f"Bearer {token}",
    }
    if content_type:
        headers["Content-Type"] = content_type
    return headers

def api_request(url: str, token: str, method: str = "GET", data: bytes | None = None, content_type: str | None = None) -> bytes:
    req = request.Request(url, method=method, data=data, headers=supabase_headers(token, content_type))
    with request.urlopen(req) as response:
        return response.read()

def ensure_bucket(base_url: str, token: str, bucket_name: str) -> None:
    existing = json.loads(api_request(f"{base_url}/storage/v1/bucket", token=token).decode("utf-8"))
    if any(bucket.get("id") == bucket_name for bucket in existing if isinstance(bucket, dict)):
        return

    api_request(
        f"{base_url}/storage/v1/bucket",
        token=token,
        method="POST",
        data=json.dumps({"id": bucket_name, "name": bucket_name, "public": False}).encode("utf-8"),
        content_type="application/json",
    )

def main() -> None:
    load_dotenv(ENV_PATH)

    supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    supabase_token = os.environ.get("SUPABASE_SECRET_KEY") or os.environ.get("SUPABASE_KEY", "")

    if not supabase_url or not supabase_token:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SECRET_KEY in the environment.")
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"File not found: {MODEL_PATH}")

    ensure_bucket(supabase_url, supabase_token, BUCKET_NAME)

    object_url = f"{supabase_url}/storage/v1/object/{BUCKET_NAME}/{OBJECT_PATH}"
    upload_request = request.Request(
        object_url,
        method="POST",
        data=MODEL_PATH.read_bytes(),
        headers={
            **supabase_headers(supabase_token, "application/octet-stream"),
            "x-upsert": "true",
        },
    )

    with request.urlopen(upload_request) as response:
        payload = json.loads(response.read().decode("utf-8"))

    print(f"Uploaded {MODEL_PATH} to {payload.get('Key', f'{BUCKET_NAME}/{OBJECT_PATH}')}")

if __name__ == "__main__":
    main()
