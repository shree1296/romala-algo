"""
Kotak Neo API client wrapper.

Responsibilities:

- Authentication
- TOTP / MPIN validation
- SDK session lifecycle
- Account connection state
- Market data
- Orders
- Portfolio
- WebSocket subscriptions

This wrapper uses the official installed neo_api_client SDK.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
import os
import time
from typing import Any, Callable, Optional


logger = logging.getLogger("romala.kotak")


# ============================================================
# KOTAK NEO SDK IMPORT
# ============================================================

NeoAPI: Any | None = None
NEO_IMPORT_ERROR: Exception | None = None


try:
    from neo_api_client import NeoAPI as _NeoAPI

    NeoAPI = _NeoAPI

except Exception as exc:

    NEO_IMPORT_ERROR = exc

    logger.exception(
        "neo_api_client could not be imported."
    )


# ============================================================
# CLIENT
# ============================================================

class KotakNeoClient:
    """
    Singleton wrapper around Kotak Neo SDK.
    """

    _instance: Optional["KotakNeoClient"] = None


    def __new__(cls) -> "KotakNeoClient":

        if cls._instance is None:

            cls._instance = super().__new__(cls)

            cls._instance._initialized = False

        return cls._instance


    def __init__(self) -> None:

        if self._initialized:
            return

        self._initialized = True

        self.client: Any = None

        self.connected: bool = False

        self.user_info: dict[str, Any] = {}

        self.credentials: dict[str, str] = {}

        self.consumer_key = (
            os.getenv("KOTAK_CONSUMER_KEY", "")
            or os.getenv("NEO_CONSUMER_KEY", "")
        ).strip()

        self.last_connected: Optional[int] = None

        self._tick_callbacks: list[
            Callable[[dict], None]
        ] = []


    # ========================================================
    # INTERNAL HELPERS
    # ========================================================

    def _require_connection(self) -> None:

        if not self.connected or self.client is None:

            raise RuntimeError(
                "Kotak Neo client is not connected. "
                "Please login first."
            )


    @staticmethod
    def _value(
        source: Any,
        *names: str,
    ) -> Optional[str]:

        for name in names:

            if isinstance(source, dict):

                value = source.get(name)

            else:

                value = getattr(
                    source,
                    name,
                    None,
                )

            if value is not None:

                value = str(value).strip()

                if value:

                    return value

        return None


    @staticmethod
    def _extract_user_info(
        *responses: Any,
        fallback_ucc: Optional[str] = None,
    ) -> dict[str, Any]:

        result: dict[str, Any] = {}

        def walk(data: Any) -> None:

            if isinstance(data, dict):

                mappings = {
                    "user_id": [
                        "user_id",
                        "userid",
                        "userId",
                        "ucc",
                        "account_id",
                        "accountId",
                    ],

                    "user_name": [
                        "user_name",
                        "username",
                        "userName",
                        "name",
                        "client_name",
                    ],

                    "email": [
                        "email",
                        "email_id",
                        "emailId",
                    ],

                    "account_id": [
                        "account_id",
                        "accountId",
                        "ucc",
                    ],
                }

                for target, keys in mappings.items():

                    if target in result:
                        continue

                    for key in keys:

                        value = data.get(key)

                        if value not in (
                            None,
                            "",
                        ):

                            result[target] = value

                            break

                for value in data.values():

                    if isinstance(
                        value,
                        (dict, list),
                    ):

                        walk(value)

            elif isinstance(data, list):

                for item in data:

                    walk(item)


        for response in responses:

            walk(response)

        if fallback_ucc:

            result.setdefault(
                "user_id",
                fallback_ucc,
            )

            result.setdefault(
                "account_id",
                fallback_ucc,
            )

        return result


    @staticmethod
    def _prepare_totp(
        value: str,
    ) -> str:
        """
        Accept either:

        1. Current six-digit OTP
        2. Base32 TOTP secret
        """

        value = value.strip()

        # ----------------------------------------------------
        # CURRENT 6 DIGIT OTP
        # ----------------------------------------------------

        if value.isdigit() and len(value) == 6:

            return value


        # ----------------------------------------------------
        # BASE32 SECRET
        # ----------------------------------------------------

        normalized = (
            value
            .replace(" ", "")
            .replace("-", "")
            .upper()
        )

        try:

            # Validate Base32 before passing to pyotp.
            padding = "=" * (
                (-len(normalized)) % 8
            )

            base64.b32decode(
                normalized + padding,
                casefold=True,
            )

        except (
            binascii.Error,
            ValueError,
        ) as exc:

            raise RuntimeError(
                "KOTAK_TOTP must be either a current "
                "six-digit OTP or a valid Base32 TOTP secret."
            ) from exc


        try:

            import pyotp

        except ImportError as exc:

            raise RuntimeError(
                "pyotp is required when KOTAK_TOTP "
                "contains a Base32 secret."
            ) from exc


        try:

            return pyotp.TOTP(
                normalized
            ).now()

        except Exception as exc:

            raise RuntimeError(
                "Unable to generate OTP from "
                "KOTAK_TOTP Base32 secret."
            ) from exc


    # ========================================================
    # LOGIN
    # ========================================================

    def login(
        self,
        credentials: Any,
    ) -> dict[str, Any]:

        consumer_key = self._value(
            credentials,
            "consumer_key",
            "api_key",
            "KOTAK_CONSUMER_KEY",
            "NEO_CONSUMER_KEY",
        )

        mobile_number = self._value(
            credentials,
            "mobile_number",
            "mobile",
            "KOTAK_MOBILE_NUMBER",
        )

        ucc = self._value(
            credentials,
            "ucc",
            "user_id",
            "account_id",
            "KOTAK_UCC",
        )

        mpin = self._value(
            credentials,
            "mpin",
            "KOTAK_MPIN",
        )

        totp = self._value(
            credentials,
            "totp",
            "KOTAK_TOTP",
        )


        # ----------------------------------------------------
        # VALIDATE
        # ----------------------------------------------------

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


        if NeoAPI is None:

            raise RuntimeError(
                "Kotak Neo SDK is unavailable. "
                f"Import error: {NEO_IMPORT_ERROR}"
            )


        # ----------------------------------------------------
        # RESET OLD SESSION
        # ----------------------------------------------------

        self.connected = False

        self.client = None

        self.user_info = {}

        self.last_connected = None


        # ----------------------------------------------------
        # CREATE SDK CLIENT
        # ----------------------------------------------------

        try:

            client = NeoAPI(
                consumer_key=consumer_key,
                environment="prod",
            )

        except Exception as exc:

            raise RuntimeError(
                "Failed to initialize Kotak Neo SDK: "
                f"{exc}"
            ) from exc


        # ----------------------------------------------------
        # TOTP LOGIN
        # ----------------------------------------------------

        try:

            login_response = client.totp_login(
                mobile_number=mobile_number,
                ucc=ucc,
                totp=totp,
            )

        except Exception as exc:

            raise RuntimeError(
                "Kotak TOTP login request failed: "
                f"{exc}"
            ) from exc


        if not isinstance(
            login_response,
            dict,
        ):

            raise RuntimeError(
                "Unexpected response type from "
                "Kotak totp_login(): "
                f"{type(login_response).__name__}"
            )


        if login_response.get("error"):

            raise RuntimeError(
                "Kotak TOTP login failed: "
                + str(
                    login_response.get("error")
                )
            )


        # ----------------------------------------------------
        # MPIN VALIDATION
        # ----------------------------------------------------

        try:

            validation_response = (
                client.totp_validate(
                    mpin=mpin
                )
            )

        except Exception as exc:

            raise RuntimeError(
                "Kotak MPIN validation request failed: "
                f"{exc}"
            ) from exc


        if not isinstance(
            validation_response,
            dict,
        ):

            raise RuntimeError(
                "Unexpected response type from "
                "Kotak totp_validate(): "
                f"{type(validation_response).__name__}"
            )


        if validation_response.get("error"):

            raise RuntimeError(
                "Kotak MPIN validation failed: "
                + str(
                    validation_response.get("error")
                )
            )


        # ----------------------------------------------------
        # SESSION SUCCESS
        # ----------------------------------------------------

        self.client = client

        self.connected = True

        self.last_connected = (
            int(time.time() * 1000)
        )

        self.credentials = {
            "consumer_key": consumer_key,
            "mobile_number": mobile_number,
            "ucc": ucc,
        }

        self.user_info = (
            self._extract_user_info(
                login_response,
                validation_response,
                fallback_ucc=ucc,
            )
        )


        logger.info(
            "Kotak Neo login successful for UCC ending in %s",
            ucc[-4:] if len(ucc) >= 4 else "****",
        )


        return {

            "status": "success",

            "authenticated": True,

            "connected": True,

            "broker": "Kotak Neo",

            "user_info": self.user_info,

            "login_response": login_response,

            "validation_response": validation_response,
        }


    # ========================================================
    # AUTO LOGIN
    # ========================================================

    def auto_login(
        self,
    ) -> dict[str, Any]:

        consumer_key = (
            os.getenv(
                "KOTAK_CONSUMER_KEY",
                "",
            )
            or os.getenv(
                "NEO_CONSUMER_KEY",
                "",
            )
        ).strip()

        mobile = os.getenv(
            "KOTAK_MOBILE_NUMBER",
            "",
        ).strip()

        ucc = os.getenv(
            "KOTAK_UCC",
            "",
        ).strip()

        mpin = os.getenv(
            "KOTAK_MPIN",
            "",
        ).strip()

        totp_value = os.getenv(
            "KOTAK_TOTP",
            "",
        ).strip()


        values = {

            "KOTAK_CONSUMER_KEY":
                consumer_key,

            "KOTAK_MOBILE_NUMBER":
                mobile,

            "KOTAK_UCC":
                ucc,

            "KOTAK_MPIN":
                mpin,

            "KOTAK_TOTP":
                totp_value,
        }


        missing = [

            name

            for name, value

            in values.items()

            if not value
        ]


        if missing:

            raise RuntimeError(
                "Auto-login missing environment variables: "
                + ", ".join(missing)
            )


        # Generate / validate TOTP

        totp_code = self._prepare_totp(
            totp_value
        )


        logger.info(
            "Kotak Neo auto-login starting."
        )


        return self.login({

            "consumer_key":
                consumer_key,

            "mobile_number":
                mobile,

            "ucc":
                ucc,

            "mpin":
                mpin,

            "totp":
                totp_code,
        })


    # ========================================================
    # LOGOUT
    # ========================================================

    def logout(
        self,
    ) -> dict[str, str]:

        if self.client is not None:

            try:

                logout_method = getattr(
                    self.client,
                    "logout",
                    None,
                )

                if callable(
                    logout_method
                ):

                    logout_method()

            except Exception as exc:

                logger.warning(
                    "Kotak logout error: %s",
                    exc,
                )


        self.connected = False

        self.client = None

        self.user_info = {}

        self.credentials = {}

        self.last_connected = None


        return {

            "status":
                "disconnected"
        }


    # ========================================================
    # STATUS
    # ========================================================

    def _status(
        self,
    ) -> dict[str, Any]:

        return {

            "status":
                (
                    "connected"
                    if self.connected
                    else "disconnected"
                ),

            "broker":
                "Kotak Neo",

            "user_id":
                self.user_info.get(
                    "user_id"
                ),

            "user_name":
                self.user_info.get(
                    "user_name"
                ),

            "email":
                self.user_info.get(
                    "email"
                ),

            "account_id":
                self.user_info.get(
                    "account_id"
                ),

            "message":

                (
                    "Connected and authenticated"
                    if self.connected
                    else "Not connected - please login"
                ),

            "last_connected":
                self.last_connected,

            "connected":
                self.connected,
        }


    # ========================================================
    # MARKET DATA
    # ========================================================

    def quotes(
        self,
        instrument_tokens: list[dict],
        quote_type: str = "all",
    ) -> list[dict]:

        self._require_connection()


        try:

            response = self.client.quotes(
                instrument_tokens=instrument_tokens,
                quote_type=quote_type,
            )


        except Exception as exc:

            logger.exception(
                "Kotak Neo quotes request failed."
            )

            raise RuntimeError(
                "Unable to fetch Kotak Neo quotes: "
                f"{exc}"
            ) from exc


        if response is None:

            return []


        if isinstance(
            response,
            list,
        ):

            return response


        if isinstance(
            response,
            dict,
        ):

            data = response.get(
                "data"
            )

            if isinstance(
                data,
                list,
            ):

                return data

            return [
                response
            ]


        raise RuntimeError(
            "Unexpected Kotak quotes response type: "
            f"{type(response).__name__}"
        )


    def scrip_master(
        self,
        exchange_segment: str = "",
    ) -> Any:

        self._require_connection()

        return self.client.scrip_master(
            exchange_segment=exchange_segment
        )


    def search_scrip(
        self,
        segment: str,
        symbol: str,
        expiry: str = "",
        option_type: str = "",
        strike_price: str = "",
    ) -> Any:

        self._require_connection()

        return self.client.search_scrip(

            exchange_segment=segment,

            symbol=symbol,

            expiry=expiry,

            option_type=option_type,

            strike_price=strike_price,
        )


    # ========================================================
    # ORDERS
    # ========================================================

    def place_order(
        self,
        **kwargs,
    ) -> Any:

        self._require_connection()

        return self.client.place_order(
            **kwargs
        )


    def modify_order(
        self,
        order_id: str,
        **kwargs,
    ) -> Any:

        self._require_connection()

        return self.client.modify_order(

            order_id=order_id,

            **kwargs,
        )


    def cancel_order(
        self,
        order_id: str,
        **kwargs,
    ) -> Any:

        self._require_connection()

        return self.client.cancel_order(

            order_id=order_id,

            **kwargs,
        )


    def order_report(
        self,
    ) -> Any:

        self._require_connection()

        return self.client.order_report()


    def order_history(
        self,
        order_id: str,
    ) -> Any:

        self._require_connection()

        return self.client.order_history(
            order_id=order_id
        )


    def trade_report(
        self,
        order_id: str = "",
    ) -> Any:

        self._require_connection()

        if order_id:

            return self.client.trade_report(
                order_id=order_id
            )

        return self.client.trade_report()


    # ========================================================
    # PORTFOLIO
    # ========================================================

    def positions(
        self,
    ) -> Any:

        self._require_connection()

        return self.client.positions()


    def holdings(
        self,
    ) -> Any:

        self._require_connection()

        return self.client.holdings()


    def limits(
        self,
        segment: str = "ALL",
        exchange: str = "ALL",
        product: str = "ALL",
    ) -> Any:

        self._require_connection()

        return self.client.limits(

            segment=segment,

            exchange=exchange,

            product=product,
        )


    def margin_required(
        self,
        **kwargs,
    ) -> Any:

        self._require_connection()

        return self.client.margin_required(
            **kwargs
        )


    # ========================================================
    # WEBSOCKET CALLBACKS
    # ========================================================

    def on_tick(
        self,
        callback: Callable[[dict], None],
    ) -> None:

        if callback not in (
            self._tick_callbacks
        ):

            self._tick_callbacks.append(
                callback
            )


    def off_tick(
        self,
        callback: Callable[[dict], None],
    ) -> None:

        if callback in (
            self._tick_callbacks
        ):

            self._tick_callbacks.remove(
                callback
            )


    def _on_message(
        self,
        message: Any,
    ) -> None:

        if not message:

            return


        try:

            data = (

                json.loads(message)

                if isinstance(
                    message,
                    str,
                )

                else message
            )

        except Exception:

            data = message


        logger.debug(
            "Kotak Neo tick: %s",
            data,
        )


        for callback in list(
            self._tick_callbacks
        ):

            try:

                callback(
                    data
                )

            except Exception:

                logger.exception(
                    "Kotak tick callback failed."
                )


    def _on_error(
        self,
        error: Any,
    ) -> None:

        logger.error(
            "Kotak WebSocket error: %s",
            error,
        )


    # ========================================================
    # SUBSCRIPTIONS
    # ========================================================

    def subscribe(
        self,
        instrument_tokens: list[dict],
        isIndex: bool = False,
        isDepth: bool = False,
    ) -> Any:

        self._require_connection()

        return self.client.subscribe(

            instrument_tokens=instrument_tokens,

            isIndex=isIndex,

            isDepth=isDepth,
        )


    def unsubscribe(
        self,
        instrument_tokens: list[dict],
        isIndex: bool = False,
        isDepth: bool = False,
    ) -> Any:

        self._require_connection()

        return self.client.un_subscribe(

            instrument_tokens=instrument_tokens,

            isIndex=isIndex,

            isDepth=isDepth,
        )


    def subscribe_orderfeed(
        self,
    ) -> Any:

        self._require_connection()

        return self.client.subscribe_to_orderfeed()