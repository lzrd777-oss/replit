import json
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
env = {}
for line in (ROOT / ".env").read_text(encoding="utf-8", errors="ignore").splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip().lstrip("\ufeff")] = v.strip().strip('"').strip("'")

base = env.get("SUPABASE_URL", "").rstrip("/") + "/rest/v1/products"
key = env.get("SUPABASE_SECRET_KEY") or env.get("SUPABASE_SERVICE_ROLE_KEY")
print("url", base[:50], "key", bool(key))
products = json.loads((ROOT / "data" / "products.json").read_text(encoding="utf-8"))
ok = 0
for p in products:
    specs = p.get("specs")
    if not isinstance(specs, dict) or not specs:
        continue
    body = json.dumps({"specs": specs}).encode("utf-8")
    req = urllib.request.Request(
        base + "?slug=eq." + urllib.parse.quote(p["slug"]),
        data=body,
        method="PATCH",
        headers={
            "apikey": key,
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            ok += 1
    except Exception as e:
        print("fail", p["slug"], e)
print("patched", ok)
