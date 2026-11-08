"""Serve the imported website and the HHC STORE admin panel."""

from __future__ import annotations

import json
import mimetypes
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

import admin_store

ROOT = Path(__file__).resolve().parent
PUBLIC_DIRECTORIES = {"_next", "bg", "brand", "storage", "admin", "checkout"}
PUBLIC_FILES = {
    "index.html",
    "hhc-store-logo.svg",
    "icon.svg",
    "age-gate.js",
    "storefront-bridge.js",
    "cart.js",
}
CHECKOUT_PATHS = {
    "/bg/kosik",
    "/bg/kosik.html",
    "/kosik",
    "/kosik.html",
    "/checkout",
    "/checkout/",
    "/bg/checkout",
    "/bg/checkout.html",
}


def _json_bytes(payload: object, status: int = 200) -> tuple[int, bytes, str]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return status, body, "application/json; charset=utf-8"


class WebsiteHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def _token(self) -> str | None:
        cookie = self.headers.get("Cookie", "")
        for part in cookie.split(";"):
            part = part.strip()
            if part.startswith("hhc_admin="):
                return part.split("=", 1)[1].strip() or None
        auth = self.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            return auth[7:].strip() or None
        return None

    def _require_admin(self) -> bool:
        return admin_store.valid_session(self._token())

    def _send(self, status: int, body: bytes, content_type: str, extra_headers: dict | None = None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def do_OPTIONS(self):
        path = unquote(urlsplit(self.path).path)
        if path.startswith("/api/admin") or path.startswith("/api/orders"):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.end_headers()
            return
        self.send_error(404)

    def do_GET(self):
        path = unquote(urlsplit(self.path).path)
        if path.startswith("/api/admin"):
            return self._handle_admin_api("GET", path)
        if path in {"/api/catalog", "/api/catalog.json"}:
            try:
                import storefront_sync

                payload = storefront_sync.build_catalog_payload(admin_store.list_products())
                status, body, ctype = _json_bytes(payload)
                self._send(status, body, ctype)
            except Exception:
                catalog = ROOT / "storage" / "catalog.json"
                if not catalog.is_file():
                    self.send_error(404)
                    return
                body = catalog.read_bytes()
                self._send(200, body, "application/json; charset=utf-8")
            return
        if path in CHECKOUT_PATHS:
            return self._serve_checkout()
        if path in {"/admin", "/admin/"}:
            return self._serve_admin_index()
        return super().do_GET()

    def do_POST(self):
        path = unquote(urlsplit(self.path).path)
        if path.startswith("/api/admin"):
            return self._handle_admin_api("POST", path)
        if path == "/api/orders":
            return self._handle_public_order()
        self.send_error(404)

    def do_PUT(self):
        path = unquote(urlsplit(self.path).path)
        if path.startswith("/api/admin"):
            return self._handle_admin_api("PUT", path)
        self.send_error(404)

    def do_PATCH(self):
        path = unquote(urlsplit(self.path).path)
        if path.startswith("/api/admin"):
            return self._handle_admin_api("PATCH", path)
        self.send_error(404)

    def do_DELETE(self):
        path = unquote(urlsplit(self.path).path)
        if path.startswith("/api/admin"):
            return self._handle_admin_api("DELETE", path)
        self.send_error(404)

    def _serve_admin_index(self):
        index = ROOT / "admin" / "index.html"
        if not index.is_file():
            self.send_error(404, "Admin UI missing")
            return
        body = index.read_bytes()
        self._send(200, body, "text/html; charset=utf-8")

    def _serve_checkout(self):
        index = ROOT / "checkout" / "index.html"
        if not index.is_file():
            self.send_error(404, "Checkout missing")
            return
        body = index.read_bytes()
        self._send(200, body, "text/html; charset=utf-8")

    def _handle_public_order(self):
        try:
            data = self._read_json()
            order = admin_store.create_order(data)
            status, body, ctype = _json_bytes({"ok": True, "order": order}, 201)
            self._send(status, body, ctype)
        except ValueError as exc:
            status, body, ctype = _json_bytes({"ok": False, "error": str(exc)}, 400)
            self._send(status, body, ctype)
        except Exception as exc:  # noqa: BLE001
            status, body, ctype = _json_bytes({"ok": False, "error": str(exc)}, 500)
            self._send(status, body, ctype)

    def _handle_admin_api(self, method: str, path: str):
        try:
            if path == "/api/admin/login" and method == "POST":
                data = self._read_json()
                token = admin_store.login(str(data.get("password") or ""))
                if not token:
                    status, body, ctype = _json_bytes({"ok": False, "error": "Грешна парола"}, 401)
                    self._send(status, body, ctype)
                    return
                status, body, ctype = _json_bytes({"ok": True})
                self._send(
                    status,
                    body,
                    ctype,
                    {
                        "Set-Cookie": (
                            f"hhc_admin={token}; Path=/; Max-Age={admin_store.SESSION_TTL}; "
                            "HttpOnly; SameSite=Lax"
                        )
                    },
                )
                return

            if path == "/api/admin/logout" and method == "POST":
                admin_store.logout(self._token())
                status, body, ctype = _json_bytes({"ok": True})
                self._send(
                    status,
                    body,
                    ctype,
                    {"Set-Cookie": "hhc_admin=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"},
                )
                return

            if path == "/api/admin/session" and method == "GET":
                ok = self._require_admin()
                status, body, ctype = _json_bytes({"ok": ok})
                self._send(status, body, ctype)
                return

            if not self._require_admin():
                status, body, ctype = _json_bytes({"ok": False, "error": "Unauthorized"}, 401)
                self._send(status, body, ctype)
                return

            if path == "/api/admin/stats" and method == "GET":
                status, body, ctype = _json_bytes(admin_store.stats())
                self._send(status, body, ctype)
                return

            if path == "/api/admin/products" and method == "GET":
                status, body, ctype = _json_bytes({"products": admin_store.list_products()})
                self._send(status, body, ctype)
                return

            if path == "/api/admin/products" and method == "POST":
                data = self._read_json()
                product = admin_store.upsert_product(data)
                status, body, ctype = _json_bytes({"product": product}, 201)
                self._send(status, body, ctype)
                return

            if path == "/api/admin/products/archive-all" and method == "POST":
                n = admin_store.archive_all()
                status, body, ctype = _json_bytes({"ok": True, "count": n})
                self._send(status, body, ctype)
                return

            if path == "/api/admin/products/restore-all" and method == "POST":
                n = admin_store.restore_all()
                status, body, ctype = _json_bytes({"ok": True, "count": n})
                self._send(status, body, ctype)
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
                    self._send(status, body, ctype)
                    return

                if method in {"PUT", "PATCH"} and not action:
                    data = self._read_json()
                    data["id"] = product_id
                    product = admin_store.upsert_product(data, product_id)
                    status, body, ctype = _json_bytes({"product": product})
                    self._send(status, body, ctype)
                    return

                if method == "DELETE" and not action:
                    ok = admin_store.delete_product(product_id)
                    status, body, ctype = _json_bytes(
                        {"ok": ok}, 200 if ok else 404
                    )
                    self._send(status, body, ctype)
                    return

                if action == "archive" and method == "POST":
                    product = admin_store.set_archived(product_id, True)
                    if not product:
                        status, body, ctype = _json_bytes({"error": "Not found"}, 404)
                    else:
                        status, body, ctype = _json_bytes({"product": product})
                    self._send(status, body, ctype)
                    return

                if action == "restore" and method == "POST":
                    product = admin_store.set_archived(product_id, False)
                    if not product:
                        status, body, ctype = _json_bytes({"error": "Not found"}, 404)
                    else:
                        status, body, ctype = _json_bytes({"product": product})
                    self._send(status, body, ctype)
                    return

                if action == "stock" and method == "POST":
                    data = self._read_json()
                    product = admin_store.get_product(product_id)
                    if not product:
                        status, body, ctype = _json_bytes({"error": "Not found"}, 404)
                        self._send(status, body, ctype)
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
                    self._send(status, body, ctype)
                    return

            if path == "/api/admin/orders" and method == "GET":
                status, body, ctype = _json_bytes({"orders": admin_store.list_orders()})
                self._send(status, body, ctype)
                return

            if path.startswith("/api/admin/orders/") and method == "POST":
                rest = path[len("/api/admin/orders/") :]
                parts = rest.split("/")
                order_id = unquote(parts[0])
                if len(parts) >= 2 and parts[1] == "status":
                    data = self._read_json()
                    order = admin_store.set_order_status(
                        order_id, str(data.get("status") or "")
                    )
                    if not order:
                        status, body, ctype = _json_bytes({"error": "Not found"}, 404)
                    else:
                        status, body, ctype = _json_bytes({"order": order})
                    self._send(status, body, ctype)
                    return

            status, body, ctype = _json_bytes({"error": "Not found"}, 404)
            self._send(status, body, ctype)
        except ValueError as exc:
            status, body, ctype = _json_bytes({"error": str(exc)}, 400)
            self._send(status, body, ctype)
        except Exception as exc:  # noqa: BLE001
            status, body, ctype = _json_bytes({"error": str(exc)}, 500)
            self._send(status, body, ctype)

    def send_head(self):
        path = unquote(urlsplit(self.path).path)
        if path in {"/", "/bg", "/bg/", "/bg.html"}:
            path = "/index.html"
        # Clean URLs: /bg/produkt/foo → /bg/produkt/foo.html
        if (
            path.startswith("/bg/")
            and not path.endswith(".html")
            and "." not in Path(path).name
        ):
            html_candidate = ROOT / (path.lstrip("/") + ".html")
            if html_candidate.is_file():
                path = path + ".html"
        if path in CHECKOUT_PATHS:
            index = ROOT / "checkout" / "index.html"
            if not index.is_file():
                self.send_error(404, "Checkout missing")
                return None
            content = index.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-cache")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            return BytesIO(content)
        if path.startswith("/admin/"):
            candidate = (ROOT / path.lstrip("/")).resolve()
            try:
                candidate.relative_to(ROOT / "admin")
            except ValueError:
                self.send_error(404)
                return None
            if candidate.is_file():
                self.path = "/" + candidate.relative_to(ROOT).as_posix()
                return SimpleHTTPRequestHandler.send_head(self)
            self.send_error(404)
            return None

        candidate = (ROOT / path.lstrip("/")).resolve()
        try:
            relative = candidate.relative_to(ROOT)
        except ValueError:
            self.send_error(404)
            return None
        if not relative.parts or (
            relative.parts[0] not in PUBLIC_DIRECTORIES
            and relative.as_posix() not in PUBLIC_FILES
        ) or any(part.startswith(".") for part in relative.parts):
            self.send_error(404)
            return None
        if not candidate.is_file() and not candidate.suffix:
            candidate = candidate.with_suffix(".html")
        if not candidate.is_file():
            self.send_error(404, "This file was not included in the website import.")
            return None

        # Hide archived / removed products from the public shop.
        if (
            len(relative.parts) >= 3
            and relative.parts[0] == "bg"
            and relative.parts[1] == "produkt"
            and candidate.suffix == ".html"
        ):
            product_id = candidate.stem
            product = admin_store.get_product(product_id)
            if product is None or product.get("archived"):
                self.send_error(404, "Product is archived or removed.")
                return None

        if candidate.suffix == ".html":
            content = candidate.read_bytes().replace(
                b"</body>",
                b'<script src="/storefront-bridge.js" defer></script>'
                b'<script src="/cart.js" defer></script>'
                b'<script src="/age-gate.js" defer></script></body>',
            )
            if (
                candidate == ROOT / "index.html"
                and parse_qs(urlsplit(self.path).query).get("age_confirmed") == ["1"]
            ):
                content = content.replace(
                    b"</head>",
                    b'<script>document.documentElement.removeAttribute("data-age-gate");</script></head>',
                )
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-cache")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            return BytesIO(content)
        self.path = "/" + candidate.relative_to(ROOT).as_posix()
        return super().send_head()

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def log_message(self, format: str, *args):  # noqa: A003
        # Keep admin API noise readable
        print("%s - %s" % (self.address_string(), format % args), flush=True)


if __name__ == "__main__":
    admin_store.ensure_seed_data()
    mimetypes.add_type("application/javascript", ".js")
    mimetypes.add_type("text/css", ".css")
    server = ThreadingHTTPServer(("0.0.0.0", 5000), WebsiteHandler)
    print("Imported website + admin running on port 5000", flush=True)
    print("Admin: http://127.0.0.1:5000/admin  (password: hhc-admin)", flush=True)
    server.serve_forever()
