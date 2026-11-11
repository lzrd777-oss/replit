"""Clean duplicate kit nav links and broken multi-id summaries on PDPs."""
from __future__ import annotations

import re
import time
from pathlib import Path

PDP = Path("bg/produkt")

# summary with stacked ids
SUMMARY_IDS_RE = re.compile(
    r'(<details\b[^>]*\bdata-oblast="kompatibilita"[^>]*>\s*<summary\b)([^>]*)(>)',
    re.I,
)

# Extra kit link jammed into specifikace <li>
EXTRA_IN_SPEC_RE = re.compile(
    r'(<li\b[^>]*data-id="specifikace"[^>]*>\s*<a\b[^>]*>\s*Спецификации\s*</a>)\s*'
    r'<a\b[^>]*href="#obsah-komplektu"[^>]*>\s*Съдържание на комплекта\s*</a>',
    re.I,
)


def write_safe(path: Path, content: str) -> bool:
    tmp = path.with_suffix(path.suffix + ".tmp_nav")
    for _ in range(8):
        try:
            tmp.write_text(content, encoding="utf-8")
            tmp.replace(path)
            return True
        except OSError as e:
            print(f"retry {path.name}: {e}")
            time.sleep(0.4)
    return False


def fix_summary_attrs(attrs: str) -> str:
    # drop all id="..." then set one
    attrs = re.sub(r'\s*id="[^"]*"', "", attrs)
    attrs = attrs.rstrip() + ' id="obsah-komplektu"'
    if not attrs.startswith(" "):
        attrs = " " + attrs
    return attrs


def fix(html: str) -> tuple[str, list[str]]:
    notes: list[str] = []

    def repl(m: re.Match[str]) -> str:
        return m.group(1) + fix_summary_attrs(m.group(2)) + m.group(3)

    html2, n = SUMMARY_IDS_RE.subn(repl, html, count=1)
    if n:
        html = html2
        notes.append("summary_id")

    html2, n = EXTRA_IN_SPEC_RE.subn(r"\1", html)
    if n:
        html = html2
        notes.append(f"removed_extra_kit_in_spec={n}")

    # If no kompatibilita nav li, ensure one kit link exists somewhere sensible
    if 'data-oblast="kompatibilita"' in html:
        kit_links = re.findall(
            r'<a\b[^>]*href="#obsah-komplektu"[^>]*>\s*Съдържание на комплекта\s*</a>',
            html,
            flags=re.I,
        )
        if len(kit_links) == 0:
            html2, n = re.subn(
                r'(<li\b[^>]*data-id="kompatibilita"[^>]*>)[\s\S]*?(</li>)',
                r'\1<a href="#obsah-komplektu">Съдържание на комплекта</a>\2',
                html,
                count=1,
                flags=re.I,
            )
            if n:
                html = html2
                notes.append("restored_komp_nav")
        elif len(kit_links) > 1:
            # keep first, strip later duplicates by replacing all then restoring one in komp li
            first = True

            def keep_one(m: re.Match[str]) -> str:
                nonlocal first
                if first:
                    first = False
                    return m.group(0)
                return ""

            html2, n = re.subn(
                r'<a\b[^>]*href="#obsah-komplektu"[^>]*>\s*Съдържание на комплекта\s*</a>',
                keep_one,
                html,
                flags=re.I,
            )
            if n > 1:
                html = html2
                notes.append(f"kept_one_kit_nav_from={n}")

    return html, notes


def main() -> None:
    updated = 0
    for path in sorted(PDP.glob("*.html")):
        html = path.read_text(encoding="utf-8", errors="ignore")
        fixed, notes = fix(html)
        if fixed != html:
            if write_safe(path, fixed):
                updated += 1
                print(f"{path.name}: {', '.join(notes)}")
            else:
                print(f"FAIL {path.name}")
    print("updated", updated)


if __name__ == "__main__":
    main()
