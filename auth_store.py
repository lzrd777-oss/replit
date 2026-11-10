"""Customer auth via Supabase Auth (auto-confirm register). First user becomes admin."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

SESSION_TTL = 60 * 60 * 24 * 14  # 14 days


def _secret() -> bytes:
    raw = (
        os.environ.get("ADMIN_SESSION_SECRET")
        or os.environ.get("ADMIN_PASSWORD")
        or "hhc-admin"
    )
    return raw.encode("utf-8")


def _supabase_url() -> str:
    return (os.environ.get("SUPABASE_URL") or "").rstrip("/")


def _secret_key() -> str:
    return (
        os.environ.get("SUPABASE_SECRET_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or ""
    )


def configured() -> bool:
    return bool(_supabase_url() and _secret_key())


def _auth_request(
    method: str,
    path: str,
    *,
    body: dict | None = None,
    use_secret: bool = True,
    apikey: str | None = None,
) -> tuple[int, Any]:
    if not configured():
        raise RuntimeError("Supabase Auth is not configured")
    key = apikey or _secret_key()
    url = f"{_supabase_url()}/auth/v1/{path.lstrip('/')}"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            if not raw:
                return resp.status, None
            return resp.status, json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        err_body: Any
        try:
            err_body = json.loads(exc.read().decode("utf-8", errors="replace"))
        except Exception:  # noqa: BLE001
            err_body = {"error": str(exc)}
        return exc.code, err_body


def sign_user_token(*, user_id: str, email: str, role: str) -> str:
    exp = int(time.time()) + SESSION_TTL
    payload = f"{user_id}|{email}|{role}|{exp}"
    sig = hmac.new(_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}|{sig}"


def parse_user_token(token: str | None) -> dict | None:
    if not token:
        return None
    parts = token.split("|")
    if len(parts) != 5:
        return None
    user_id, email, role, exp_s, sig = parts
    try:
        exp = int(exp_s)
    except ValueError:
        return None
    if exp < int(time.time()):
        return None
    payload = f"{user_id}|{email}|{role}|{exp_s}"
    expected = hmac.new(_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return None
    return {"id": user_id, "email": email, "role": role, "exp": exp}


def _has_admin_user() -> bool:
    status, data = _auth_request("GET", "admin/users?page=1&per_page=100")
    if status >= 400:
        return False
    users = (data or {}).get("users") if isinstance(data, dict) else data
    if not isinstance(users, list):
        return False
    for u in users:
        meta = (u or {}).get("app_metadata") or {}
        if str(meta.get("role") or "").lower() == "admin":
            return True
    return False


def register(email: str, password: str, *, name: str = "") -> dict:
    email = (email or "").strip().lower()
    password = password or ""
    if not email or "@" not in email:
        raise ValueError("Въведете валиден имейл")
    if len(password) < 6:
        raise ValueError("Паролата трябва да е поне 6 символа")

    make_admin = not _has_admin_user()
    app_meta = {"role": "admin"} if make_admin else {"role": "customer"}
    user_meta = {"name": name.strip()} if name else {}

    status, data = _auth_request(
        "POST",
        "admin/users",
        body={
            "email": email,
            "password": password,
            "email_confirm": True,
            "app_metadata": app_meta,
            "user_metadata": user_meta,
        },
    )
    if status >= 400:
        msg = ""
        if isinstance(data, dict):
            msg = str(data.get("msg") or data.get("error_description") or data.get("error") or "")
        if "already" in msg.lower() or status == 422:
            raise ValueError("Този имейл вече е регистриран")
        raise ValueError(msg or "Регистрацията неуспешна")

    user = (data or {}).get("user") if isinstance(data, dict) and "user" in (data or {}) else data
    if not isinstance(user, dict):
        user = data if isinstance(data, dict) else {}
    uid = str(user.get("id") or "")
    role = "admin" if make_admin else "customer"
    token = sign_user_token(user_id=uid or email, email=email, role=role)
    return {"ok": True, "token": token, "user": {"id": uid, "email": email, "role": role, "is_admin": role == "admin"}}


def login(email: str, password: str) -> dict:
    email = (email or "").strip().lower()
    password = password or ""
    if not email or not password:
        raise ValueError("Въведете имейл и парола")

    # Password grant uses anon/publishable key typically; secret key also works for GoTrue.
    publishable = (
        os.environ.get("SUPABASE_PUBLISHABLE_KEY")
        or os.environ.get("SUPABASE_ANON_KEY")
        or _secret_key()
    )
    status, data = _auth_request(
        "POST",
        "token?grant_type=password",
        body={"email": email, "password": password},
        apikey=publishable,
    )
    if status >= 400:
        raise ValueError("Грешен имейл или парола")

    user = (data or {}).get("user") if isinstance(data, dict) else {}
    if not isinstance(user, dict):
        user = {}
    meta = user.get("app_metadata") or {}
    role = str(meta.get("role") or "customer")
    uid = str(user.get("id") or "")
    token = sign_user_token(user_id=uid or email, email=email, role=role)
    return {
        "ok": True,
        "token": token,
        "user": {"id": uid, "email": email, "role": role, "is_admin": role == "admin"},
    }


def session_from_token(token: str | None) -> dict | None:
    parsed = parse_user_token(token)
    if not parsed:
        return None
    return {
        "ok": True,
        "user": {
            "id": parsed["id"],
            "email": parsed["email"],
            "role": parsed["role"],
            "is_admin": parsed["role"] == "admin",
        },
    }


def is_admin_token(token: str | None) -> bool:
    parsed = parse_user_token(token)
    return bool(parsed and parsed.get("role") == "admin")
