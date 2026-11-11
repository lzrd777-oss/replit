"""Remove duplicate kit details blocks / nav links on PDPs."""
from __future__ import annotations

import re
from pathlib import Path

PDP = Path("bg/produkt")
KIT_RE = re.compile(
    r'<details[^>]*(?:data-oblast="kit"|id="obsah-komplektu")[\s\S]*?</details>',
    re.I,
)
NAV_KIT_RE = re.compile(
    r'(?:<a[^>]*>\s*Съдържание на комплекта\s*</a>\s*){2,}',
    re.I,
)

updated = 0
for path in PDP.glob("*.html"):
    html = path.read_text(encoding="utf-8", errors="ignore")
    kits = KIT_RE.findall(html)
    changed = False
    if len(kits) > 1:
        keep = kits[0]
        html2 = KIT_RE.sub("__KIT_PLACEHOLDER__", html)
        html2 = html2.replace("__KIT_PLACEHOLDER__", keep, 1)
        html2 = html2.replace("__KIT_PLACEHOLDER__", "")
        html = html2
        changed = True
    html2, n = NAV_KIT_RE.subn('<a href="#obsah-komplektu">Съдържание на комплекта</a>', html)
    if n:
        html = html2
        changed = True
    if changed:
        path.write_text(html, encoding="utf-8")
        updated += 1
print("updated", updated)
