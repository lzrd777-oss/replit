"""Vercel route: /api/admin-page — serve admin UI or custom 404."""

from __future__ import annotations

import os
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import supabase_client  # noqa: F401
except Exception:
    pass

import admin_store
import auth_store


def _cookie(handler: BaseHTTPRequestHandler, name: str) -> str | None:
    cookie = handler.headers.get("Cookie", "")
    prefix = f"{name}="
    for part in cookie.split(";"):
        part = part.strip()
        if part.startswith(prefix):
            return part.split("=", 1)[1].strip() or None
    return None


def _authorized(handler: BaseHTTPRequestHandler) -> bool:
    admin_token = _cookie(handler, "hhc_admin")
    if admin_token and admin_store.valid_session(admin_token):
        return True
    auth = handler.headers.get("Authorization", "")
    if auth.lower().startswith("bearer ") and admin_store.valid_session(auth[7:].strip()):
        return True
    return auth_store.is_admin_token(_cookie(handler, "hhc_user"))


def _send_html(handler: BaseHTTPRequestHandler, status: int, path: Path) -> None:
    body = path.read_bytes() if path.is_file() else b"Not found"
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


class handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def do_GET(self):  # noqa: N802
        if _authorized(self):
            _send_html(self, 200, ROOT / "admin" / "app.html")
        else:
            _send_html(self, 404, ROOT / "404.html")

    def do_OPTIONS(self):  # noqa: N802
        self.send_response(204)
        self.end_headers()
