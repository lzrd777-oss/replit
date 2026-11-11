"""Scrape hhc-store.shop PDPs for specs / kit contents / reviews; match local slugs."""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "shop_pdp_enrichment.json"
LOCAL = json.loads((ROOT / "data" / "products.json").read_text(encoding="utf-8"))
local_slugs = {p["slug"] for p in LOCAL}

UA = {
    "User-Agent": "Mozilla/5.0 (compatible; HHCStoreSync/1.0)",
    "Accept-Language": "bg,en;q=0.8",
}


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read().decode("utf-8", "ignore")


def list_product_slugs() -> list[str]:
    slugs: set[str] = set()
    # catalog pages + category pages often expose product links
    seeds = [
        "https://hhc-store.shop/bg/produkty",
        "https://hhc-store.shop/bg/produkty?page=1",
        "https://hhc-store.shop/bg/produkty?page=2",
        "https://hhc-store.shop/bg/produkty?page=3",
        "https://hhc-store.shop/bg/produkty?page=4",
        "https://hhc-store.shop/bg/produkty?page=5",
        "https://hhc-store.shop/bg/kategorie/thc-x",
        "https://hhc-store.shop/bg/kategorie/hxc",
        "https://hhc-store.shop/bg/kategorie/ccell",
        "https://hhc-store.shop/bg/kategorie/aromaterapie",
    ]
    for url in seeds:
        try:
            html = fetch(url)
        except Exception as e:
            print("list fail", url, e)
            continue
        for m in re.finditer(r'href="(?:https://hhc-store\.shop)?/bg/produkt/([a-z0-9\-]+)"', html):
            slugs.add(m.group(1))
        print("seed", url, "slugs so far", len(slugs))
        time.sleep(0.2)
    # also try sitemap
    for sm in [
        "https://hhc-store.shop/sitemap.xml",
        "https://hhc-store.shop/sitemap-0.xml",
        "https://hhc-store.shop/bg/sitemap.xml",
    ]:
        try:
            xml = fetch(sm)
        except Exception:
            continue
        for m in re.finditer(r"/bg/produkt/([a-z0-9\-]+)", xml):
            slugs.add(m.group(1))
        print("sitemap", sm, "slugs", len(slugs))
    return sorted(slugs)


def strip_tags(html: str) -> str:
    html = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    html = re.sub(r"<style[\s\S]*?</style>", " ", html, flags=re.I)
    html = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", html).strip()


def extract_section_by_heading(html: str, heading: str) -> str | None:
    # Prefer details/summary blocks used by Pdp
    pat = re.compile(
        rf"(<details[^>]*>[\s\S]*?{re.escape(heading)}[\s\S]*?</details>)",
        re.I,
    )
    m = pat.search(html)
    if m:
        return m.group(1)
    # h2 based
    pat2 = re.compile(
        rf"(<h2[^>]*>\s*{re.escape(heading)}\s*</h2>[\s\S]{{0,8000}}?)(?=<h2\b|<footer\b|<section\b|$)",
        re.I,
    )
    m2 = pat2.search(html)
    return m2.group(1) if m2 else None


def parse_specs_rows(block: str) -> list[dict]:
    rows = []
    # dt/dd
    for dt, dd in re.findall(r"<dt[^>]*>([\s\S]*?)</dt>\s*<dd[^>]*>([\s\S]*?)</dd>", block, re.I):
        rows.append({"label": strip_tags(dt), "value": strip_tags(dd)})
    if rows:
        return rows
    # table
    for tr in re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", block, re.I):
        cells = re.findall(r"<t[hd][^>]*>([\s\S]*?)</t[hd]>", tr, re.I)
        if len(cells) >= 2:
            rows.append({"label": strip_tags(cells[0]), "value": strip_tags(cells[1])})
    if rows:
        return rows
    # fallback key:value lines in text
    text = strip_tags(block)
    return [{"label": "_text", "value": text[:2000]}]


def parse_kit_items(block: str) -> list[str]:
    items = []
    for li in re.findall(r"<li[^>]*>([\s\S]*?)</li>", block, re.I):
        t = strip_tags(li)
        if t and len(t) < 300:
            items.append(t)
    if items:
        return items
    text = strip_tags(block)
    return [text[:2000]] if text else []


def parse_reviews(block: str) -> dict:
    text = strip_tags(block)
    rating = None
    count = None
    m = re.search(r"(\d+[.,]\d+)\s*.{0,5}?(\d+)\s*отзив", text, re.I)
    if m:
        rating = m.group(1).replace(",", ".")
        count = int(m.group(2))
    # keep raw html snippet truncated for later injection if needed
    return {
        "rating": rating,
        "count": count,
        "text_preview": text[:1500],
        "html": block[:25000],
    }


def scrape_pdp(slug: str) -> dict | None:
    url = f"https://hhc-store.shop/bg/produkt/{slug}"
    try:
        html = fetch(url)
    except Exception as e:
        return {"slug": slug, "error": str(e)}
    if "404" in html[:500] and "produkt" not in html.lower():
        return {"slug": slug, "error": "not found"}

    out: dict = {"slug": slug, "url": url, "local": slug in local_slugs}

    for key, heading in [
        ("specs", "Спецификации"),
        ("kit", "Съдържание на комплекта"),
        ("kit_alt", "Съдържание"),
        ("reviews", "Отзиви на клиенти"),
        ("reviews_alt", "Отзиви"),
        ("info", "Информация за продукта"),
    ]:
        block = extract_section_by_heading(html, heading)
        if not block:
            continue
        if key.startswith("specs"):
            out["specs_rows"] = parse_specs_rows(block)
            out["specs_html"] = block[:20000]
        elif key.startswith("kit"):
            if "kit_items" not in out:
                out["kit_items"] = parse_kit_items(block)
                out["kit_html"] = block[:15000]
        elif key.startswith("reviews"):
            if "reviews" not in out:
                out["reviews"] = parse_reviews(block)
        elif key == "info":
            out["info_text"] = strip_tags(block)[:2000]

    # detect kit heading presence more loosely
    if "Съдържание на комплекта" in html and "kit_items" not in out:
        out["kit_flag"] = True
    return out


def main():
    slugs = list_product_slugs()
    print("total shop slugs", len(slugs))
    # Prefer local overlap first, then rest
    ordered = sorted(slugs, key=lambda s: (0 if s in local_slugs else 1, s))
    results = []
    for i, slug in enumerate(ordered, 1):
        print(f"[{i}/{len(ordered)}] {slug} local={slug in local_slugs}")
        results.append(scrape_pdp(slug))
        time.sleep(0.15)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    matched = [r for r in results if r.get("local") and not r.get("error")]
    with_specs = [r for r in matched if r.get("specs_rows")]
    with_kit = [r for r in matched if r.get("kit_items")]
    with_rev = [r for r in matched if r.get("reviews", {}).get("count")]
    print("matched", len(matched), "specs", len(with_specs), "kit", len(with_kit), "reviews", len(with_rev))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
