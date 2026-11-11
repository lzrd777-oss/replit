"""Fix empty Specs/Kit cards + duplicate kit nav on PDPs.

Root cause:
- details[data-desktop-otevrit] ship without open, so desktop bodies stay collapsed
- a second data-oblast=kit block was injected while kompatibilita was retitled to kit
"""
from __future__ import annotations

import re
from pathlib import Path

PDP = Path("bg/produkt")
CSS = Path("_next/static/chunks/17xvjgz6fe76t.css")

KIT_DETAILS_RE = re.compile(
    r'<details\b[^>]*\bdata-oblast="kit"[^>]*>[\s\S]*?</details>',
    re.I,
)
# consecutive duplicate kit anchors (with or without wrapping)
DUP_NAV_RE = re.compile(
    r'(<a\b[^>]*href="#(?:obsah-komplektu|kompatibilita)"[^>]*>\s*Съдържание на комплекта\s*</a>\s*){2,}',
    re.I,
)
# orphan nav link to kit section when only kompatibilita remains
KIT_NAV_ONLY_RE = re.compile(
    r'<a\b[^>]*href="#obsah-komplektu"[^>]*>\s*Съдържание на комплекта\s*</a>',
    re.I,
)
KOMP_SUMMARY_RE = re.compile(
    r'(<details\b[^>]*\bdata-oblast="kompatibilita"[^>]*>\s*<summary\b)([^>]*)(>)',
    re.I,
)
OPEN_DESKTOP_RE = re.compile(
    r'<details\b([^>]*\bdata-desktop-otevrit\b[^>]*)>',
    re.I,
)


def ensure_open(attrs: str) -> str:
    if re.search(r"(?:^|\s)open(?:\s|=|>|$)", attrs, re.I):
        return f"<details{attrs}>" if attrs.startswith(" ") or attrs.startswith("\n") else f"<details {attrs}>"
    # normalize leading space
    if not attrs.startswith(" "):
        attrs = " " + attrs
    # insert open before closing
    return f"<details{attrs} open>"


def fix_html(html: str) -> tuple[str, list[str]]:
    notes: list[str] = []

    # 1) Drop injected kit details — kompatibilita is the side card
    html2, n_kit = KIT_DETAILS_RE.subn("", html)
    if n_kit:
        html = html2
        notes.append(f"removed_kit_details={n_kit}")

    # 2) Point kompatibilita summary at #obsah-komplektu for nav
    def komp_id(m: re.Match[str]) -> str:
        attrs = re.sub(r'\s*id="[^"]*"', "", m.group(2))
        attrs = attrs.rstrip() + ' id="obsah-komplektu"'
        if not attrs.startswith(" "):
            attrs = " " + attrs
        return m.group(1) + attrs + m.group(3)

    html2, n_id = KOMP_SUMMARY_RE.subn(komp_id, html, count=1)
    if n_id:
        html = html2
        notes.append("komp_summary_id")

    # 3) Dedupe kit nav links → single #obsah-komplektu
    html2, n_dup = DUP_NAV_RE.subn(
        '<a href="#obsah-komplektu">Съдържание на комплекта</a>',
        html,
    )
    if n_dup:
        html = html2
        notes.append(f"deduped_nav={n_dup}")

    # If both #kompatibilita and #obsah-komplektu remain as separate non-consecutive links, collapse
    # Replace leftover #kompatibilita kit-titled anchors
    html2, n_komp_nav = re.subn(
        r'<a\b[^>]*href="#kompatibilita"[^>]*>\s*Съдържание на комплекта\s*</a>',
        '<a href="#obsah-komplektu">Съдържание на комплекта</a>',
        html,
        flags=re.I,
    )
    if n_komp_nav:
        html = html2
        notes.append(f"rewrote_komp_nav={n_komp_nav}")

    # Second pass: still two kit links next to each other
    html2, n_dup2 = DUP_NAV_RE.subn(
        '<a href="#obsah-komplektu">Съдържание на комплекта</a>',
        html,
    )
    if n_dup2:
        html = html2
        notes.append(f"deduped_nav2={n_dup2}")

    # Ensure at least one kit nav if kompatibilita exists
    if 'data-oblast="kompatibilita"' in html and "Съдържание на комплекта" in html:
        if not KIT_NAV_ONLY_RE.search(html):
            html2, n_add = re.subn(
                r'(<a[^>]*>\s*Спецификации\s*</a>)',
                r'\1<a href="#obsah-komplektu">Съдържание на комплекта</a>',
                html,
                count=1,
            )
            if n_add:
                html = html2
                notes.append("added_kit_nav")

    # 4) Force open on every desktop-otevrit details
    opened = 0

    def open_repl(m: re.Match[str]) -> str:
        nonlocal opened
        raw = m.group(0)
        if re.search(r"<details\b[^>]*\bopen\b", raw, re.I):
            return raw
        opened += 1
        return raw[:-1] + " open>"

    html2, _ = OPEN_DESKTOP_RE.subn(open_repl, html)
    html = html2
    if opened:
        notes.append(f"opened={opened}")

    return html, notes


def patch_css(css: str) -> tuple[str, bool]:
    marker = "/* pdp-desktop-otevrit-force */"
    if marker in css:
        return css, False
    rule = (
        f"{marker}"
        "@media (min-width:1024px){"
        "details[data-desktop-otevrit] > *:not(summary){display:block!important;}"
        "details[data-desktop-otevrit][data-oblast=recenze] > *:not(summary){display:grid!important;}"
        "}"
    )
    return css + rule, True


def write_safe(path: Path, content: str) -> bool:
    import time

    tmp = path.with_suffix(path.suffix + ".tmp_vis")
    for _ in range(8):
        try:
            tmp.write_text(content, encoding="utf-8")
            tmp.replace(path)
            return True
        except OSError as e:
            print(f"retry {path.name}: {e}")
            time.sleep(0.4)
    return False


def main() -> None:
    updated = 0
    failed = 0
    for path in sorted(PDP.glob("*.html")):
        html = path.read_text(encoding="utf-8", errors="ignore")
        fixed, notes = fix_html(html)
        if fixed != html:
            if write_safe(path, fixed):
                updated += 1
                print(f"{path.name}: {', '.join(notes)}")
            else:
                failed += 1
                print(f"FAIL {path.name}: {', '.join(notes)}")
    print("html_updated", updated, "failed", failed)

    if CSS.exists():
        css = CSS.read_text(encoding="utf-8")
        css2, changed = patch_css(css)
        if changed:
            CSS.write_text(css2, encoding="utf-8")
            print("css_patched", CSS)
        else:
            print("css_already_patched")


if __name__ == "__main__":
    main()
