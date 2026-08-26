"""
Central Live Quote Store

Single source of truth for normalized broker ticks.
"""

from __future__ import annotations

from threading import RLock
from typing import Dict, Optional


LIVE_QUOTES = {}

_LOCK = RLock()


def quote_key(exchange: str, token: str) -> str:
    return f"{exchange}|{token}"


def update_live_quote(tick: dict) -> dict:
    """
    Single ownership point for live quote updates.

    Expected normalized tick:

    {
        "exchange": "nse_fo",
        "token": "12345",
        "symbol": "NIFTY...",
        "ltp": 25000.0,
        ...
    }
    """

    exchange = str(tick.get("exchange") or "")
    token = str(tick.get("token") or "")

    if not exchange or not token:
        raise ValueError(
            "Live tick requires exchange and token"
        )

    key = quote_key(exchange, token)

    with _LOCK:
        previous = LIVE_QUOTES.get(key, {})

        merged = {
            **previous,
            **tick,
        }

        LIVE_QUOTES[key] = merged

    return merged


def get_live_quote(
    exchange: str,
    token: str,
) -> Optional[dict]:

    key = quote_key(exchange, token)

    with _LOCK:
        quote = LIVE_QUOTES.get(key)

        return dict(quote) if quote else None


def get_all_live_quotes() -> Dict[str, dict]:

    with _LOCK:
        return {
            key: dict(value)
            for key, value in LIVE_QUOTES.items()
        }


def clear_live_quotes():

    with _LOCK:
        LIVE_QUOTES.clear()
