"""Ensure storefront scripts are present in static HTML (needed for Vercel)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNIPPET = (
    '<script src="/storefront-bridge.js" defer></script>'
    '<script src="/cart.js" defer></script>'
    '<script src="/age-gate.js" defer></script>'
)
MARKERS = (
    'src="/storefront-bridge.js"',
    "src='/storefront-bridge.js'",
)


def patch(path: Path) -> bool:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if any(m in text for m in MARKERS):
        # Ensure cart.js is also present for pages that only had bridge.
        if 'src="/cart.js"' not in text and "src='/cart.js'" not in text:
            text = text.replace(
                '<script src="/storefront-bridge.js" defer></script>',
                '<script src="/storefront-bridge.js" defer></script>'
                '<script src="/cart.js" defer></script>',
            )
            if 'src="/cart.js"' not in text:
                text = text.replace("</body>", f"{SNIPPET}</body>")
            path.write_text(text, encoding="utf-8", newline="")
            return True
        return False
    lower = text.lower()
    if "</body>" not in lower:
        return False
    # Case-preserving replace of closing body tag
    idx = lower.rfind("</body>")
    text = text[:idx] + SNIPPET + text[idx:]
    path.write_text(text, encoding="utf-8", newline="")
    return True


def main() -> None:
    targets = [ROOT / "index.html"]
    targets += list((ROOT / "bg").rglob("*.html"))
    changed = 0
    for path in targets:
        if not path.is_file():
            continue
        if patch(path):
            changed += 1
            print("patched", path.relative_to(ROOT))
    print(f"done, changed {changed} files")


if __name__ == "__main__":
    main()
