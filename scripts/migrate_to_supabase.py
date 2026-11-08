"""Create schema (if DATABASE_URL set) and upload local JSON into Supabase."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import admin_store  # noqa: E402
import supabase_client as sb  # noqa: E402


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    if not sb.configured():
        raise SystemExit("Missing SUPABASE_URL / SUPABASE_SECRET_KEY in .env")

    if not sb.tables_ready():
        raise SystemExit(
            "Tables products/orders not found.\n"
            "Open Supabase SQL Editor and run scripts/supabase_schema.sql, then re-run this script."
        )

    products = json.loads((ROOT / "data" / "products.json").read_text(encoding="utf-8"))
    orders = json.loads((ROOT / "data" / "orders.json").read_text(encoding="utf-8"))

    print(f"Uploading {len(products)} products...")
    rows = [admin_store._product_to_row(p) for p in products]
    for i in range(0, len(rows), 80):
        chunk = rows[i : i + 80]
        sb.upsert("products", chunk, on_conflict="id")
        print(f"  products {i + len(chunk)}/{len(rows)}")

    print(f"Uploading {len(orders)} orders...")
    orows = [admin_store._order_to_row(o) for o in orders]
    for i in range(0, len(orows), 80):
        chunk = orows[i : i + 80]
        sb.upsert("orders", chunk, on_conflict="id")
        print(f"  orders {i + len(chunk)}/{len(orows)}")

    admin_store.refresh_supabase_status()
    print("Backend:", "supabase" if admin_store.use_supabase() else "json")
    print("Products in DB:", len(admin_store.list_products()))
    print("Orders in DB:", len(admin_store.list_orders()))
    admin_store._sync_storefront(admin_store.list_products())
    print("Done.")


if __name__ == "__main__":
    main()
