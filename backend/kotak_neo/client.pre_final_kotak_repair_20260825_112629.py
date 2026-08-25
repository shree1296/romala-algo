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

    def login(self, credentials):
        """
        Authenticate Kotak Neo using the installed SDK contract.

        Flow:
            NeoAPI(...)
                ->
            totp_login(...)
                ->
            totp_validate(mpin=...)

        No order operation is performed here.
        """

        def _value(source, *names):
            for name in names:
                if isinstance(source, dict):
                    value = source.get(name)
                else:
                    value = getattr(source, name, None)

                if value is not None and str(value).strip():
                    return str(value).strip()

            return None

        consumer_key = _value(
            credentials,
            "consumer_key",
            "api_key",
            "KOTAK_CONSUMER_KEY",
        )

        mobile_number = _value(
            credentials,
            "mobile_number",
            "mobile",
            "KOTAK_MOBILE_NUMBER",
        )

        ucc = _value(
            credentials,
            "ucc",
            "user_id",
            "account_id",
            "KOTAK_UCC",
        )

        mpin = _value(
            credentials,
            "mpin",
            "KOTAK_MPIN",
        )

        totp = _value(
            credentials,
            "totp",
            "KOTAK_TOTP",
        )

        missing = []

        if not consumer_key:
            missing.append("consumer_key")

        if not mobile_number:
            missing.append("mobile_number")

        if not ucc:
            missing.append("ucc")

        if not mpin:
            missing.append("mpin")

        if not totp:
            missing.append("totp")

        if missing:
            raise ValueError(
                "Missing Kotak authentication fields: "
                + ", ".join(missing)
            )

        # The installed SDK contract does not expose session_init().
        from neo_api_client import NeoAPI

        self.client = NeoAPI(
            consumer_key=consumer_key,
            environment="prod",
        )

        login_response = self.client.totp_login(
            mobile_number=mobile_number,
            ucc=ucc,
            totp=totp,
        )

        if not isinstance(login_response, dict):
            raise RuntimeError(
                "Unexpected response type from totp_login(): "
                + type(login_response).__name__
            )

        if login_response.get("error"):
            raise RuntimeError(
                "Kotak TOTP login failed: "
                + str(login_response.get("error"))
            )

        validation_response = self.client.totp_validate(
            mpin=mpin
        )

        if not isinstance(validation_response, dict):
            raise RuntimeError(
                "Unexpected response type from totp_validate(): "
                + type(validation_response).__name__
            )

        if validation_response.get("error"):
            raise RuntimeError(
                "Kotak MPIN validation failed: "
                + str(validation_response.get("error"))
            )

        # Set common facade state only when these attributes already
        # exist or can safely be attached to this wrapper object.
        self.connected = True

        return {
            "status": "success",
            "authenticated": True,
            "broker": "Kotak Neo",
            "login_response": login_response,
            "validation_response": validation_response,
        }

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
