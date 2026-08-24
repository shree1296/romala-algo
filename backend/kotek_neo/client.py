"""Kotak Neo API client wrapper.

Wraps the neo_api_client SDK with session management, error handling,
and normalized return values. Uses the real Kotak Neo API exclusively.
"""
from __future__ import annotations

import os
import json
import time
import logging
from typing import Any, Callable

logger = logging.getLogger("romala.kotak")

try:
    from neo_api_client import NeoAPI
except Exception as _import_err:
    NeoAPI = None
    logger.warning(f"neo_api_client not installed: {_import_err}")


class KotakNeoClient:
    """Singleton wrapper around NeoAPI."""

    _instance: KotakNeoClient | None = None

    def __new__(cls) -> KotakNeoClient:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self.client: Any = None
        self.connected = False
        self.user_info: dict[str, str] = {}
        self.credentials: dict[str, str] = {}
        self.consumer_key = os.getenv("NEO_CONSUMER_KEY", "")
        self._tick_callbacks: list[Callable[[dict], None]] = []

    def login(self, credentials: dict[str, str]) -> dict[str, Any]:
        """Login to Kotak Neo with TOTP flow."""
        self.credentials = credentials
        self.consumer_key = credentials.get("consumer_key", self.consumer_key)

        if NeoAPI is None:
            raise RuntimeError(
                "neo_api_client SDK is not installed. "
                "Run: pip install git+https://github.com/Kotak-Neo/Kotak-neo-api-v2.git"
            )
        try:
            self.client = NeoAPI(
                environment="prod",
                access_token=None,
                neo_fin_key=None,
                consumer_key=self.consumer_key,
            )
            self.client.on_message = self._on_message
            self.client.on_error = self._on_error

            # Session init
            self.client.session_init(
                mobilenumber=credentials.get("mobile_number", ""),
                password=credentials.get("password", ""),
            )

            # TOTP login
            self.client.totp_login(
                mpin=credentials.get("mpin", ""),
                totp=credentials.get("totp", ""),
            )

            # Verify 2FA
            self.client.totp_verify()

            self.connected = True
            self.user_info = {
                "user_id": "NEO_USER",
                "user_name": "Kotak Neo Trader",
                "email": "",
                "account_id": "",
            }
            logger.info("Kotak Neo login successful")
            return self._status()

        except Exception as e:
            logger.error(f"Kotak Neo login failed: {e}")
            self.connected = False
            raise

    def auto_login(self) -> dict[str, Any]:
        """Auto-login using credentials from environment variables.

        Reads NEO_MOBILE_NUMBER, NEO_PASSWORD, NEO_MPIN, NEO_TOTP_SECRET
        from the environment. Generates the current TOTP code from the
        secret key using pyotp, so no manual TOTP entry is needed.
        """
        import os
        try:
            import pyotp
        except ImportError:
            raise RuntimeError("pyotp is not installed. Run: pip install pyotp")

        mobile = os.getenv("NEO_MOBILE_NUMBER", "")
        password = os.getenv("NEO_PASSWORD", "")
        mpin = os.getenv("NEO_MPIN", "")
        totp_secret = os.getenv("NEO_TOTP_SECRET", "")

        if not all([mobile, password, mpin, totp_secret]):
            missing = [k for k, v in {
                "NEO_MOBILE_NUMBER": mobile,
                "NEO_PASSWORD": password,
                "NEO_MPIN": mpin,
                "NEO_TOTP_SECRET": totp_secret,
            }.items() if not v]
            raise RuntimeError(f"Auto-login missing env vars: {', '.join(missing)}")

        totp_code = pyotp.TOTP(totp_secret).now()
        logger.info("Auto-login: generated TOTP from secret key")

        return self.login({
            "mobile_number": mobile,
            "password": password,
            "mpin": mpin,
            "totp": totp_code,
        })

    def logout(self) -> dict[str, str]:
        if self.client and self.connected:
            try:
                self.client.logout()
            except Exception as e:
                logger.warning(f"Logout error: {e}")
        self.connected = False
        self.client = None
        self.user_info = {}
        return {"status": "disconnected"}

    def _status(self) -> dict[str, Any]:
        return {
            "status": "connected" if self.connected else "disconnected",
            "broker": "Kotak Neo",
            "user_id": self.user_info.get("user_id"),
            "user_name": self.user_info.get("user_name"),
            "email": self.user_info.get("email"),
            "account_id": self.user_info.get("account_id"),
            "message": "Connected and authenticated" if self.connected else "Not connected — please login",
            "last_connected": int(time.time() * 1000) if self.connected else None,
        }

    # ─── Market Data ───

    def quotes(self, instrument_tokens: list[dict], quote_type: str = "all") -> list[dict]:
        """Get quotes for given instruments from Kotak Neo."""
        try:
            return self.client.quotes(instrument_tokens=instrument_tokens, quote_type=quote_type)
        except Exception as e:
            logger.error(f"Quotes error: {e}")
            return []

    def scrip_master(self, exchange_segment: str = "") -> list[dict]:
        """Get scrip master list from Kotak Neo."""
        try:
            return self.client.scrip_master(exchange_segment=exchange_segment)
        except Exception as e:
            logger.error(f"Scrip master error: {e}")
            return []

    def search_scrip(self, segment: str, symbol: str, expiry: str = "", option_type: str = "", strike_price: str = "") -> list[dict]:
        try:
            return self.client.search_scrip(
                exchange_segment=segment, symbol=symbol,
                expiry=expiry, option_type=option_type, strike_price=strike_price,
            )
        except Exception as e:
            logger.error(f"Search scrip error: {e}")
            return []

    # ─── Orders ───

    def place_order(self, **kwargs) -> dict:
        """Place an order through Kotak Neo."""
        return self.client.place_order(**kwargs)

    def modify_order(self, order_id: str, **kwargs) -> dict:
        return self.client.modify_order(order_id=order_id, **kwargs)

    def cancel_order(self, order_id: str, **kwargs) -> dict:
        return self.client.cancel_order(order_id=order_id, **kwargs)

    def order_report(self) -> list[dict]:
        """Get order book from Kotak Neo."""
        try:
            return self.client.order_report()
        except Exception as e:
            logger.error(f"Order report error: {e}")
            return []

    def order_history(self, order_id: str) -> dict:
        try:
            return self.client.order_history(order_id=order_id)
        except Exception as e:
            logger.error(f"Order history error: {e}")
            return {}

    def trade_report(self, order_id: str = "") -> list[dict]:
        try:
            return self.client.trade_report(order_id=order_id) if order_id else self.client.trade_report()
        except Exception as e:
            logger.error(f"Trade report error: {e}")
            return []

    # ─── Portfolio ───

    def positions(self) -> list[dict]:
        try:
            return self.client.positions()
        except Exception as e:
            logger.error(f"Positions error: {e}")
            return []

    def holdings(self) -> list[dict]:
        try:
            return self.client.holdings()
        except Exception as e:
            logger.error(f"Holdings error: {e}")
            return []

    def limits(self, segment: str = "ALL", exchange: str = "ALL", product: str = "ALL") -> dict:
        try:
            return self.client.limits(segment=segment, exchange=exchange, product=product)
        except Exception as e:
            logger.error(f"Limits error: {e}")
            return {"available_margin": 0, "utilised_margin": 0, "total_margin": 0, "realised": 0, "unrealised": 0, "total": 0}

    def margin_required(self, **kwargs) -> dict:
        try:
            return self.client.margin_required(**kwargs)
        except Exception as e:
            logger.error(f"Margin required error: {e}")
            return {"margin_required": 0}

    # ─── WebSocket ───

    def on_tick(self, callback: Callable[[dict], None]) -> None:
        self._tick_callbacks.append(callback)

    def off_tick(self, callback: Callable[[dict], None]) -> None:
        if callback in self._tick_callbacks:
            self._tick_callbacks.remove(callback)

    def _on_message(self, message: Any) -> None:
        if not message:
            return
        try:
            data = json.loads(message) if isinstance(message, str) else message
        except Exception:
            data = message
        logger.debug(f"Neo tick: {data}")
        for cb in self._tick_callbacks:
            try:
                cb(data)
            except Exception as e:
                logger.warning(f"tick callback error: {e}")

    def _on_error(self, error: Any) -> None:
        logger.error(f"Neo WS error: {error}")

    def subscribe(self, instrument_tokens: list[dict], isIndex: bool = False, isDepth: bool = False) -> dict:
        try:
            return self.client.subscribe(instrument_tokens=instrument_tokens, isIndex=isIndex, isDepth=isDepth)
        except Exception as e:
            logger.error(f"Subscribe error: {e}")
        return {"status": "ok"}

    def unsubscribe(self, instrument_tokens: list[dict], isIndex: bool = False, isDepth: bool = False) -> dict:
        try:
            return self.client.un_subscribe(instrument_tokens=instrument_tokens, isIndex=isIndex, isDepth=isDepth)
        except Exception:
            pass
        return {"status": "ok"}

    def subscribe_orderfeed(self) -> dict:
        try:
            return self.client.subscribe_to_orderfeed()
        except Exception:
            pass
        return {"status": "ok"}
