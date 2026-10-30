from __future__ import annotations

import hashlib
import hmac
import json
from urllib.parse import urlencode

import pytest

from app.webapp_auth import InitDataError, validate_telegram_init_data


def signed_data(token: str, now: int) -> str:
    fields = {
        "auth_date": str(now),
        "query_id": "test-query-id",
        "user": json.dumps({"id": 123456789, "username": "tester"}, separators=(",", ":")),
    }
    check = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


def test_valid_init_data():
    result = validate_telegram_init_data(signed_data("123:token", 1_800_000_000), "123:token", now=1_800_000_010)
    assert result["user"]["id"] == 123456789


def test_rejects_tampered_data():
    raw = signed_data("123:token", 1_800_000_000).replace("tester", "attacker")
    with pytest.raises(InitDataError, match="signature"):
        validate_telegram_init_data(raw, "123:token", now=1_800_000_010)


def test_rejects_expired_data():
    raw = signed_data("123:token", 1_700_000_000)
    with pytest.raises(InitDataError, match="expired"):
        validate_telegram_init_data(raw, "123:token", now=1_800_000_000)


def test_rejects_duplicate_fields():
    raw = signed_data("123:token", 1_800_000_000) + "&auth_date=1800000000"
    with pytest.raises(InitDataError, match="Duplicate"):
        validate_telegram_init_data(raw, "123:token", now=1_800_000_010)
