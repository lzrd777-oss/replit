"""Permanently remove banned / imageless products from local JSON, catalog, and HTML."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HIDDEN = re.compile(r"greenz\s*hemp|gummies|infused\s*pre[-\s]?rolls?", re.I)

CATEGORY_PAGES = [
    "thc-x-greenz-hemp.html",
    "thc-x-gummies.html",
    "thc-x-infused-pre-rolls.html",
    "hxc-greenz-hemp.html",
]


def should_remove(p: dict) -> bool:
    img = str(p.get("image") or "").strip()
    if not img:
        return True
    hay = " ".join(
        str(x or "")
        for x in [
            p.get("category"),
            p.get("lab_label"),
            p.get("title"),
            p.get("slug"),
            p.get("id"),
            " ".join(p.get("tags") or []) if isinstance(p.get("tags"), list) else p.get("tags"),
        ]
    )
    return bool(HIDDEN.search(hay))


def main() -> None:
    # Prefer live Supabase list for catalog rebuild.
    products = []
    try:
        import supabase_client as sb  # noqa: F401
        import admin_store

        admin_store.refresh_supabase_status()
        if admin_store.use_supabase():
            products = admin_store.list_products()
            print(f"Loaded {len(products)} from Supabase")
        else:
            print("Supabase not ready locally; using JSON + filter")
    except Exception as exc:  # noqa: BLE001
        print("Supabase load failed:", exc)

    products_path = ROOT / "data" / "products.json"
    if not products and products_path.is_file():
        products = json.loads(products_path.read_text(encoding="utf-8"))

    kept = [p for p in products if not should_remove(p)]
    removed = [p for p in products if should_remove(p)]
    removed_ids = {str(p.get("id") or "") for p in removed if p.get("id")}
    print(f"kept={len(kept)} removed={len(removed)}")

    if products_path.parent.is_dir():
        products_path.write_text(
            json.dumps(kept, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print("Updated data/products.json")

    # Rebuild catalog snapshot from kept products
    try:
        import storefront_sync
        import admin_store

        # Force JSON path write via sync helper if available
        payload = storefront_sync.build_catalog_payload(kept)
        catalog_path = ROOT / "storage" / "catalog.json"
        catalog_path.parent.mkdir(parents=True, exist_ok=True)
        catalog_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        print(f"Wrote storage/catalog.json products={len(payload.get('products') or {})}")
    except Exception as exc:  # noqa: BLE001
        print("catalog rebuild failed:", exc)

    # Delete product HTML pages
    produkt_dir = ROOT / "bg" / "produkt"
    deleted_html = 0
    if produkt_dir.is_dir():
        for pid in removed_ids:
            for name in (f"{pid}.html",):
                path = produkt_dir / name
                if path.is_file():
                    path.unlink()
                    deleted_html += 1
        # Also match by slug filename containing banned terms
        for path in list(produkt_dir.glob("*.html")):
            stem = path.stem
            if HIDDEN.search(stem.replace("-", " ")) or "greenz" in stem or "gummies" in stem or "infused-pre-roll" in stem:
                path.unlink(missing_ok=True)
                deleted_html += 1
    print(f"Deleted product HTML files: {deleted_html}")

    # Delete dedicated category pages
    kat = ROOT / "bg" / "kategorie"
    for name in CATEGORY_PAGES:
        path = kat / name
        if path.is_file():
            path.unlink()
            print("Deleted category page", name)

    # Strip category links from remaining kategorie HTML + homepage is heavy;
    # rebuild produkty page will drop sidebar rows via script.


if __name__ == "__main__":
    main()
