"""Push admin product changes into the static storefront."""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CATALOG_PATH = ROOT / "storage" / "catalog.json"
PRODUKT_DIR = ROOT / "bg" / "produkt"
TEMPLATE_SLUG = "thc-x-vape-pen-99-skywalker-2-ml"
NBSP = "\u00a0"


def format_eur(amount: float | int | None) -> str:
    cents = int(round(float(amount or 0) * 100))
    whole, frac = divmod(abs(cents), 100)
    sign = "-" if cents < 0 else ""
    body = f"{whole}" if frac == 0 else f"{whole},{frac:02d}"
    return f"{sign}{body}{NBSP}€"


def price_cents(amount: float | int | None) -> int:
    return int(round(float(amount or 0) * 100))


def member_price(product: dict) -> float:
    if product.get("member_price") is not None:
        return float(product["member_price"])
    return round(float(product.get("price") or 0) * 0.95, 2)


def stock_qty(product: dict) -> int:
    if not product.get("in_stock"):
        return 0
    text = product.get("stock_text") or ""
    m = re.search(r"(\d+)", text)
    return int(m.group(1)) if m else 5


def stock_label(product: dict) -> str:
    if product.get("in_stock"):
        return product.get("stock_text") or "В наличност (5+ бр.)"
    return product.get("stock_text") or "Изчерпано"


def product_page_path(product_id: str) -> Path:
    return PRODUKT_DIR / f"{product_id}.html"


def build_catalog_payload(products: list[dict]) -> dict:
    return {
        "updated_at": time.time(),
        "products": {
            p["id"]: {
                "id": p.get("id"),
                "slug": p.get("slug") or p.get("id"),
                "title": p.get("title") or "",
                "category": p.get("category") or "",
                "price": float(p.get("price") or 0),
                "old_price": p.get("old_price"),
                "member_price": member_price(p),
                "price_text": format_eur(p.get("price")),
                "member_text": format_eur(member_price(p)),
                "volume": p.get("volume") or "",
                "lab_label": p.get("lab_label") or "",
                "in_stock": bool(p.get("in_stock")),
                "stock_text": p.get("stock_text")
                or ("В наличност (5+ бр.)" if p.get("in_stock") else "Изчерпан"),
                "image": p.get("image") or "",
                "archived": bool(p.get("archived")),
                "short_description": p.get("short_description") or "",
                "flavors": [
                    {
                        "name": str(f.get("name") or "").strip(),
                        "description": str(f.get("description") or "").strip(),
                    }
                    for f in (p.get("flavors") or [])
                    if str(f.get("name") or "").strip()
                ],
                "colors": [
                    str(c).strip()
                    for c in (p.get("colors") or [])
                    if str(c).strip()
                ],
                "flavor_slots": int(p.get("flavor_slots") or 0)
                or (2 if str(p.get("title") or "").lower().startswith("2x") else 0),
            }
            for p in products
            if p.get("id")
        },
    }


def publish_catalog(products: list[dict]) -> dict:
    payload = build_catalog_payload(products)
    # On Vercel the filesystem is ephemeral/read-only — live catalog comes from /api/catalog.
    if os.environ.get("VERCEL"):
        return payload
    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CATALOG_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp.replace(CATALOG_PATH)
    return payload


def _set_meta(content: str, prop: str, value: str) -> str:
    pattern = rf'(property="{re.escape(prop)}" content=")[^"]*(")'

    def repl(match: re.Match[str]) -> str:
        safe = value.replace('"', "&quot;")
        return f"{match.group(1)}{safe}{match.group(2)}"

    if re.search(pattern, content):
        return re.sub(pattern, repl, content, count=1)
    return content


def _patch_product_page(content: str, product: dict) -> str:
    title = product.get("title") or product["id"]
    price = format_eur(product.get("price"))
    member = format_eur(member_price(product))
    cents = str(price_cents(product.get("price")))
    in_stock = bool(product.get("in_stock"))
    stock_text = product.get("stock_text") or (
        "В наличност (5+ бр.)" if in_stock else "Изчерпан"
    )
    avail = "true" if in_stock else "false"
    schema_target = "InStock" if in_stock else "OutOfStock"
    schema_other = "OutOfStock" if in_stock else "InStock"

    content = re.sub(
        r"<title>.*?</title>",
        f"<title>{title} – HHC-STORE</title>",
        content,
        count=1,
        flags=re.S,
    )
    content = _set_meta(content, "og:title", f"{title} – HHC-STORE")
    if product.get("image"):
        content = _set_meta(content, "og:image", product["image"])
    if product.get("short_description"):
        content = _set_meta(content, "og:description", product["short_description"])

    content = re.sub(
        r"(<h1\b[^>]*>)(.*?)(</h1>)",
        lambda m: f"{m.group(1)}{title}{m.group(3)}",
        content,
        count=1,
        flags=re.S,
    )

    content = content.replace(
        f"https://schema.org/{schema_other}",
        f"https://schema.org/{schema_target}",
        1,
    )

    # PDP stock line + CSS state classes
    if in_stock:
        content = content.replace("Pdp-module__d6MGZG__skladNic", "Pdp-module__d6MGZG__stock")
        content = content.replace("__skladNic", "__stock")
        content = content.replace("__stockOut", "__stockIn")
    else:
        content = content.replace("__stockIn", "__stockOut")
    content = re.sub(
        r'(class="[^"]*stock[^"]*"[^>]*>)([^<]*)(</p>)',
        lambda m: f"{m.group(1)}{stock_text}{m.group(3)}",
        content,
        count=3,
    )
    # PDP/RSC stock count
    content = re.sub(
        r'(\\?"stock\\?"\s*:\s*)\d+',
        rf"\g<1>{stock_qty(product)}",
        content,
        count=3,
    )
    # PDP primary CTA: enable when in stock (may contain SVG + label).
    def _patch_pdp_cta(match: re.Match[str]) -> str:
        tag = match.group(0)
        if in_stock:
            tag = re.sub(r"\sdisabled(?:=\"\")?", "", tag, count=1)
            tag = tag.replace("Извести ме", "Добави в количката")
            # Sold-out PDP CTA label is often plain "Изчерпано"
            tag = re.sub(
                r"(</svg>)\s*Изчерпано\s*(</button>)",
                r"\1Добави в количката\2",
                tag,
                count=1,
            )
            tag = re.sub(
                r"(>)Изчерпано(</button>)",
                r"\1Добави в количката\2",
                tag,
                count=1,
            )
            return tag
        if "disabled" not in tag:
            tag = tag.replace("<button", '<button disabled=""', 1)
        tag = tag.replace("Добави в количката", "Изчерпано")
        tag = tag.replace("Избери", "Изчерпано")
        return tag

    content = re.sub(
        r'<button\b[^>]*class="[^"]*cta[^"]*"[^>]*>[\s\S]{0,500}?</button>',
        _patch_pdp_cta,
        content,
        count=2,
    )
    # Listing-style notify buttons without nested markup
    if in_stock:
        content = re.sub(
            r'(<button\b[^>]*class="[^"]*cta[^"]*"[^>]*?)\sdisabled(?:="")?([^>]*>)\s*Извести ме\s*(</button>)',
            r"\1\2Избери\3",
            content,
            count=2,
        )
    else:
        content = re.sub(
            r'(<button\b[^>]*class="[^"]*ProductCard[^"]*cta[^"]*"[^>]*>)\s*Избери\s*(</button>)',
            r'<button class="ProductCard-module__ba2BAq__cta" type="button" disabled="">Извести ме</button>',
            content,
            count=2,
        )

    # Main product payload fields (first occurrence = this product on PDP)
    content = re.sub(
        r'(\\?"priceCents\\?"\s*:\s*)\d+',
        rf"\g<1>{cents}",
        content,
        count=1,
    )
    content = re.sub(
        r'(\\?"regularText\\?"\s*:\s*\\?")([^\\"]*)(\\?")',
        rf"\g<1>{price}\3",
        content,
        count=1,
    )
    content = re.sub(
        r'(\\?"memberText\\?"\s*:\s*\\?")([^\\"]*)(\\?")',
        rf"\g<1>{member}\3",
        content,
        count=1,
    )
    content = re.sub(
        r'(\\?"available\\?"\s*:\s*)(true|false)',
        rf"\g<1>{avail}",
        content,
        count=1,
    )

    # Visible PDP euro amounts in price nodes
    def replace_price_node(match: re.Match[str]) -> str:
        return re.sub(
            r"\d[\d\s\u00a0]*(?:[.,]\d{1,2})?(?:\u00a0|&nbsp;)?€",
            price,
            match.group(0),
            count=1,
        )

    content = re.sub(
        r'class="[^"]*(?:price|cena|pcena)[^"]*"[^>]*>[\s\S]{0,80}?\d[\d\s\u00a0.,]*(?:\u00a0|&nbsp;)?€',
        replace_price_node,
        content,
        count=4,
    )
    return content


def ensure_product_page(product: dict) -> None:
    dest = product_page_path(product["id"])
    if dest.exists():
        return
    template = product_page_path(TEMPLATE_SLUG)
    if not template.exists():
        pages = sorted(PRODUKT_DIR.glob("*.html"))
        if not pages:
            return
        template = pages[0]
    text = template.read_text(encoding="utf-8", errors="ignore")
    text = text.replace(template.stem, product["id"])
    dest.write_text(text, encoding="utf-8", newline="")


def sync_product_page(product: dict) -> None:
    if product.get("archived"):
        return
    ensure_product_page(product)
    path = product_page_path(product["id"])
    if not path.exists():
        return
    content = path.read_text(encoding="utf-8", errors="ignore")
    path.write_text(_patch_product_page(content, product), encoding="utf-8", newline="")


def _patch_window(window: str, product: dict) -> str:
    price = format_eur(product.get("price"))
    member = format_eur(member_price(product))
    cents = str(price_cents(product.get("price")))
    avail = "true" if product.get("in_stock") else "false"
    qty = str(stock_qty(product))
    window = re.sub(r'(\\?"priceCents\\?"\s*:\s*)\d+', rf"\g<1>{cents}", window)
    window = re.sub(
        r'(\\?"regularText\\?"\s*:\s*\\?")([^\\"]*)(\\?")',
        rf"\g<1>{price}\3",
        window,
    )
    window = re.sub(
        r'(\\?"memberText\\?"\s*:\s*\\?")([^\\"]*)(\\?")',
        rf"\g<1>{member}\3",
        window,
    )
    window = re.sub(
        r'(\\?"available\\?"\s*:\s*)(true|false)',
        rf"\g<1>{avail}",
        window,
    )
    # Card/RSC stock count drives notify-me vs buy CTA.
    window = re.sub(r'(\\?"stock\\?"\s*:\s*)\d+', rf"\g<1>{qty}", window)
    return window


def _patch_visible_product_card(window: str, product: dict) -> str:
    """Fix SSR product-card stock badge + CTA around a product href."""
    label = stock_label(product)
    in_stock = bool(product.get("in_stock"))

    if in_stock:
        window = window.replace("ba2BAq__stockOut", "ba2BAq__stockIn")
        window = window.replace("__stockOut", "__stockIn")
        window = re.sub(
            r"(<div class=\"[^\"]*stock[^\"]*\"[^>]*>\s*<span[^>]*></span>\s*<span>)([^<]*)(</span>)",
            rf"\1{label}\3",
            window,
            count=1,
        )
        window = re.sub(
            r"<span>Изчерпано</span>|<span>Изчерпан</span>",
            f"<span>{label}</span>",
            window,
            count=2,
        )
        # Disabled notify CTA -> enabled select
        window = re.sub(
            r'<button class="([^"]*cta[^"]*)" type="button" disabled(?:="")?>Извести ме</button>',
            r'<button class="\1" type="button">Избери</button>',
            window,
            count=2,
        )
        window = re.sub(
            r">Извести ме</button>",
            ">Избери</button>",
            window,
            count=2,
        )
        window = window.replace(' disabled="">Избери</button>', ">Избери</button>")
        window = window.replace(" disabled>Избери</button>", ">Избери</button>")
    else:
        window = window.replace("ba2BAq__stockIn", "ba2BAq__stockOut")
        window = window.replace("__stockIn", "__stockOut")
        window = re.sub(
            r"(<div class=\"[^\"]*stock[^\"]*\"[^>]*>\s*<span[^>]*></span>\s*<span>)([^<]*)(</span>)",
            r"\1Изчерпано\3",
            window,
            count=1,
        )
        window = re.sub(
            r'<button class="([^"]*cta[^"]*)" type="button"(?:(?!>).)*>Избери</button>',
            r'<button class="\1" type="button" disabled="">Извести ме</button>',
            window,
            count=2,
        )
    return window


def sync_product_across_html(product: dict) -> int:
    slug = product.get("slug") or product["id"]
    page = product_page_path(product["id"]).resolve()
    changed = 0
    for path in ROOT.rglob("*.html"):
        if "admin" in path.parts:
            continue
        if path.resolve() == page:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if slug not in text:
            continue
        original = text
        for pos in reversed([m.start() for m in re.finditer(re.escape(slug), text)]):
            start = max(0, pos - 550)
            end = min(len(text), pos + 1200)
            window = text[start:end]
            patched = window
            if "priceCents" in window or "regularText" in window or '"stock"' in window or '\\"stock\\"' in window:
                patched = _patch_window(patched, product)
            if "ProductCard" in window or "stockOut" in window or "Извести ме" in window or "stockIn" in window:
                patched = _patch_visible_product_card(patched, product)
            if patched != window:
                text = text[:start] + patched + text[end:]
        if text != original:
            path.write_text(text, encoding="utf-8", newline="")
            changed += 1
    return changed


def delete_product_page(product_id: str) -> None:
    path = product_page_path(product_id)
    if path.exists():
        path.unlink()


def sync_product(product: dict) -> None:
    if not product.get("archived"):
        sync_product_page(product)
    sync_product_across_html(product)


def after_mutation(
    products: list[dict],
    product: dict | None = None,
    deleted_id: str | None = None,
) -> None:
    publish_catalog(products)
    # Static HTML rewrites are local-dev only; Vercel serves immutable static files.
    if os.environ.get("VERCEL"):
        return
    if deleted_id:
        delete_product_page(deleted_id)
        return
    if product:
        sync_product(product)


def is_product_public(product_id: str, products: list[dict] | None = None) -> bool:
    items = products
    if items is None:
        catalog = CATALOG_PATH
        if catalog.exists():
            data = json.loads(catalog.read_text(encoding="utf-8"))
            item = (data.get("products") or {}).get(product_id)
            if item is not None:
                return not item.get("archived")
        return True
    for p in items:
        if p.get("id") == product_id:
            return not p.get("archived")
    return False
