"""Build /bg/produkty from a real Katalog category page shell (CSS only, no Next hydration)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "bg" / "kategorie" / "thc-x.html"
OUT = ROOT / "bg" / "produkty.html"


def main() -> None:
    html = SRC.read_text(encoding="utf-8", errors="ignore")

    # Root-absolute assets
    html = html.replace('href="../../', 'href="/')
    html = html.replace('src="../../', 'src="/')
    html = html.replace('srcset="../../', 'srcset="/')
    html = html.replace('imagesrcset="../../', 'imagesrcset="/')

    # Links
    html = re.sub(r'href="\.\./produkt/', 'href="/bg/produkt/', html)
    html = re.sub(r'href="\.\./produkty"', 'href="/bg/produkty"', html)
    html = re.sub(
        r'href="((?:thc-x|hxc|ccell|aromaterapie)[^"]*)"',
        r'href="/bg/kategorie/\1"',
        html,
    )

    # Title
    html = re.sub(
        r"<title>[^<]*</title>",
        "<title>Всички продукти – HHC-STORE</title>",
        html,
        count=1,
    )

    # Hero heading / breadcrumbs
    html = re.sub(r"(<h1[^>]*>)([\s\S]*?)(</h1>)", r"\1Всички продукти\3", html, count=1)
    html = re.sub(
        r'(aria-current="page"[^>]*>)([^<]+)(</)',
        r"\1Всички продукти\3",
        html,
        count=1,
    )

    # Sidebar active state: all products
    html = re.sub(
        r'<a class="Katalog-module__iT4WXq__katOdkaz(?: Katalog-module__iT4WXq__katAktivni)?" href="/bg/produkty">',
        '<a class="Katalog-module__iT4WXq__katOdkaz Katalog-module__iT4WXq__katAktivni" href="/bg/produkty">',
        html,
        count=1,
    )
    html = html.replace(
        'class="Katalog-module__iT4WXq__katOdkaz Katalog-module__iT4WXq__katAktivni" href="/bg/kategorie/thc-x"',
        'class="Katalog-module__iT4WXq__katOdkaz " href="/bg/kategorie/thc-x"',
    )
    html = html.replace(
        'class="Katalog-module__iT4WXq__katOdkaz Katalog-module__iT4WXq__katAktivni" href="/bg/kategorie/thc-x"',
        'class="Katalog-module__iT4WXq__katOdkaz " href="/bg/kategorie/thc-x"',
    )
    # Also form where aktivni is on thc-x with trailing space class first
    html = re.sub(
        r'(<a class="Katalog-module__iT4WXq__katOdkaz )Katalog-module__iT4WXq__katAktivni(" href="/bg/kategorie/thc-x")',
        r"\1\2",
        html,
        count=1,
    )

    # Clear product grid
    html2, n = re.subn(
        r'(<div class="ProductCard-module__ba2BAq__products Katalog-module__iT4WXq__mrizka">)[\s\S]*?</div>',
        r'<div id="hhc-product-grid" class="ProductCard-module__ba2BAq__products Katalog-module__iT4WXq__mrizka">'
        r'<div id="hhc-live-status" style="padding:16px;opacity:.7">Зареждане…</div></div>',
        html,
        count=1,
    )
    if n != 1:
        raise SystemExit(f"grid replace failed ({n})")
    html = html2

    # Hide pagination (static clone leftovers)
    html = re.sub(
        r'<nav[^>]*aria-label="Странициране"[\s\S]*?</nav>',
        "",
        html,
        count=1,
    )

    # Tag first checkbox + price inputs for filters
    html = re.sub(
        r'(<input[^>]*type="checkbox"[^>]*)(>)',
        r'\1 id="hhc-filter-stock" data-hhc-filter="stock"\2',
        html,
        count=1,
    )
    price_n = 0

    def tag_price(m: re.Match[str]) -> str:
        nonlocal price_n
        attrs = m.group(1)
        if 'type="number"' not in attrs and "spinbutton" not in attrs and 'placeholder="от"' not in attrs and 'placeholder="до"' not in attrs:
            # still tag number-looking price fields by placeholder
            if 'placeholder="от"' not in attrs and 'placeholder="до"' not in attrs and 'type="number"' not in attrs:
                return m.group(0)
        price_n += 1
        if price_n == 1:
            return f'<input{attrs} id="hhc-price-from" data-hhc-filter="price-from">'
        if price_n == 2:
            return f'<input{attrs} id="hhc-price-to" data-hhc-filter="price-to">'
        return m.group(0)

    html = re.sub(r"<input([^>]*?)>", tag_price, html)
    # Fallback: placeholders от/до
    if "hhc-price-from" not in html:
        html = html.replace('placeholder="от"', 'placeholder="от" id="hhc-price-from"', 1)
        html = html.replace('placeholder="до"', 'placeholder="до" id="hhc-price-to"', 1)

    html = re.sub(
        r"<button([^>]*)>([^<]*Покажи[\s\S]{0,80}?продукта[^<]*)</button>",
        '<button type="button" id="hhc-apply-filters" class="Katalog-module__iT4WXq__tlacitko">'
        'Покажи <span id="hhc-apply-count">0</span> продукта</button>',
        html,
        count=1,
    )

    # Remove leftover static product cards (outside the live grid).
    html = re.sub(
        r'<article class="ProductCard-module__ba2BAq__card[\s\S]*?</article>',
        "",
        html,
    )

    # Drop removed subcategory rows from sidebar lists only (exact short labels).
    for label in (
        "Greenz Hemp",
        "Gummies",
        "Infused Pre-Rolls",
    ):
        html = re.sub(
            rf'<li>\s*<a class="Katalog-module__iT4WXq__katOdkaz[^"]*" href="[^"]*">\s*<span>{re.escape(label)}</span>\s*<span class="Katalog-module__iT4WXq__katPocet">\d+</span>\s*</a>\s*</li>',
            "",
            html,
            flags=re.I,
        )

    # CRITICAL: strip Next.js runtime / RSC / hydration so the category page
    # cannot re-render THC-X content over our live grid.
    html = re.sub(r"<script\b[\s\S]*?</script>", "", html, flags=re.I)

    inject = (
        '\n<script src="/age-gate.js" defer></script>'
        '\n<script src="/storefront-bridge.js" defer></script>'
        '\n<script src="/cart.js" defer></script>'
        '\n<script src="/produkty/produkty.js" defer></script>\n'
    )
    html = html.replace("</body>", inject + "</body>", 1)

    OUT.write_text(html, encoding="utf-8")
    print(f"Wrote {OUT} ({OUT.stat().st_size} bytes) articles={html.count('<article')}")


if __name__ == "__main__":
    main()
