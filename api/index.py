"""Vercel Python serverless API (no framework preset — keeps static files)."""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import supabase_client  # noqa: F401 — loads .env locally
except Exception:
    pass

import admin_store
import storefront_sync


def _json_bytes(payload: Any, status: int = 200) -> tuple[int, bytes, str]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return status, body, "application/json; charset=utf-8"


def _read_json(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length") or 0)
    raw = handler.rfile.read(length) if length else b"{}"
    if not raw:
        return {}
    try:
        data = json.loads(raw.decode("utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _token(handler: BaseHTTPRequestHandler) -> str | None:
    cookie = handler.headers.get("Cookie", "")
    for part in cookie.split(";"):
        part = part.strip()
        if part.startswith("hhc_admin="):
            return part.split("=", 1)[1].strip() or None
    auth = handler.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    return None


def _send(
    handler: BaseHTTPRequestHandler,
    status: int,
    body: bytes,
    content_type: str,
    extra_headers: dict[str, str] | None = None,
) -> None:
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Credentials", "true")
    if extra_headers:
        for k, v in extra_headers.items():
            handler.send_header(k, v)
    handler.end_headers()
    handler.wfile.write(body)


def _dispatch(handler: BaseHTTPRequestHandler, method: str) -> None:
    path = unquote(urlsplit(handler.path).path)
    if not path.startswith("/api"):
        # Rewrite destination may leave path as /index or /
        path = "/api" + (path if path.startswith("/") else f"/{path}")
    if path in {"/api", "/api/"}:
        status, body, ctype = _json_bytes({"ok": True, "service": "hhc-store-api"})
        _send(handler, status, body, ctype)
        return

    try:
        if path in {"/api/catalog", "/api/catalog.json"} and method == "GET":
            payload = storefront_sync.build_catalog_payload(admin_store.list_products())
            status, body, ctype = _json_bytes(payload)
            _send(handler, status, body, ctype)
            return

        if path == "/api/orders" and method == "POST":
            order = admin_store.create_order(_read_json(handler))
            status, body, ctype = _json_bytes({"ok": True, "order": order}, 201)
            _send(handler, status, body, ctype)
            return

        if path == "/api/admin/login" and method == "POST":
            data = _read_json(handler)
            token = admin_store.login(str(data.get("password") or ""))
            if not token:
                status, body, ctype = _json_bytes({"ok": False, "error": "Грешна парола"}, 401)
                _send(handler, status, body, ctype)
                return
            secure = "; Secure" if os.environ.get("VERCEL") == "1" else ""
            status, body, ctype = _json_bytes({"ok": True})
            _send(
                handler,
                status,
                body,
                ctype,
                {
                    "Set-Cookie": (
                        f"hhc_admin={token}; Path=/; Max-Age={admin_store.SESSION_TTL}; "
                        f"HttpOnly; SameSite=Lax{secure}"
                    )
                },
            )
            return

        if path == "/api/admin/logout" and method == "POST":
            admin_store.logout(_token(handler))
            status, body, ctype = _json_bytes({"ok": True})
            _send(
                handler,
                status,
                body,
                ctype,
                {"Set-Cookie": "hhc_admin=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"},
            )
            return

        if path == "/api/admin/session" and method == "GET":
            status, body, ctype = _json_bytes({"ok": admin_store.valid_session(_token(handler))})
            _send(handler, status, body, ctype)
            return

        if not path.startswith("/api/admin"):
            status, body, ctype = _json_bytes({"error": "Not found"}, 404)
            _send(handler, status, body, ctype)
            return

        if not admin_store.valid_session(_token(handler)):
            status, body, ctype = _json_bytes({"ok": False, "error": "Unauthorized"}, 401)
            _send(handler, status, body, ctype)
            return

        if path == "/api/admin/stats" and method == "GET":
            status, body, ctype = _json_bytes(admin_store.stats())
            _send(handler, status, body, ctype)
            return

        if path == "/api/admin/products" and method == "GET":
            status, body, ctype = _json_bytes({"products": admin_store.list_products()})
            _send(handler, status, body, ctype)
            return

        if path == "/api/admin/products" and method == "POST":
            product = admin_store.upsert_product(_read_json(handler))
            status, body, ctype = _json_bytes({"product": product}, 201)
            _send(handler, status, body, ctype)
            return

        if path == "/api/admin/products/archive-all" and method == "POST":
            n = admin_store.archive_all()
            status, body, ctype = _json_bytes({"ok": True, "count": n})
            _send(handler, status, body, ctype)
            return

        if path == "/api/admin/products/restore-all" and method == "POST":
            n = admin_store.restore_all()
            status, body, ctype = _json_bytes({"ok": True, "count": n})
            _send(handler, status, body, ctype)
            return

        if path.startswith("/api/admin/products/"):
            rest = path[len("/api/admin/products/") :]
            parts = rest.split("/")
            product_id = unquote(parts[0])
            action = parts[1] if len(parts) > 1 else None

            if method == "GET" and not action:
                product = admin_store.get_product(product_id)
                if not product:
                    status, body, ctype = _json_bytes({"error": "Not found"}, 404)
                else:
                    status, body, ctype = _json_bytes({"product": product})
                _send(handler, status, body, ctype)
                return

            if method in {"PUT", "PATCH"} and not action:
                data = _read_json(handler)
                data["id"] = product_id
                product = admin_store.upsert_product(data, product_id)
                status, body, ctype = _json_bytes({"product": product})
                _send(handler, status, body, ctype)
                return

            if method == "DELETE" and not action:
                ok = admin_store.delete_product(product_id)
                status, body, ctype = _json_bytes({"ok": ok}, 200 if ok else 404)
                _send(handler, status, body, ctype)
                return

            if action == "archive" and method == "POST":
                product = admin_store.set_archived(product_id, True)
                status, body, ctype = (
                    _json_bytes({"error": "Not found"}, 404)
                    if not product
                    else _json_bytes({"product": product})
                )
                _send(handler, status, body, ctype)
                return

            if action == "restore" and method == "POST":
                product = admin_store.set_archived(product_id, False)
                status, body, ctype = (
                    _json_bytes({"error": "Not found"}, 404)
                    if not product
                    else _json_bytes({"product": product})
                )
                _send(handler, status, body, ctype)
                return

            if action == "stock" and method == "POST":
                data = _read_json(handler)
                product = admin_store.get_product(product_id)
                if not product:
                    status, body, ctype = _json_bytes({"error": "Not found"}, 404)
                    _send(handler, status, body, ctype)
                    return
                in_stock = bool(data.get("in_stock"))
                product = admin_store.upsert_product(
                    {
                        **product,
                        "in_stock": in_stock,
                        "stock_text": data.get("stock_text")
                        or ("В наличност (5+ бр.)" if in_stock else "Изчерпан"),
                    },
                    product_id,
                )
                status, body, ctype = _json_bytes({"product": product})
                _send(handler, status, body, ctype)
                return

        if path == "/api/admin/orders" and method == "GET":
            status, body, ctype = _json_bytes({"orders": admin_store.list_orders()})
            _send(handler, status, body, ctype)
            return

        if path.startswith("/api/admin/orders/") and method == "POST":
            rest = path[len("/api/admin/orders/") :]
            parts = rest.split("/")
            order_id = unquote(parts[0])
            if len(parts) >= 2 and parts[1] == "status":
                data = _read_json(handler)
                order = admin_store.set_order_status(order_id, str(data.get("status") or ""))
                status, body, ctype = (
                    _json_bytes({"error": "Not found"}, 404)
                    if not order
                    else _json_bytes({"order": order})
                )
                _send(handler, status, body, ctype)
                return

        status, body, ctype = _json_bytes({"error": "Not found"}, 404)
        _send(handler, status, body, ctype)
    except ValueError as exc:
        status, body, ctype = _json_bytes({"error": str(exc)}, 400)
        _send(handler, status, body, ctype)
    except Exception as exc:  # noqa: BLE001
        status, body, ctype = _json_bytes({"error": str(exc)}, 500)
        _send(handler, status, body, ctype)


class handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def do_OPTIONS(self):  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Credentials", "true")
        self.end_headers()

    def do_GET(self):  # noqa: N802
        _dispatch(self, "GET")

    def do_POST(self):  # noqa: N802
        _dispatch(self, "POST")

    def do_PUT(self):  # noqa: N802
        _dispatch(self, "PUT")

    def do_PATCH(self):  # noqa: N802
        _dispatch(self, "PATCH")

    def do_DELETE(self):  # noqa: N802
        _dispatch(self, "DELETE")
