"""Hydrated scrape of hhc-store.shop PDPs via Playwright for local product slugs."""
from __future__ import annotations

import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
LOCAL = json.loads((ROOT / "data" / "products.json").read_text(encoding="utf-8"))
OUT = ROOT / "data" / "shop_pdp_enrichment.json"


EXTRACT_JS = r"""
() => {
  const clean = (s) => (s || '').replace(/\s+/g, ' ').trim();
  const title = clean(document.querySelector('h1')?.textContent || '');
  const details = [...document.querySelectorAll('details')];
  const byTitle = (needle) => details.find(d => clean(d.querySelector('summary,h2')?.textContent || '').includes(needle));

  const spec = byTitle('Спецификации');
  const specs_rows = [];
  if (spec) {
    for (const tr of spec.querySelectorAll('tr')) {
      const th = clean(tr.querySelector('th')?.textContent || '');
      const td = clean(tr.querySelector('td')?.textContent || '');
      if (th && td) specs_rows.push({label: th, value: td});
    }
    if (!specs_rows.length) {
      for (const dt of spec.querySelectorAll('dt')) {
        const dd = dt.nextElementSibling;
        specs_rows.push({label: clean(dt.textContent), value: clean(dd?.textContent || '')});
      }
    }
  }

  const kit = byTitle('Съдържание на комплекта') || details.find(d => (d.innerText||'').includes('Съдържание на комплекта'));
  const kit_items = kit ? [...kit.querySelectorAll('li')].map(li => clean(li.textContent)).filter(Boolean) : [];

  const rev = byTitle('Отзиви на клиенти') || byTitle('Отзиви');
  let reviews = null;
  if (rev) {
    const text = clean(rev.innerText);
    const m = text.match(/(\d+[.,]\d+)\s*.{0,12}?(\d+)\s*отзив/i);
    const cards = [...rev.querySelectorAll('article, .Pdp-module__d6MGZG__review')].map(a => ({
      text: clean(a.querySelector('p')?.textContent || a.textContent).slice(0, 500),
      author: clean(a.querySelector('[class*=\"reviewMeta\"], [class*=\"Avatar\"]')?.textContent || '').slice(0, 80),
      stars: (a.textContent.match(/★/g) || []).length,
    })).filter(x => x.text.length > 8).slice(0, 12);
    reviews = {
      rating: m ? parseFloat(m[1].replace(',', '.')) : null,
      count: m ? parseInt(m[2], 10) : cards.length || null,
      cards,
      html: rev.outerHTML.slice(0, 60000),
      text: text.slice(0, 3000),
    };
  }

  const info = byTitle('Информация за продукта');
  return {
    title,
    specs_rows,
    specs_html: spec ? spec.outerHTML.slice(0, 20000) : null,
    kit_items,
    kit_html: kit ? kit.outerHTML.slice(0, 15000) : null,
    reviews,
    info_text: info ? clean(info.innerText).slice(0, 2000) : null,
    has_kit_heading: document.body.innerText.includes('Съдържание на комплекта'),
  };
}
"""


def main():
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        # dismiss age gate cookies preemptively
        page.add_init_script(
            """() => { try { localStorage.setItem('hhc-age-ok','1'); document.cookie='age_ok=1;path=/'; } catch(e){} }"""
        )
        for i, prod in enumerate(LOCAL, 1):
            slug = prod["slug"]
            url = f"https://hhc-store.shop/bg/produkt/{slug}"
            print(f"[{i}/{len(LOCAL)}] {slug}")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                # click age gate if present
                try:
                    btn = page.locator("button:has-text('Да, на 18')").first
                    if btn.is_visible(timeout=1500):
                        btn.click()
                        page.wait_for_timeout(400)
                except Exception:
                    pass
                page.wait_for_timeout(700)
                data = page.evaluate(EXTRACT_JS)
                data.update({"slug": slug, "ok": True, "url": url})
                results.append(data)
                print(
                    "  title=",
                    (data.get("title") or "")[:50],
                    "specs",
                    len(data.get("specs_rows") or []),
                    "kit",
                    len(data.get("kit_items") or []),
                    "rev",
                    (data.get("reviews") or {}).get("count"),
                )
            except Exception as e:
                results.append({"slug": slug, "ok": False, "error": str(e), "url": url})
                print("  ERR", e)
        browser.close()

    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = [r for r in results if r.get("ok")]
    print(
        "DONE ok",
        len(ok),
        "rich_specs",
        sum(1 for r in ok if len(r.get("specs_rows") or []) >= 4),
        "kit",
        sum(1 for r in ok if r.get("kit_items")),
        "reviews",
        sum(1 for r in ok if (r.get("reviews") or {}).get("count")),
    )


if __name__ == "__main__":
    main()
