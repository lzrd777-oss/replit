"""Extract products from static HTML into data/products.json."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
PROD_DIR = ROOT / "bg" / "produkt"
OUT = ROOT / "data" / "products.json"


def parse_eur_text(text: str | None) -> float | None:
    if not text:
        return None
    m = re.search(r"([\d\s\u00a0]+(?:[.,]\d{1,2})?)\s*€", text)
    if not m:
        return None
    raw = m.group(1).replace("\u00a0", "").replace(" ", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def category_from_title_slug(title: str, slug: str) -> str:
    t = f"{title} {slug}".lower()
    if slug.startswith("2x-") or "set" in slug or "комплект" in t:
        return "Изгодни Сетове"
    if "aromaterapie" in slug or "арома" in t:
        return "Ароматерапия"
    if slug.startswith("ccell") or t.startswith("ccell"):
        return "CCELL"
    if "hxc" in slug or re.search(r"\bhxc\b", t):
        return "HXC"
    if "thc-x" in slug or "thc-x" in t or "thc x" in t:
        return "THC-X"
    return "Други"


def lab_badge(title: str) -> str:
    m = re.search(r"(99%\s*(?:THC-X|HXC))", title, re.I)
    if m:
        return re.sub(r"\s+", " ", m.group(1).upper().replace("THC-X", "THC-X"))
    if re.search(r"\bCCELL\b", title, re.I):
        return "CCELL"
    return ""


def volume_from_title(title: str) -> str:
    m = re.search(r"(\d+(?:[.,]\d+)?\s*ml)", title, re.I)
    return m.group(1).replace(",", ".") if m else ""


def schema_availability(html: str) -> str | None:
    # Prefer first Product offer availability
    for m in re.finditer(
        r'<script type="application/ld\+json">(.*?)</script>', html, re.S
    ):
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        nodes = data if isinstance(data, list) else [data]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            if node.get("@type") == "Product":
                offers = node.get("offers") or {}
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                avail = str(offers.get("availability", ""))
                if "OutOfStock" in avail:
                    return "out"
                if "InStock" in avail:
                    return "in"
    # Fallback: first schema availability mention
    m = re.search(r"schema\.org/(InStock|OutOfStock)", html)
    if m:
        return "in" if m.group(1) == "InStock" else "out"
    return None


def stock_label(html: str, in_stock: bool) -> str:
    if not in_stock:
        return "Изчерпан"
    m = re.search(r"В наличност\s*\(([^)]+)\)", html)
    if m and "{n}" not in m.group(0):
        return f"В наличност ({m.group(1)})"
    return "В наличност (5+ бр.)"


def extract_one(path: Path) -> dict:
    html = path.read_text(encoding="utf-8", errors="ignore")
    slug = path.stem

    title_m = re.search(r'property="og:title" content="([^"]+)"', html)
    title = title_m.group(1) if title_m else slug
    title = re.sub(r"\s*[–—-]\s*HHC-STORE.*$", "", title).strip()
    h1 = re.search(r"<h1[^>]*>([^<]+)", html)
    if h1:
        title = h1.group(1).strip()

    img_m = re.search(r'property="og:image" content="([^"]+)"', html)
    image = img_m.group(1) if img_m else ""

    desc_m = re.search(r'property="og:description" content="([^"]+)"', html)
    description = desc_m.group(1) if desc_m else ""

    price = None
    cents_m = re.search(r'\\"priceCents\\":(\d+)', html)
    if cents_m:
        price = int(cents_m.group(1)) / 100.0
    if price is None:
        reg_m = re.search(r'\\"regularText\\":\\"([^\\"]+)\\"', html)
        price = parse_eur_text(reg_m.group(1) if reg_m else None)
    if price is None:
        # first visible euro price in page body-ish
        for m in re.finditer(r">([\d\s\u00a0]+(?:[.,]\d{1,2})?)\u00a0€<", html):
            price = parse_eur_text(m.group(1) + " €")
            if price:
                break
    if price is None:
        price = 0.0

    member = None
    mem_m = re.search(r'\\"memberText\\":\\"([^\\"]+)\\"', html)
    if mem_m:
        member = parse_eur_text(mem_m.group(1))

    avail = schema_availability(html)
    in_stock = avail != "out"
    stock_text = stock_label(html, in_stock)

    sku = slug
    short = description
    for m in re.finditer(
        r'<script type="application/ld\+json">(.*?)</script>', html, re.S
    ):
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("@type") == "Product":
            sku = data.get("sku") or sku
            if data.get("description"):
                short = data["description"]

    volume = volume_from_title(title)
    badge = lab_badge(title)
    category = category_from_title_slug(title, slug)

    if volume and badge:
        specs = f"Обем: {volume} · Канабиноиден профил: {badge}"
    elif volume:
        specs = f"Обем: {volume}"
    elif badge:
        specs = f"Канабиноиден профил: {badge}"
    else:
        specs = ""

    return {
        "id": slug,
        "slug": slug,
        "title": title,
        "category": category,
        "price": round(float(price), 2),
        "old_price": None,
        "member_price": round(member, 2) if member is not None else None,
        "volume": volume,
        "lab_label": badge,
        "in_stock": in_stock,
        "stock_text": stock_text,
        "image": image,
        "specs": specs,
        "tags": "CRD Full Spectrum, Drug Test Free" if badge else "",
        "short_description": (short or "")[:280],
        "full_description": short or "",
        "flavors": [],
        "archived": False,
        "sku": sku,
    }


def main() -> None:
    products = [extract_one(p) for p in sorted(PROD_DIR.glob("*.html"))]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(products, ensure_ascii=False, indent=2), encoding="utf-8")
    cats: dict[str, int] = {}
    for p in products:
        cats[p["category"]] = cats.get(p["category"], 0) + 1
    stock = sum(1 for p in products if p["in_stock"])
    print(f"wrote {len(products)} products -> {OUT}")
    print("categories", cats)
    print("in_stock", stock, "out", len(products) - stock)
    print("sample", products[0]["title"], products[0]["price"], products[0]["category"])


if __name__ == "__main__":
    main()
