"""
Broker Tick Normalization

Converts Kotak and future broker ticks into one
canonical internal market-data format.
"""

from __future__ import annotations

from typing import Any, Dict


class TickNormalizer:

    @staticmethod
    def _number(value, default=None):

        if value is None:
            return default

        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @classmethod
    def normalize_kotak(
        cls,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:

        """
        Kotak WebSocket mapping.

        tk   -> token
        ts   -> trading symbol
        e    -> exchange
        ltp  -> last traded price
        ltq  -> last traded quantity
        oi   -> open interest
        bp   -> best bid
        sp   -> best ask
        """

        return {
            "broker": "KOTAK",

            "exchange": (
                payload.get("e")
                or payload.get("exchange")
                or ""
            ),

            "token": str(
                payload.get("tk")
                or payload.get("token")
                or ""
            ),

            "symbol": (
                payload.get("ts")
                or payload.get("symbol")
                or ""
            ),

            "ltp": cls._number(
                payload.get("ltp")
            ),

            "ltq": cls._number(
                payload.get("ltq")
            ),

            "open": cls._number(
                payload.get("op")
            ),

            "high": cls._number(
                payload.get("h")
            ),

            "low": cls._number(
                payload.get("lo")
            ),

            "close": cls._number(
                payload.get("c")
            ),

            "change": cls._number(
                payload.get("cng")
            ),

            "change_percent": cls._number(
                payload.get("nc")
            ),

            "bid_price": cls._number(
                payload.get("bp")
            ),

            "bid_qty": cls._number(
                payload.get("bq")
            ),

            "ask_price": cls._number(
                payload.get("sp")
            ),

            "ask_qty": cls._number(
                payload.get("bs")
            ),

            "total_buy_qty": cls._number(
                payload.get("tbq")
            ),

            "total_sell_qty": cls._number(
                payload.get("tsq")
            ),

            "volume": cls._number(
                payload.get("v")
                or payload.get("vol")
            ),

            "oi": cls._number(
                payload.get("oi")
            ),

            "average_price": cls._number(
                payload.get("ap")
            ),

            "turnover": cls._number(
                payload.get("to")
            ),

            "last_trade_time": (
                payload.get("ltt")
            ),

            "feed_time": (
                payload.get("fdtm")
            ),

            "raw": payload,
        }
