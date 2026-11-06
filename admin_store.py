"""JSON-backed store for admin products and orders."""

from __future__ import annotations

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
_sessions: dict[str, float] = {}  # token -> expiry ts
SESSION_TTL = 60 * 60 * 12

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "hhc-admin")


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


def ensure_seed_data() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
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
    # Always refresh public catalog used by the storefront bridge.
    _sync_storefront(list_products())


def login(password: str) -> str | None:
    if password != ADMIN_PASSWORD:
        return None
    token = secrets.token_urlsafe(32)
    with _lock:
        _sessions[token] = time.time() + SESSION_TTL
    return token


def logout(token: str | None) -> None:
    if not token:
        return
    with _lock:
        _sessions.pop(token, None)


def valid_session(token: str | None) -> bool:
    if not token:
        return False
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
    with _lock:
        return _read_json(PRODUCTS_PATH, [])


def save_products(products: list[dict]) -> None:
    with _lock:
        _write_json(PRODUCTS_PATH, products)


def get_product(product_id: str) -> dict | None:
    for p in list_products():
        if p.get("id") == product_id:
            return p
    return None


def upsert_product(product: dict, product_id: str | None = None) -> dict:
    products = list_products()
    pid = product_id or product.get("id") or product.get("slug")
    if not pid:
        raise ValueError("Product id required")
    product = {**product, "id": pid, "slug": product.get("slug") or pid}
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
    products = list_products()
    next_list = [p for p in products if p.get("id") != product_id]
    if len(next_list) == len(products):
        return False
    save_products(next_list)
    _sync_storefront(next_list, deleted_id=product_id)
    return True


def set_archived(product_id: str, archived: bool) -> dict | None:
    products = list_products()
    for i, p in enumerate(products):
        if p.get("id") == product_id:
            products[i] = {**p, "archived": archived}
            save_products(products)
            _sync_storefront(products, product=products[i])
            return products[i]
    return None


def archive_all(active_only: bool = True) -> int:
    products = list_products()
    n = 0
    for i, p in enumerate(products):
        if active_only and p.get("archived"):
            continue
        if not p.get("archived"):
            products[i] = {**p, "archived": True}
            n += 1
    save_products(products)
    # Catalog/bridge hide archived cards sitewide; skip full HTML rewrite.
    _sync_storefront(products)
    return n


def restore_all() -> int:
    products = list_products()
    n = 0
    for i, p in enumerate(products):
        if p.get("archived"):
            products[i] = {**p, "archived": False}
            n += 1
    save_products(products)
    _sync_storefront(products)
    return n


def list_orders() -> list[dict]:
    with _lock:
        return _read_json(ORDERS_PATH, [])


def save_orders(orders: list[dict]) -> None:
    with _lock:
        _write_json(ORDERS_PATH, orders)


def set_order_status(order_id: str, status: str) -> dict | None:
    if status not in ORDER_STATUSES:
        raise ValueError("Invalid status")
    orders = list_orders()
    for i, o in enumerate(orders):
        if o.get("id") == order_id:
            orders[i] = {**o, "status": status}
            save_orders(orders)
            return orders[i]
    return None


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
    }
