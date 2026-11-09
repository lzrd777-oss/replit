"""Telegram notifications for new storefront orders."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


def configured() -> bool:
    return bool(
        (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
        and (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
    )


def _escape_html(text: str) -> str:
    return (
        str(text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _eur(amount: float | int | None) -> str:
    value = float(amount or 0)
    # Match screenshot style: €26,80
    formatted = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", " ")
    return f"€{formatted}"


def _item_label(item: dict[str, Any]) -> str:
    title = str(item.get("title") or item.get("product_id") or "Продукт").strip()
    volume = str(item.get("volume") or "").strip()
    flavors = [str(f).strip() for f in (item.get("flavors") or []) if str(f).strip()]
    color = str(item.get("color") or "").strip()

    bits = [title]
    if volume and volume.lower() not in title.lower():
        bits.append(volume)
    label = " ".join(bits)
    extras = []
    if flavors:
        extras.append(", ".join(flavors))
    if color:
        extras.append(color)
    if extras:
        label = f"{label} / {' / '.join(extras)}"
    return label


def format_order_message(order: dict[str, Any]) -> str:
    """Build HTML message matching the admin Telegram screenshot."""
    order_id = _escape_html(order.get("id") or "")
    customer = _escape_html(order.get("customer_name") or "")
    phone_raw = str(order.get("phone") or "").strip()
    email_raw = str(order.get("email") or "").strip()
    phone = _escape_html(phone_raw)
    email = _escape_html(email_raw)

    city = str(order.get("city") or "").strip()
    postal = str(order.get("postal_code") or "").strip()
    address = str(order.get("address") or "").strip()
    delivery_type = str(order.get("delivery_type") or "office").strip()

    location_parts = [p for p in [address, f"{postal} {city}".strip() if postal or city else ""] if p]
    location = ", ".join(location_parts)
    if location and "българия" not in location.lower() and "bulgaria" not in location.lower():
        location = f"{location}, България"
    location = _escape_html(location)

    if delivery_type == "address":
        place_label = "Адрес"
    else:
        place_label = "Офис на Еконт"

    lines = [
        f"<b>Нова поръчка</b> {_escape_html(order_id)}",
        "",
        f"<b>Клиент:</b> {customer}",
    ]
    if phone_raw:
        tel_href = urllib.parse.quote(phone_raw.replace(" ", ""), safe="+")
        lines.append(f'<b>Телефон:</b> <a href="tel:{tel_href}">{phone}</a>')
    if email_raw:
        lines.append(f'<b>Имейл:</b> <a href="mailto:{email_raw}">{email}</a>')
    if location:
        lines.append(f"<b>{place_label}:</b> {location}")

    lines.extend(["", "<b>Артикули:</b>"])
    items = order.get("items") or []
    if not items:
        lines.append("—")
    else:
        for item in items:
            if not isinstance(item, dict):
                continue
            qty = max(1, int(item.get("qty") or 1))
            unit = float(item.get("unit_price") or 0)
            line_total = unit * qty
            label = _escape_html(_item_label(item))
            lines.append(f"{qty} × {label} — {_escape_html(_eur(line_total))}")

    subtotal = order.get("subtotal")
    if subtotal is None:
        subtotal = sum(
            float(i.get("unit_price") or 0) * max(1, int(i.get("qty") or 1))
            for i in items
            if isinstance(i, dict)
        )

    lines.extend(
        [
            "",
            f"<b>Артикули общо:</b> {_escape_html(_eur(subtotal))}",
            # Screenshot wording: shipping calculated later / additionally.
            "<b>Доставка:</b> изчислява се при изпращане (допълнително)",
            "<b>Плащане:</b> Наложен платеж",
            "<b>Статус:</b> unprocessed",
        ]
    )
    return "\n".join(lines)


def send_message(text: str, *, chat_id: str | None = None) -> bool:
    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chat = (chat_id or os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
    if not token or not chat:
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8") or "{}")
            return bool(body.get("ok"))
    except urllib.error.HTTPError as exc:
        err = ""
        try:
            err = exc.read().decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass
        print(f"[telegram] send failed: {exc.code} {err}", flush=True)
        return False
    except Exception as exc:  # noqa: BLE001
        print(f"[telegram] send failed: {exc}", flush=True)
        return False


def notify_new_order(order: dict[str, Any]) -> bool:
    if not configured():
        print("[telegram] skipped (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set)", flush=True)
        return False
    return send_message(format_order_message(order))
