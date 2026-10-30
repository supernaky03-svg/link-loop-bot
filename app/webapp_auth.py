from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl


class InitDataError(ValueError):
    """Telegram Mini App initData validation error."""


def validate_telegram_init_data(
    init_data: str,
    bot_token: str,
    *,
    now: int | None = None,
    max_age_seconds: int = 86_400,
) -> dict:
    """Validate Telegram WebApp initData using Telegram's bot-token HMAC scheme."""
    if not init_data or len(init_data) > 16_384:
        raise InitDataError("Missing or oversized Telegram initData")
    try:
        pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
    except (TypeError, ValueError) as exc:
        raise InitDataError("Malformed Telegram initData") from exc
    values = dict(pairs)
    if len(values) != len(pairs):
        raise InitDataError("Duplicate Telegram initData fields")

    received_hash = values.pop("hash", None)
    if not received_hash or len(received_hash) != 64:
        raise InitDataError("Missing Telegram initData hash")
    check_string = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    expected = hmac.new(secret_key, check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        raise InitDataError("Invalid Telegram initData signature")

    try:
        auth_date = int(values.get("auth_date", "0"))
        user = json.loads(values["user"])
        user_id = int(user["id"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise InitDataError("Invalid Telegram user payload") from exc
    if not isinstance(user, dict) or user_id <= 0:
        raise InitDataError("Invalid Telegram user")

    current = int(time.time()) if now is None else int(now)
    if auth_date <= 0 or auth_date > current + 300 or current - auth_date > max_age_seconds:
        raise InitDataError("Telegram initData has expired")
    return {"user": user, "auth_date": auth_date, "query_id": values.get("query_id")}
