"""Store for admin products and orders — Supabase when configured, else JSON files."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
PRODUCTS_PATH = DATA / "products.json"
ORDERS_PATH = DATA / "orders.json"

ORDER_STATUSES = ("new_order", "in_process", "shipped", "declined")
STATUS_LABELS_BG = {
    "new_order": "ЧАКАЩА",
    "in_process": "ПРИЕТА",
    "shipped": "ИЗПЪЛНЕНА",
    "declined": "ОТКАЗАНА",
}

_lock = threading.RLock()
_sessions: dict[str, float] = {}  # local/dev fallback only
SESSION_TTL = 60 * 60 * 12

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "hhc-admin")


def _admin_password() -> str:
    return os.environ.get("ADMIN_PASSWORD") or ADMIN_PASSWORD or "hhc-admin"


def _session_secret() -> bytes:
    # Prefer dedicated secret; fall back to admin password so Vercel works without new env.
    raw = os.environ.get("ADMIN_SESSION_SECRET") or _admin_password()
    return raw.encode("utf-8")


def _sign_session(exp: int, nonce: str) -> str:
    payload = f"{exp}.{nonce}"
    sig = hmac.new(_session_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def _verify_signed_session(token: str) -> bool:
    parts = token.split(".")
    if len(parts) != 3:
        return False
    exp_s, nonce, sig = parts
    try:
        exp = int(exp_s)
    except ValueError:
        return False
    if exp < int(time.time()):
        return False
    if not nonce or not sig:
        return False
    expected = hmac.new(
        _session_secret(), f"{exp_s}.{nonce}".encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, sig)

_supabase_ready: bool | None = None

PRODUCT_FIELDS = (
    "id",
    "slug",
    "title",
    "category",
    "price",
    "old_price",
    "member_price",
    "volume",
    "lab_label",
    "in_stock",
    "stock_text",
    "image",
    "archived",
    "short_description",
    "full_description",
    "sku",
    "tags",
    "specs",
    "flavors",
    "colors",
    "flavor_slots",
)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return deepcopy(default)
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def _sync_storefront(
    products: list[dict] | None = None,
    product: dict | None = None,
    deleted_id: str | None = None,
) -> None:
    try:
        import storefront_sync

        storefront_sync.after_mutation(
            products if products is not None else list_products(),
            product=product,
            deleted_id=deleted_id,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[storefront_sync] {exc}", flush=True)


def refresh_supabase_status() -> bool:
    global _supabase_ready
    _supabase_ready = None
    return use_supabase()


def use_supabase() -> bool:
    global _supabase_ready
    try:
        import supabase_client as sb
    except Exception:
        return False
    if not sb.configured():
        return False
    if _supabase_ready is None:
        try:
            _supabase_ready = sb.tables_ready()
        except Exception as exc:  # noqa: BLE001
            print(f"[supabase] tables check failed: {exc}", flush=True)
            _supabase_ready = False
    return bool(_supabase_ready)


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _product_from_row(row: dict) -> dict:
    title = row.get("title") or ""
    slots = int(row.get("flavor_slots") or 0)
    if not slots and str(title).lower().startswith("2x"):
        slots = 2
    return {
        "id": row.get("id"),
        "slug": row.get("slug") or row.get("id"),
        "title": title,
        "category": row.get("category") or "",
        "price": float(row.get("price") or 0),
        "old_price": _num(row.get("old_price")),
        "member_price": _num(row.get("member_price")),
        "volume": row.get("volume") or "",
        "lab_label": row.get("lab_label") or "",
        "in_stock": bool(row.get("in_stock")),
        "stock_text": row.get("stock_text") or "",
        "image": row.get("image") or "",
        "archived": bool(row.get("archived")),
        "short_description": row.get("short_description") or "",
        "full_description": row.get("full_description") or "",
        "sku": row.get("sku") or "",
        "tags": row.get("tags") if isinstance(row.get("tags"), list) else [],
        "specs": row.get("specs") if isinstance(row.get("specs"), dict) else {},
        "flavors": row.get("flavors") if isinstance(row.get("flavors"), list) else [],
        "colors": row.get("colors") if isinstance(row.get("colors"), list) else [],
        "flavor_slots": slots,
    }


def _product_to_row(product: dict) -> dict:
    pid = product.get("id") or product.get("slug")
    title = product.get("title") or ""
    slots = int(product.get("flavor_slots") or 0)
    if not slots and str(title).lower().startswith("2x"):
        slots = 2
    row = {
        "id": pid,
        "slug": product.get("slug") or pid,
        "title": title,
        "category": product.get("category") or "",
        "price": float(product.get("price") or 0),
        "old_price": _num(product.get("old_price")),
        "member_price": _num(product.get("member_price")),
        "volume": product.get("volume") or "",
        "lab_label": product.get("lab_label") or "",
        "in_stock": bool(product.get("in_stock")),
        "stock_text": product.get("stock_text") or "",
        "image": product.get("image") or "",
        "archived": bool(product.get("archived")),
        "short_description": product.get("short_description") or "",
        "full_description": product.get("full_description") or "",
        "sku": product.get("sku") or "",
        "tags": product.get("tags") if isinstance(product.get("tags"), list) else [],
        "specs": product.get("specs") if isinstance(product.get("specs"), dict) else {},
        "flavors": product.get("flavors") if isinstance(product.get("flavors"), list) else [],
        "colors": product.get("colors") if isinstance(product.get("colors"), list) else [],
        "flavor_slots": slots,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    return row


def _order_from_row(row: dict) -> dict:
    created = row.get("created_at") or ""
    if isinstance(created, str) and created.endswith("Z"):
        created = created.replace("Z", "")
    if isinstance(created, str) and "+" in created:
        created = created.split("+")[0]
    return {
        "id": row.get("id"),
        "created_at": created,
        "customer_name": row.get("customer_name") or "",
        "first_name": row.get("first_name") or "",
        "last_name": row.get("last_name") or "",
        "phone": row.get("phone") or "",
        "email": row.get("email") or "",
        "city": row.get("city") or "",
        "postal_code": row.get("postal_code") or "",
        "courier": row.get("courier") or "Econt",
        "delivery_type": row.get("delivery_type") or "office",
        "address": row.get("address") or "",
        "payment": row.get("payment") or "cod",
        "status": row.get("status") or "new_order",
        "items": row.get("items") if isinstance(row.get("items"), list) else [],
        "subtotal": float(row.get("subtotal") or 0),
        "discount": float(row.get("discount") or 0),
        "promo_code": row.get("promo_code") or "",
        "shipping": float(row.get("shipping") or 0),
        "total": float(row.get("total") or 0),
    }


def _order_to_row(order: dict) -> dict:
    return {
        "id": order.get("id"),
        "created_at": order.get("created_at") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "customer_name": order.get("customer_name") or "",
        "first_name": order.get("first_name") or "",
        "last_name": order.get("last_name") or "",
        "phone": order.get("phone") or "",
        "email": order.get("email") or "",
        "city": order.get("city") or "",
        "postal_code": order.get("postal_code") or "",
        "courier": order.get("courier") or "Econt",
        "delivery_type": order.get("delivery_type") or "office",
        "address": order.get("address") or "",
        "payment": order.get("payment") or "cod",
        "status": order.get("status") or "new_order",
        "items": order.get("items") if isinstance(order.get("items"), list) else [],
        "subtotal": float(order.get("subtotal") or 0),
        "discount": float(order.get("discount") or 0),
        "promo_code": order.get("promo_code") or "",
        "shipping": float(order.get("shipping") or 0),
        "total": float(order.get("total") or 0),
    }


def ensure_seed_data() -> None:
    # Load .env early
    try:
        import supabase_client  # noqa: F401
    except Exception:
        pass
    global ADMIN_PASSWORD
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", ADMIN_PASSWORD)

    DATA.mkdir(parents=True, exist_ok=True)
    if use_supabase():
        print("[store] Using Supabase for products/orders", flush=True)
        _sync_storefront(list_products())
        return

    print("[store] Using local JSON (Supabase tables not ready yet)", flush=True)
    if not PRODUCTS_PATH.exists():
        import runpy

        runpy.run_path(str(ROOT / "scripts" / "extract_products.py"), run_name="__main__")
    if not ORDERS_PATH.exists():
        products = _read_json(PRODUCTS_PATH, [])
        by_id = {p["id"]: p for p in products}
        demo_ids = [
            "thc-x-cartridge-99-og-kush-1-ml",
            "thc-x-vape-pen-99-skywalker-2-ml",
            "hxc-cartridge-99-amnesia-haze-1-ml",
            "thc-x-vape-pen-99-strawberry-2-ml",
            "ccell-palm",
            "thc-x-cartridge-99-blackberry-lemonade-1-ml",
            "2x-thc-x-cartridge-99-1-ml-ccell-rizo-palm",
        ]
        customers = [
            ("Kristian Dimitrov", "+359 877104225", "София", "Econt", "Люлин 8, офис 123"),
            ("Dragomir Dimitrov", "+359 888112233", "Пловдив", "Speedy", "Център, офис 12"),
            ("Stefan Radev", "+359 899445566", "Варна", "Econt", "Младост, офис 7"),
            ("Maria Petrova", "+359 876554433", "Бургас", "Speedy", "Лазур, офис 3"),
            ("Ivan Georgiev", "+359 885001122", "Русе", "Econt", "Център, офис 9"),
            ("Elena Nikolova", "+359 878990011", "Стара Загора", "Speedy", "Три чучура, офис 2"),
            ("Petar Stoyanov", "+359 887223344", "Плевен", "Econt", "Сторгозия, офис 5"),
        ]
        orders = []
        for i, cust in enumerate(customers):
            pid = demo_ids[i % len(demo_ids)]
            prod = by_id.get(pid) or next(iter(by_id.values()), None)
            if not prod:
                break
            qty = 2 if i % 3 == 0 else 1
            unit = float(prod.get("price") or 0)
            shipping = 4.0
            total = round(unit * qty + shipping, 2)
            orders.append(
                {
                    "id": f"HMP-{918982 - i * 17}",
                    "created_at": f"2026-11-{6 - (i % 5):02d}T{8 + i}:29:00",
                    "customer_name": cust[0],
                    "phone": cust[1],
                    "city": cust[2],
                    "courier": cust[3],
                    "address": cust[4],
                    "status": "new_order",
                    "items": [
                        {
                            "product_id": prod["id"],
                            "title": prod["title"],
                            "volume": prod.get("volume") or "",
                            "qty": qty,
                            "unit_price": unit,
                        }
                    ],
                    "shipping": shipping,
                    "total": total,
                }
            )
        _write_json(ORDERS_PATH, orders)
    _sync_storefront(list_products())


def login(password: str) -> str | None:
    if password != _admin_password():
        return None
    # Signed tokens work across Vercel serverless instances (no shared memory).
    exp = int(time.time()) + SESSION_TTL
    nonce = secrets.token_urlsafe(16)
    token = _sign_session(exp, nonce)
    with _lock:
        _sessions[token] = float(exp)
    return token


def logout(token: str | None) -> None:
    if not token:
        return
    with _lock:
        _sessions.pop(token, None)


def valid_session(token: str | None) -> bool:
    if not token:
        return False
    if _verify_signed_session(token):
        return True
    # Legacy in-memory tokens (local single-process server).
    with _lock:
        exp = _sessions.get(token)
        if not exp:
            return False
        if exp < time.time():
            _sessions.pop(token, None)
            return False
        _sessions[token] = time.time() + SESSION_TTL
        return True


def list_products() -> list[dict]:
    if use_supabase():
        import supabase_client as sb

        rows = sb.select("products", order="title.asc")
        return [_product_from_row(r) for r in rows]
    with _lock:
        return _read_json(PRODUCTS_PATH, [])


def save_products(products: list[dict]) -> None:
    if use_supabase():
        import supabase_client as sb

        rows = [_product_to_row(p) for p in products if p.get("id")]
        # Upsert in chunks
        for i in range(0, len(rows), 100):
            sb.upsert("products", rows[i : i + 100], on_conflict="id")
        return
    with _lock:
        _write_json(PRODUCTS_PATH, products)


def get_product(product_id: str) -> dict | None:
    if use_supabase():
        import supabase_client as sb

        rows = sb.select("products", filters={"id": f"eq.{product_id}"}, limit=1)
        return _product_from_row(rows[0]) if rows else None
    for p in list_products():
        if p.get("id") == product_id:
            return p
    return None


def upsert_product(product: dict, product_id: str | None = None) -> dict:
    pid = product_id or product.get("id") or product.get("slug")
    if not pid:
        raise ValueError("Product id required")
    product = {**product, "id": pid, "slug": product.get("slug") or pid}

    if use_supabase():
        import supabase_client as sb

        existing = get_product(pid) or {}
        merged = {**existing, **product, "id": pid}
        rows = sb.upsert("products", _product_to_row(merged), on_conflict="id")
        out = _product_from_row(rows[0]) if rows else _product_from_row(_product_to_row(merged))
        _sync_storefront(list_products(), product=out)
        return out

    products = list_products()
    found = False
    for i, p in enumerate(products):
        if p.get("id") == pid:
            products[i] = {**p, **product, "id": pid}
            product = products[i]
            found = True
            break
    if not found:
        products.append(product)
    save_products(products)
    _sync_storefront(products, product=product)
    return product


def delete_product(product_id: str) -> bool:
    if use_supabase():
        import supabase_client as sb

        existing = get_product(product_id)
        if not existing:
            return False
        sb.delete("products", {"id": f"eq.{product_id}"})
        _sync_storefront(list_products(), deleted_id=product_id)
        return True

    products = list_products()
    next_list = [p for p in products if p.get("id") != product_id]
    if len(next_list) == len(products):
        return False
    save_products(next_list)
    _sync_storefront(next_list, deleted_id=product_id)
    return True


def set_archived(product_id: str, archived: bool) -> dict | None:
    product = get_product(product_id)
    if not product:
        return None
    return upsert_product({**product, "archived": archived}, product_id)


def archive_all(active_only: bool = True) -> int:
    products = list_products()
    n = 0
    updated = []
    for p in products:
        if active_only and p.get("archived"):
            updated.append(p)
            continue
        if not p.get("archived"):
            updated.append({**p, "archived": True})
            n += 1
        else:
            updated.append(p)
    if n:
        save_products(updated)
        _sync_storefront(updated)
    return n


def restore_all() -> int:
    products = list_products()
    n = 0
    updated = []
    for p in products:
        if p.get("archived"):
            updated.append({**p, "archived": False})
            n += 1
        else:
            updated.append(p)
    if n:
        save_products(updated)
        _sync_storefront(updated)
    return n


def list_orders() -> list[dict]:
    if use_supabase():
        import supabase_client as sb

        rows = sb.select("orders", order="created_at.desc")
        return [_order_from_row(r) for r in rows]
    with _lock:
        return _read_json(ORDERS_PATH, [])


def save_orders(orders: list[dict]) -> None:
    if use_supabase():
        import supabase_client as sb

        rows = [_order_to_row(o) for o in orders if o.get("id")]
        for i in range(0, len(rows), 100):
            sb.upsert("orders", rows[i : i + 100], on_conflict="id")
        return
    with _lock:
        _write_json(ORDERS_PATH, orders)


def set_order_status(order_id: str, status: str) -> dict | None:
    if status not in ORDER_STATUSES:
        raise ValueError("Invalid status")
    if use_supabase():
        import supabase_client as sb

        rows = sb.update("orders", {"id": f"eq.{order_id}"}, {"status": status})
        return _order_from_row(rows[0]) if rows else None
    orders = list_orders()
    for i, o in enumerate(orders):
        if o.get("id") == order_id:
            orders[i] = {**o, "status": status}
            save_orders(orders)
            return orders[i]
    return None


def _new_order_id() -> str:
    return f"HMP-{secrets.randbelow(900000) + 100000}"


def create_order(payload: dict) -> dict:
    """Create a storefront order (cash on delivery)."""
    customer_name = " ".join(
        part
        for part in [
            str(payload.get("first_name") or "").strip(),
            str(payload.get("last_name") or "").strip(),
        ]
        if part
    ) or str(payload.get("customer_name") or "").strip()
    phone = str(payload.get("phone") or "").strip()
    city = str(payload.get("city") or "").strip()
    address = str(payload.get("address") or "").strip()
    raw_items = payload.get("items") or []
    if not customer_name:
        raise ValueError("Името е задължително")
    if not phone:
        raise ValueError("Телефонът е задължителен")
    if not city:
        raise ValueError("Градът е задължителен")
    if not address:
        raise ValueError("Адресът е задължителен")
    if not isinstance(raw_items, list) or not raw_items:
        raise ValueError("Количката е празна")

    products_by_id = {p["id"]: p for p in list_products() if p.get("id")}
    items: list[dict] = []
    subtotal = 0.0
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        pid = str(raw.get("product_id") or raw.get("id") or "").strip()
        product = products_by_id.get(pid)
        qty = min(100, max(1, int(raw.get("qty") or 1)))
        if product:
            if product.get("archived") or not product.get("in_stock"):
                raise ValueError(f"Продуктът „{product.get('title') or pid}“ не е наличен")
            unit = float(product.get("price") or 0)
            title = product.get("title") or pid
            volume = product.get("volume") or ""
        else:
            unit = float(raw.get("unit_price") or raw.get("price") or 0)
            title = str(raw.get("title") or pid or "Продукт")
            volume = str(raw.get("volume") or "")
        flavors = [str(f).strip() for f in (raw.get("flavors") or []) if str(f).strip()]
        color = str(raw.get("color") or "").strip()
        option_bits = []
        if flavors:
            option_bits.append("Вкусове: " + ", ".join(flavors))
        if color:
            option_bits.append("Цвят: " + color)
        line = {
            "product_id": pid,
            "title": title,
            "volume": volume,
            "qty": qty,
            "unit_price": round(unit, 2),
            "flavors": flavors,
            "color": color,
            "options": " · ".join(option_bits),
        }
        items.append(line)
        subtotal += unit * qty

    if not items:
        raise ValueError("Количката е празна")

    delivery_type = str(payload.get("delivery_type") or "office").strip()
    shipping = 5.0 if delivery_type == "address" else 4.0
    try:
        shipping = float(payload.get("shipping") if payload.get("shipping") is not None else shipping)
    except (TypeError, ValueError):
        pass

    promo = str(payload.get("promo_code") or "").strip().upper()
    discount = 0.0
    if promo == "VIP10":
        discount = round(subtotal * 0.1, 2)

    total = round(max(0.0, subtotal - discount) + shipping, 2)
    order = {
        "id": _new_order_id(),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "customer_name": customer_name,
        "first_name": str(payload.get("first_name") or "").strip(),
        "last_name": str(payload.get("last_name") or "").strip(),
        "phone": phone,
        "email": str(payload.get("email") or "").strip(),
        "city": city,
        "postal_code": str(payload.get("postal_code") or "").strip(),
        "courier": "Econt",
        "delivery_type": delivery_type,
        "address": address,
        "payment": "cod",
        "status": "new_order",
        "items": items,
        "subtotal": round(subtotal, 2),
        "discount": discount,
        "promo_code": promo,
        "shipping": round(shipping, 2),
        "total": total,
    }

    if use_supabase():
        import supabase_client as sb

        rows = sb.insert("orders", _order_to_row(order))
        saved = _order_from_row(rows[0]) if rows else order
    else:
        orders = list_orders()
        orders.insert(0, order)
        save_orders(orders)
        saved = order

    try:
        import telegram_notify

        telegram_notify.notify_new_order(saved)
    except Exception as exc:  # noqa: BLE001
        print(f"[telegram] notify error: {exc}", flush=True)

    return saved


def stats() -> dict:
    orders = list_orders()
    products = list_products()
    counts = {s: 0 for s in ORDER_STATUSES}
    turnover = 0.0
    for o in orders:
        st = o.get("status") or "new_order"
        if st in counts:
            counts[st] += 1
        if st != "declined":
            turnover += float(o.get("total") or 0)
    active = [p for p in products if not p.get("archived")]
    return {
        "orders": counts,
        "orders_total": len(orders),
        "new_orders": counts["new_order"],
        "turnover": round(turnover, 2),
        "products_total": len(active),
        "products_all": len(products),
        "in_stock": sum(1 for p in active if p.get("in_stock")),
        "out_of_stock": sum(1 for p in active if not p.get("in_stock")),
        "archived": sum(1 for p in products if p.get("archived")),
        "status_labels": STATUS_LABELS_BG,
        "backend": "supabase" if use_supabase() else "json",
    }
