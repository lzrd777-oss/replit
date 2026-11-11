"""Apply shop specs (incl. kit rows) + missing reviews into local PDP HTML + products.json."""
from __future__ import annotations

import json
import re
import time
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENRICH = json.loads((ROOT / "data" / "shop_pdp_enrichment.json").read_text(encoding="utf-8"))
PRODUCTS_PATH = ROOT / "data" / "products.json"
PRODUCTS = json.loads(PRODUCTS_PATH.read_text(encoding="utf-8"))
PDP_DIR = ROOT / "bg" / "produkt"

SPEC_DETAILS_RE = re.compile(
    r'<details[^>]*data-oblast="spec"[\s\S]*?</details>',
    re.I,
)
REV_DETAILS_RE = re.compile(
    r'<details[^>]*data-oblast="recenze"[\s\S]*?</details>',
    re.I,
)


def normalize_shop_html(html: str) -> str:
    if not html:
        return html
    # Keep/force open so desktop cards are not collapsed on static export
    if "data-desktop-otevrit" in html and not re.search(r"<details\b[^>]*\bopen\b", html, re.I):
        html = re.sub(r"(<details\b[^>]*data-desktop-otevrit[^>]*)>", r"\1 open>", html, count=1, flags=re.I)
    html = html.replace("viewBox", "viewbox")
    # drop cursor refs if any
    html = re.sub(r'\sdata-cursor-ref="[^"]*"', "", html)
    return html


def build_specs_details(rows: list[dict], template_html: str | None) -> str:
    # Prefer shop outerHTML if present, else rebuild from template classes
    if template_html and ("<table" in template_html):
        return normalize_shop_html(template_html)
    rows_html = "".join(
        f'<tr><th scope="row">{escape(r["label"])}</th><td>{escape(r["value"])}</td></tr>'
        for r in rows
    )
    return (
        '<details class="Pdp-module__d6MGZG__infoKarta Pdp-module__d6MGZG__infoPlna" '
        'data-otevrit-od-tabletu="" data-oblast="spec" data-desktop-otevrit="" open>'
        '<summary class="Pdp-module__d6MGZG__infoHlava" id="specifikace">'
        '<h2 class="Pdp-module__d6MGZG__infoTitul">'
        '<svg class="Pdp-module__d6MGZG__infoIkona" viewbox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<circle cx="12" cy="12" r="3"></circle>'
        '<path d="M12 2v3M12 19v3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M2 12h3M19 12h3M4.9 19.1 7 17M17 7l2.1-2.1"></path>'
        "</svg>"
        '<span class="Pdp-module__d6MGZG__infoTitulText">Спецификации</span>'
        '<svg class="Pdp-module__d6MGZG__infoSipka" viewbox="0 0 24 24" width="18" height="18" fill="none" '
        'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="m6 9 6 6 6-6"></path></svg></h2></summary>'
        f'<div class="Pdp-module__d6MGZG__infoTelo"><table class="Pdp-module__d6MGZG__spec" id="pdpSpecsTable">'
        f"<tbody>{rows_html}</tbody></table></div></details>"
    )


def fill_kompatibilita_kit(html: str, rows: list[dict]) -> tuple[str, bool]:
    """Put kit rows into the existing kompatibilita side-card (no second kit section)."""
    kit_rows = [
        r
        for r in rows
        if "Съдържание" in r["label"] or "Допълнително" in r["label"] or "опаков" in r["label"].lower()
    ]
    if not kit_rows or 'data-oblast="kompatibilita"' not in html:
        return html, False
    rows_html = "".join(
        f'<tr><th scope="row">{escape(r["label"])}</th><td>{escape(r["value"])}</td></tr>'
        for r in kit_rows
    )
    table = f'<table class="Pdp-module__d6MGZG__spec"><tbody>{rows_html}</tbody></table>'

    def repl(m: re.Match[str]) -> str:
        block = m.group(0)
        # force title + id + open
        block = re.sub(
            r'(<span class="Pdp-module__d6MGZG__infoTitulText">)[^<]*(</span>)',
            r"\1Съдържание на комплекта\2",
            block,
            count=1,
        )
        block = re.sub(
            r'(<summary\b[^>]*)(\bid="[^"]*")?',
            r'\1 id="obsah-komplektu"',
            block,
            count=1,
        )
        if not re.search(r"<details\b[^>]*\bopen\b", block, re.I):
            block = re.sub(r"(<details\b[^>]*)>", r"\1 open>", block, count=1)
        block = re.sub(
            r'(<div class="Pdp-module__d6MGZG__infoTelo">)[\s\S]*?(</div>\s*</details>)',
            rf"\1{table}\2",
            block,
            count=1,
        )
        return block

    html2, n = re.subn(
        r'<details\b[^>]*\bdata-oblast="kompatibilita"[^>]*>[\s\S]*?</details>',
        repl,
        html,
        count=1,
        flags=re.I,
    )
    return (html2, True) if n else (html, False)


def local_has_review_body(html: str) -> bool:
    m = REV_DETAILS_RE.search(html)
    if not m:
        return False
    text = re.sub(r"<[^>]+>", " ", m.group(0))
    text = re.sub(r"\s+", " ", text)
    return bool(re.search(r"\d+\s*отзив", text, re.I)) and (
        "★★" in text or "review" in m.group(0).lower() or "Потвърдена" in text or len(text) > 180
    )


def ensure_nav_link(html: str, label: str, anchor: str) -> str:
    # Add jump link near other pdp anchors if missing
    if f'href="#{anchor}"' in html or f"#{anchor}" in html:
        return html
    # insert after Specifikace link if present
    html2, n = re.subn(
        r'(<a[^>]*>\s*Спецификации\s*</a>)',
        rf'\1<a href="#{anchor}">{label}</a>',
        html,
        count=1,
    )
    return html2 if n else html


def write_safe(path: Path, content: str) -> bool:
    tmp = path.with_suffix(path.suffix + ".tmp_enrich")
    for _ in range(5):
        try:
            tmp.write_text(content, encoding="utf-8")
            tmp.replace(path)
            return True
        except OSError:
            time.sleep(0.3)
    return False


def apply_one(slug: str, enrich: dict) -> dict:
    path = PDP_DIR / f"{slug}.html"
    if not path.exists():
        return {"slug": slug, "status": "missing-html"}
    html = path.read_text(encoding="utf-8", errors="ignore")
    rows = enrich.get("specs_rows") or []
    changed = []

    if rows:
        new_spec = build_specs_details(rows, enrich.get("specs_html"))
        if SPEC_DETAILS_RE.search(html):
            html2 = SPEC_DETAILS_RE.sub(new_spec, html, count=1)
        else:
            html2 = html
            # try insert before reviews
            html2, n = re.subn(
                r'(<details[^>]*data-oblast="recenze")',
                new_spec + r"\1",
                html2,
                count=1,
            )
            if not n:
                return {"slug": slug, "status": "no-spec-slot"}
        if html2 != html:
            html = html2
            changed.append("specs")

    # Never inject a second kit details block — fill kompatibilita side card instead
    html, kit_ok = fill_kompatibilita_kit(html, rows)
    if kit_ok:
        # drop any leftover injected kit sections
        html2, n_drop = re.subn(
            r'<details\b[^>]*\bdata-oblast="kit"[^>]*>[\s\S]*?</details>',
            "",
            html,
            flags=re.I,
        )
        if n_drop:
            html = html2
        html = ensure_nav_link(html, "Съдържание на комплекта", "obsah-komplektu")
        changed.append("kit")

    # Reviews: only fill if local empty; and only if shop cards look product-specific enough
    # Skip shop reviews that look like flower reviews (пъпки/миризма/разновидност Snowflake)
    rev = enrich.get("reviews") or {}
    rev_html = rev.get("html")
    rev_text = (rev.get("text") or "") + " " + " ".join(
        c.get("text", "") for c in (rev.get("cards") or [])
    )
    flowerish = any(
        w in rev_text.lower()
        for w in ["пъпки", "снежинка", "snowflake", "торбите", "миризма може"]
    )
    if rev_html and not local_has_review_body(html) and not flowerish:
        new_rev = normalize_shop_html(rev_html)
        if REV_DETAILS_RE.search(html):
            html = REV_DETAILS_RE.sub(new_rev, html, count=1)
            changed.append("reviews")
        else:
            # insert after kit/specs
            html = SPEC_DETAILS_RE.sub(lambda m: m.group(0) + new_rev, html, count=1)
            changed.append("reviews-inserted")

    if not changed:
        return {"slug": slug, "status": "noop"}

    if not write_safe(path, html):
        return {"slug": slug, "status": "write-fail", "changed": changed}
    return {"slug": slug, "status": "ok", "changed": changed}


def update_products_json():
    by_slug = {e["slug"]: e for e in ENRICH if e.get("ok")}
    updated = 0
    for p in PRODUCTS:
        e = by_slug.get(p["slug"])
        if not e or not e.get("specs_rows"):
            continue
        # store structured specs
        p["specs"] = {r["label"]: r["value"] for r in e["specs_rows"]}
        kit_rows = {
            r["label"]: r["value"]
            for r in e["specs_rows"]
            if "Съдържание" in r["label"] or "Допълнително" in r["label"]
        }
        if kit_rows:
            p["package_contents"] = kit_rows
        updated += 1
    PRODUCTS_PATH.write_text(json.dumps(PRODUCTS, ensure_ascii=False, indent=2), encoding="utf-8")
    return updated


def main():
    results = []
    for e in ENRICH:
        if not e.get("ok"):
            continue
        results.append(apply_one(e["slug"], e))
    pj = update_products_json()
    ok = sum(1 for r in results if r["status"] == "ok")
    print("pdp updated", ok, "/", len(results))
    print("products.json specs updated", pj)
    from collections import Counter

    print(Counter(tuple(r.get("changed") or [r["status"]]) for r in results).most_common(20))
    (ROOT / "data" / "apply_enrichment_report.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
