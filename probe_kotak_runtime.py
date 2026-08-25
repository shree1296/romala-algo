"""
ROMALA ALGO — KOTAK NEO SFEED FINAL CONTRACT PROBE

READ-ONLY SDK FORENSIC INSPECTION.

Does NOT:
- modify repository files
- modify .env
- authenticate
- open WebSocket
- subscribe to market data
- place/modify/cancel orders

Purpose:
Determine the exact runtime contract required to safely integrate
neo_api_client 3.0.1 SFeedWebSocket into backend/kotak_neo/client.py.
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path


SEP = "=" * 100
SUB = "-" * 100


def section(title: str) -> None:
    print()
    print(SEP)
    print(title)
    print(SEP)


def subsection(title: str) -> None:
    print()
    print(SUB)
    print(title)
    print(SUB)


def safe_source(obj, label: str) -> None:
    subsection(f"SOURCE — {label}")

    try:
        source = inspect.getsource(obj)
        lines = source.splitlines()

        print(f"[INFO] Total source lines: {len(lines)}")

        for index, line in enumerate(lines, start=1):
            print(f"{index:04d}: {line}")

    except Exception as exc:
        print(f"[WARN] Could not retrieve source: {exc}")


def inspect_callable(obj, label: str) -> None:
    subsection(f"CALLABLE — {label}")

    try:
        print(f"[INFO] Object    : {obj}")
    except Exception:
        pass

    try:
        print(f"[INFO] Module    : {obj.__module__}")
    except Exception:
        pass

    try:
        print(f"[INFO] Signature : {inspect.signature(obj)}")
    except Exception as exc:
        print(f"[WARN] Signature unavailable: {exc}")

    try:
        print(f"[INFO] Source    : {inspect.getsourcefile(obj)}")
    except Exception:
        pass


def main() -> int:

    section("ROMALA ALGO — KOTAK NEO SFEED FINAL CONTRACT PROBE")

    print("[SAFETY] READ-ONLY forensic inspection.")
    print("[SAFETY] No repository files will be modified.")
    print("[SAFETY] No .env file will be modified.")
    print("[SAFETY] No authentication API will be called.")
    print("[SAFETY] No WebSocket connection will be opened.")
    print("[SAFETY] No market-data subscription will be performed.")
    print("[SAFETY] No order API will be called.")

    section("1. PYTHON RUNTIME")

    print(f"[INFO] Python  : {sys.executable}")
    print(f"[INFO] Version : {sys.version}")

    section("2. SDK IMPORT")

    try:
        import neo_api_client

        print("[PASS] neo_api_client imported.")
        print(
            "[INFO] SDK version: "
            f"{getattr(neo_api_client, '__version__', 'UNKNOWN')}"
        )
        print(f"[INFO] SDK path   : {neo_api_client.__file__}")

    except Exception as exc:
        print(f"[FAIL] neo_api_client import failed: {exc}")
        return 1

    section("3. IMPORT SFEED COMPONENTS")

    try:
        from neo_api_client.websocket.feed import (
            SFeedWebSocket,
            WsToken,
        )

        print("[PASS] SFeedWebSocket imported.")
        print("[PASS] WsToken imported.")

    except Exception as exc:
        print(f"[FAIL] SFeed imports failed: {exc}")
        return 1

    section("4. SFEED WEBSOCKET CLASS")

    print(f"[INFO] Class  : {SFeedWebSocket}")
    print(f"[INFO] Module : {SFeedWebSocket.__module__}")

    try:
        print(
            "[INFO] Source : "
            f"{inspect.getsourcefile(SFeedWebSocket)}"
        )
    except Exception:
        pass

    try:
        print(
            "[INFO] Constructor: "
            f"{inspect.signature(SFeedWebSocket)}"
        )
    except Exception as exc:
        print(f"[WARN] Constructor signature unavailable: {exc}")

    section("5. COMPLETE PUBLIC METHOD INVENTORY")

    methods = []

    for name, member in inspect.getmembers(
        SFeedWebSocket,
        predicate=callable,
    ):
        if not name.startswith("__"):
            methods.append(name)

    if methods:
        for name in methods:
            try:
                member = getattr(SFeedWebSocket, name)
                signature = inspect.signature(member)

                print(f"[METHOD] {name}{signature}")

            except Exception:
                print(f"[METHOD] {name} (signature unavailable)")

        print()
        print(f"[INFO] Total public callable methods: {len(methods)}")

    else:
        print("[WARN] No public callable methods discovered.")

    section("6. ASYNC LIFECYCLE CONTRACT")

    lifecycle_names = [
        "__aenter__",
        "__aexit__",
        "__aiter__",
        "__anext__",
        "connect",
        "disconnect",
        "close",
        "start",
        "stop",
        "run",
    ]

    for name in lifecycle_names:

        member = getattr(SFeedWebSocket, name, None)

        if member is None:
            print(f"[MISS] {name}")
            continue

        print(f"[PASS] {name}")

        inspect_callable(
            member,
            f"SFeedWebSocket.{name}",
        )

        safe_source(
            member,
            f"SFeedWebSocket.{name}",
        )

    section("7. SUBSCRIPTION CONTRACT")

    subscription_names = [
        "subscribe_scrips",
        "unsubscribe_scrips",
        "subscribe",
        "unsubscribe",
    ]

    for name in subscription_names:

        member = getattr(SFeedWebSocket, name, None)

        if member is None:
            print(f"[MISS] {name}")
            continue

        print(f"[PASS] {name}")

        inspect_callable(
            member,
            f"SFeedWebSocket.{name}",
        )

        safe_source(
            member,
            f"SFeedWebSocket.{name}",
        )

    section("8. WsToken CONTRACT")

    print(f"[INFO] WsToken class: {WsToken}")

    try:
        print(
            "[INFO] Constructor: "
            f"{inspect.signature(WsToken)}"
        )
    except Exception as exc:
        print(f"[WARN] Signature unavailable: {exc}")

    safe_source(
        WsToken,
        "WsToken",
    )

    section("9. MESSAGE MODEL DISCOVERY")

    try:
        import neo_api_client.websocket.feed.models as models

        print(
            "[INFO] Models module: "
            f"{getattr(models, '__file__', 'UNKNOWN')}"
        )

        discovered = []

        for name, obj in inspect.getmembers(
            models,
            inspect.isclass,
        ):
            if obj.__module__ == models.__name__:
                discovered.append((name, obj))

        if not discovered:
            print("[WARN] No SDK model classes discovered.")

        for name, obj in discovered:

            print()
            print(f"[MODEL] {name}")

            try:
                print(
                    "[INFO] Constructor: "
                    f"{inspect.signature(obj)}"
                )
            except Exception:
                pass

            try:
                annotations = getattr(
                    obj,
                    "__annotations__",
                    {},
                )

                if annotations:
                    print("[FIELDS]")

                    for field_name, field_type in annotations.items():
                        print(
                            f"  - {field_name}: {field_type}"
                        )

            except Exception as exc:
                print(
                    f"[WARN] Could not inspect annotations: {exc}"
                )

    except Exception as exc:
        print(f"[WARN] Model discovery failed: {exc}")

    section("10. INTERNAL STATE / CONNECTION ATTRIBUTES")

    try:
        class_annotations = getattr(
            SFeedWebSocket,
            "__annotations__",
            {},
        )

        if class_annotations:
            print("[INFO] Class annotations:")

            for key, value in class_annotations.items():
                print(f"  - {key}: {value}")

        else:
            print(
                "[INFO] No class-level annotations found."
            )

    except Exception as exc:
        print(f"[WARN] State inspection failed: {exc}")

    section("11. FULL CLASS SOURCE")

    safe_source(
        SFeedWebSocket,
        "SFeedWebSocket",
    )

    section("12. NEOAPI CREATE_WEBSOCKET SOURCE")

    try:
        from neo_api_client import NeoAPI

        inspect_callable(
            NeoAPI.create_websocket,
            "NeoAPI.create_websocket",
        )

        safe_source(
            NeoAPI.create_websocket,
            "NeoAPI.create_websocket",
        )

    except Exception as exc:
        print(
            f"[WARN] Could not inspect NeoAPI.create_websocket: {exc}"
        )

    section("13. FINAL DECISION MATRIX")

    checks = {
        "async context manager":
            hasattr(SFeedWebSocket, "__aenter__")
            and hasattr(SFeedWebSocket, "__aexit__"),

        "async iterator":
            hasattr(SFeedWebSocket, "__aiter__")
            and hasattr(SFeedWebSocket, "__anext__"),

        "subscribe_scrips":
            hasattr(SFeedWebSocket, "subscribe_scrips"),

        "WsToken available":
            WsToken is not None,
    }

    for name, passed in checks.items():

        status = "[PASS]" if passed else "[FAIL]"

        print(f"{status} {name}")

    section("14. EXPECTED NEXT REPAIR")

    print(
        "If the contract above confirms the expected lifecycle, "
        "the next production repair will implement:"
    )

    print()
    print("    authenticated NeoAPI")
    print("            ↓")
    print("    create_websocket()")
    print("            ↓")
    print("    retain SFeedWebSocket instance")
    print("            ↓")
    print("    async connection task")
    print("            ↓")
    print("    subscribe_scrips([WsToken(...)])")
    print("            ↓")
    print("    async message consumer")
    print("            ↓")
    print("    SDK message → project tick dict")
    print("            ↓")
    print("    existing on_tick() callbacks")

    print()
    print(
        "[INFO] This probe does NOT perform the repair."
    )

    section("END OF SFEED FINAL CONTRACT PROBE")

    print(
        "[SAFETY] No authentication attempted."
    )
    print(
        "[SAFETY] No WebSocket opened."
    )
    print(
        "[SAFETY] No subscription performed."
    )
    print(
        "[SAFETY] No repository files modified."
    )
    print(
        "[SAFETY] No order operation performed."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())