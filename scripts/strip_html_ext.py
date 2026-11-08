"""Strip .html from internal page href/action attributes in HTML files."""

from __future__ import annotations

import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

HREF_RE = re.compile(
    r"""(?P<attr>(?:href|action)=)(?P<q>["'])(?P<path>[^"']*?)\.html(?P<tail>[?#][^"']*)?(?P=q)""",
    re.IGNORECASE,
)

ABS_RE = re.compile(
    r"""(?P<q>["'])(?P<path>/(?:bg/[^"']*|bg|produkt/[^"']*|kategorie/[^"']*|znacky/[^"']*|clanky/[^"']*|[^"'/]+))\.html(?P<tail>[?#][^"']*)?(?P=q)"""
)


def normalize_page_path(path: str) -> str:
    if path in {"/bg", "bg"}:
        return "/"
    return path


def replace_href(m: re.Match) -> str:
    path = normalize_page_path(m.group("path"))
    tail = m.group("tail") or ""
    return f"{m.group('attr')}{m.group('q')}{path}{tail}{m.group('q')}"


def replace_abs(m: re.Match) -> str:
    path = normalize_page_path(m.group("path"))
    tail = m.group("tail") or ""
    return f"{m.group('q')}{path}{tail}{m.group('q')}"


def patch_text(text: str) -> str:
    text = text.replace("/bg.html", "/")
    text = HREF_RE.sub(replace_href, text)
    text = ABS_RE.sub(replace_abs, text)
    return text.replace("\x00", "")


def safe_write(path: Path, text: str) -> None:
    data = text.encode("utf-8")
    tmp = path.with_name(path.name + ".tmpstrip")
    tmp.write_bytes(data)
    for attempt in range(5):
        try:
            tmp.replace(path)
            return
        except OSError:
            time.sleep(0.15 * (attempt + 1))
    # Last resort: write via open wb
    with path.open("wb") as f:
        f.write(data)
    try:
        tmp.unlink()
    except OSError:
        pass


def main() -> None:
    changed = 0
    errors = 0
    skipped = 0
    targets = [ROOT / "index.html", *sorted((ROOT / "bg").rglob("*.html"))]
    for path in targets:
        if not path.is_file():
            continue
        try:
            original = path.read_text(encoding="utf-8", errors="ignore")
            updated = patch_text(original)
            if updated == original:
                skipped += 1
                continue
            safe_write(path, updated)
            changed += 1
            print("ok", path.relative_to(ROOT))
        except OSError as exc:
            errors += 1
            print("ERROR", path.relative_to(ROOT), exc)
    print(f"changed {changed}, unchanged {skipped}, errors {errors}")


if __name__ == "__main__":
    main()
