"""Minimal Supabase PostgREST client (no external deps)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent


def _load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        os.environ.setdefault(key, val)


_load_dotenv()

SUPABASE_URL = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
SUPABASE_SECRET_KEY = (
    os.environ.get("SUPABASE_SECRET_KEY")
    or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or ""
)
SUPABASE_PUBLISHABLE_KEY = (
    os.environ.get("SUPABASE_PUBLISHABLE_KEY")
    or os.environ.get("SUPABASE_ANON_KEY")
    or ""
)


def configured() -> bool:
    return bool(SUPABASE_URL and SUPABASE_SECRET_KEY)


class SupabaseError(RuntimeError):
    def __init__(self, message: str, status: int = 0, body: str = ""):
        super().__init__(message)
        self.status = status
        self.body = body


def _request(
    method: str,
    path: str,
    *,
    params: dict[str, str] | None = None,
    body: Any = None,
    prefer: str | None = None,
    key: str | None = None,
) -> Any:
    if not configured():
        raise SupabaseError("Supabase is not configured (missing URL or secret key)")
    api_key = key or SUPABASE_SECRET_KEY
    query = f"?{urllib.parse.urlencode(params)}" if params else ""
    url = f"{SUPABASE_URL}/rest/v1/{path.lstrip('/')}{query}"
    headers = {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            if not raw:
                return None
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        err_body = ""
        try:
            err_body = exc.read().decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass
        raise SupabaseError(
            f"Supabase {method} {path} failed: {exc.code} {err_body}",
            status=exc.code,
            body=err_body,
        ) from exc


def select(
    table: str,
    *,
    columns: str = "*",
    filters: dict[str, str] | None = None,
    order: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    params: dict[str, str] = {"select": columns}
    if filters:
        params.update(filters)
    if order:
        params["order"] = order
    if limit is not None:
        params["limit"] = str(limit)
    data = _request("GET", table, params=params)
    return data or []


def insert(table: str, rows: dict | list[dict], *, upsert: bool = False) -> list[dict]:
    prefer = "return=representation"
    if upsert:
        prefer += ",resolution=merge-duplicates"
    data = _request("POST", table, body=rows, prefer=prefer)
    return data or []


def upsert(table: str, rows: dict | list[dict], *, on_conflict: str = "id") -> list[dict]:
    prefer = f"return=representation,resolution=merge-duplicates"
    params = {"on_conflict": on_conflict}
    data = _request("POST", table, params=params, body=rows, prefer=prefer)
    return data or []


def update(table: str, filters: dict[str, str], patch: dict) -> list[dict]:
    data = _request(
        "PATCH",
        table,
        params={**filters, "select": "*"},
        body=patch,
        prefer="return=representation",
    )
    return data or []


def delete(table: str, filters: dict[str, str]) -> None:
    _request("DELETE", table, params=filters, prefer="return=minimal")


def tables_ready() -> bool:
    """True when products + orders endpoints exist."""
    try:
        select("products", columns="id", limit=1)
        select("orders", columns="id", limit=1)
        return True
    except SupabaseError as exc:
        if exc.status in {404, 406}:
            return False
        # Missing table often returns 404 PGRST205
        if "PGRST" in (exc.body or "") or "Could not find" in (exc.body or ""):
            return False
        raise
