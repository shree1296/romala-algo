"""Romala Algo â€” FastAPI backend with Kotak Neo integration.

Run with: uvicorn main:app --reload --port 8000
"""


from __future__ import annotations

import os
import sys
import time
import logging
import asyncio
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Ensure backend package dirs are importable
sys.path.insert(0, str(Path(__file__).parent))

from kotak_neo.client import KotakNeoClient
from indicators.engine import OHLCBar, compute_all_indicators
from strategies.engine import STRATEGY_DEFINITIONS, run_strategy

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("romala")

app = FastAPI(title="Romala Algo API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

neo = KotakNeoClient()
START_TIME = time.time()

@app.on_event("startup")
async def _capture_application_event_loop() -> None:
    """
    Capture the FastAPI/Uvicorn event loop.

    Kotak Neo SDK callbacks may arrive from a background thread.
    That thread must NOT attempt to create or retrieve its own
    asyncio event loop.
    """
    app.state.event_loop = asyncio.get_running_loop()
    logger.info("FastAPI event loop captured for broker callbacks.")


# â”€â”€â”€ Connected WebSocket clients (for live tick broadcast) â”€â”€â”€
_active_ws_clients: list[WebSocket] = []


def _broadcast_tick(tick: dict) -> None:
    """
    Forward a Kotak Neo tick to every connected frontend WebSocket client.

    The Kotak Neo SDK may invoke this callback from a background thread.
    Therefore we must always schedule WebSocket sends on the FastAPI
    application's running event loop.
    """

    loop = getattr(app.state, "event_loop", None)

    if loop is None or loop.is_closed():
        logger.warning(
            "Cannot broadcast tick: application event loop unavailable."
        )
        return

    clients = list(_active_ws_clients)

    for ws in clients:

        if ws.client_state.name != "CONNECTED":

            try:
                _active_ws_clients.remove(ws)
            except ValueError:
                pass

            continue

        try:

            future = asyncio.run_coroutine_threadsafe(
                ws.send_json({
                    "type": "tick",
                    "data": tick,
                }),
                loop,
            )

            def _handle_send_result(
                future_result,
                websocket=ws,
            ):

                try:
                    future_result.result()

                except Exception as exc:

                    logger.warning(
                        "WebSocket tick send failed: %s",
                        exc,
                    )

                    def _remove_client():

                        try:
                            _active_ws_clients.remove(websocket)
                        except ValueError:
                            pass

                    if not loop.is_closed():
                        loop.call_soon_threadsafe(
                            _remove_client
                        )

            future.add_done_callback(
                _handle_send_result
            )

        except Exception as exc:

            logger.warning(
                "Failed to schedule tick broadcast: %s",
                exc,
            )
# Register our broadcast as the tick callback so the Neo SDK pushes
# every live tick through to all connected frontend WebSocket clients.
neo.on_tick(_broadcast_tick)

# â”€â”€â”€ Real NSE instrument tokens for watchlist/quotes â”€â”€â”€
NSE_SYMBOLS = [
    {"symbol": "NIFTY", "exchange": "nse_cm", "token": "256265", "isIndex": True},
    {"symbol": "BANKNIFTY", "exchange": "nse_cm", "token": "260105", "isIndex": True},
    {"symbol": "FINNIFTY", "exchange": "nse_cm", "token": "257061", "isIndex": True},
    {"symbol": "RELIANCE", "exchange": "nse_cm", "token": "2885", "isIndex": False},
    {"symbol": "TCS", "exchange": "nse_cm", "token": "2953", "isIndex": False},
    {"symbol": "INFY", "exchange": "nse_cm", "token": "1594", "isIndex": False},
    {"symbol": "HDFCBANK", "exchange": "nse_cm", "token": "1333", "isIndex": False},
    {"symbol": "ICICIBANK", "exchange": "nse_cm", "token": "4963", "isIndex": False},
    {"symbol": "SBIN", "exchange": "nse_cm", "token": "3045", "isIndex": False},
    {"symbol": "TATAMOTORS", "exchange": "nse_cm", "token": "3456", "isIndex": False},
    {"symbol": "WIPRO", "exchange": "nse_cm", "token": "3787", "isIndex": False},
    {"symbol": "AXISBANK", "exchange": "nse_cm", "token": "5900", "isIndex": False},
    {"symbol": "ITC", "exchange": "nse_cm", "token": "1660", "isIndex": False},
    {"symbol": "LT", "exchange": "nse_cm", "token": "11483", "isIndex": False},
    {"symbol": "BHARTIARTL", "exchange": "nse_cm", "token": "10604", "isIndex": False},
    {"symbol": "HINDUNILVR", "exchange": "nse_cm", "token": "1394", "isIndex": False},
    {"symbol": "KOTAKBANK", "exchange": "nse_cm", "token": "1922", "isIndex": False},
    {"symbol": "BAJFINANCE", "exchange": "nse_cm", "token": "317", "isIndex": False},
    {"symbol": "MARUTI", "exchange": "nse_cm", "token": "10999", "isIndex": False},
    {"symbol": "ASIANPAINT", "exchange": "nse_cm", "token": "236", "isIndex": False},
]


# â”€â”€â”€ Helper: parse Kotak Neo quote response to our Quote schema â”€â”€â”€

def _parse_quote(raw: dict, symbol: str = "") -> dict[str, Any]:
    """Normalize Kotak Neo quote response to our frontend schema."""
    # Kotak Neo quotes can have various formats depending on quote_type
    ltp = float(raw.get("ltp", raw.get("last_traded_price", 0)) or 0)
    prev_close = float(raw.get("circuit_lower_limit", raw.get("prev_close", raw.get("close", ltp))) or ltp)
    change = ltp - prev_close
    change_pct = (change / prev_close * 100) if prev_close else 0.0
    return {
        "symbol": symbol or raw.get("trading_symbol", raw.get("symbol", "")),
        "exchange": raw.get("exchange_segment", raw.get("exchange", "nse_cm")),
        "ltp": round(ltp, 2),
        "open": float(raw.get("open", ltp) or ltp),
        "high": float(raw.get("high", ltp) or ltp),
        "low": float(raw.get("low", ltp) or ltp),
        "close": prev_close,
        "prev_close": prev_close,
        "volume": int(raw.get("volume", raw.get("trade_volume", 0)) or 0),
        "oi": int(raw.get("oi", raw.get("open_interest", 0)) or 0),
        "oi_day_high": int(raw.get("oi_day_high", 0) or 0),
        "oi_day_low": int(raw.get("oi_day_low", 0) or 0),
        "bid_price": float(raw.get("bid_price", ltp) or ltp),
        "bid_qty": int(raw.get("bid_qty", 0) or 0),
        "ask_price": float(raw.get("ask_price", ltp) or ltp),
        "ask_qty": int(raw.get("ask_qty", 0) or 0),
        "high_52w": float(raw.get("high_52w", ltp) or ltp),
        "low_52w": float(raw.get("low_52w", ltp) or ltp),
        "upper_circuit": float(raw.get("upper_circuit", ltp * 1.1) or ltp * 1.1),
        "lower_circuit": float(raw.get("lower_circuit", ltp * 0.9) or ltp * 0.9),
        "timestamp": int(time.time() * 1000),
        "change": round(change, 2),
        "change_pct": round(change_pct, 2),
    }


# â”€â”€â”€ Helper: build OHLC bars from Kotak Neo historical / quotes â”€â”€â”€

def _bars_from_quotes(symbol: str, count: int = 200) -> list[OHLCBar]:
    """Fetch historical candles. Kotak Neo SDK doesn't have a direct
    historical API, so we build bars from the quotes endpoint's OHLC data
    repeated with small variations based on real LTP.

    For production, you'd use the Neo REST API historical endpoint:
    {BASE_URL}/ohlc/1.0/historical/{token}
    """
    # Get the real current quote for this symbol
    sym_def = next((s for s in NSE_SYMBOLS if s["symbol"] == symbol), None)
    if not sym_def:
        return []

    try:
        raw_quotes = neo.quotes(
            [{"instrument_token": sym_def["token"], "exchange_segment": sym_def["exchange"]}],
            quote_type="ohlc",
        )
        if raw_quotes:
            q = raw_quotes[0] if isinstance(raw_quotes, list) else raw_quotes
            real_ltp = float(q.get("ltp", q.get("last_traded_price", 0)) or 0)
            real_open = float(q.get("open", real_ltp) or real_ltp)
            real_high = float(q.get("high", real_ltp) or real_ltp)
            real_low = float(q.get("low", real_ltp) or real_ltp)
            real_close = float(q.get("close", real_ltp) or real_ltp)
            real_vol = int(q.get("volume", 0) or 0)

            # Build intraday bars from real OHLC by interpolating
            bars: list[OHLCBar] = []
            now = time.time() * 1000
            interval_ms = 60000  # 1-minute bars
            for i in range(count):
                progress = (i + 1) / count
                o = real_open + (real_close - real_open) * (i / count) + (real_high - real_low) * 0.01 * ((-1) ** i)
                c = real_open + (real_close - real_open) * ((i + 1) / count)
                h = max(o, c) + (real_high - real_low) * 0.005
                l = min(o, c) - (real_high - real_low) * 0.005
                v = int(real_vol / count * (0.5 + abs(((i * 7) % 100) / 100)))
                ts = now - (count - i) * interval_ms
                bars.append(OHLCBar(
                    timestamp=ts,
                    date=time.strftime("%Y-%m-%d %H:%M", time.localtime(ts / 1000)),
                    open=round(o, 2),
                    high=round(h, 2),
                    low=round(l, 2),
                    close=round(c, 2),
                    volume=v,
                ))
            return bars
    except Exception as e:
        logger.error(f"Failed to build bars for {symbol}: {e}")

    return []


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# ROUTES
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "broker": "Kotak Neo",
        "uptime": int(time.time() - START_TIME),
        "connected": neo.connected,
    }


# â”€â”€â”€ Broker â”€â”€â”€

class LoginRequest(BaseModel):
    consumer_key: str = ""
    mobile_number: str = ""
    ucc: str = ""
    password: str = ""
    mpin: str = ""
    totp: str = ""


@app.get("/api/broker/status")
async def broker_status():

    raw_status = neo._status()

    if not isinstance(raw_status, dict):
        raw_status = {
            "message": str(raw_status)
        }

    connected = bool(neo.connected)

    raw_status["connected"] = connected

    raw_status["status"] = (
        "connected"
        if connected
        else "disconnected"
    )

    raw_status.setdefault(
        "message",
        (
            "Connected"
            if connected
            else "Not connected â€” please login"
        ),
    )

    return raw_status


@app.post("/api/broker/login")
async def broker_login(req: LoginRequest):

    creds = {
        "consumer_key": (
            req.consumer_key
            or os.getenv("KOTAK_CONSUMER_KEY", "")
            or os.getenv("NEO_CONSUMER_KEY", "")
        ),

        "mobile_number": (
            req.mobile_number
            or os.getenv("KOTAK_MOBILE_NUMBER", "")
        ),

        "ucc": (
            req.ucc
            or os.getenv("KOTAK_UCC", "")
        ),

        "password": req.password,

        "mpin": (
            req.mpin
            or os.getenv("KOTAK_MPIN", "")
        ),

        "totp": (
            req.totp
            or os.getenv("KOTAK_TOTP", "")
        ),
    }

    try:

        return neo.login(creds)

    except Exception as exc:

        logger.exception(
            "Kotak Neo login failed"
        )

        raise HTTPException(
            status_code=401,
            detail=str(exc),
        )
@app.post("/api/broker/logout")
async def broker_logout():
    return neo.logout()


# â”€â”€â”€ Market Data â”€â”€â”€

class QuoteRequest(BaseModel):
    instrument_tokens: list[dict] = []


@app.post("/api/quotes")
async def get_quotes(req: QuoteRequest):

    if not neo.connected:
        raise HTTPException(
            status_code=403,
            detail="Broker not connected. Please login first.",
        )

    try:

        raw = neo.quotes(
            req.instrument_tokens
        )

    except Exception as exc:

        logger.exception(
            "Quote request failed"
        )

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        )

    results = []

    for i, tok in enumerate(
        req.instrument_tokens
    ):

        r = (
            raw[i]
            if i < len(raw)
            else {}
        )

        sym = next(
            (
                s["symbol"]
                for s in NSE_SYMBOLS
                if s["token"]
                == tok.get(
                    "instrument_token"
                )
            ),
            tok.get(
                "instrument_token",
                "",
            ),
        )

        results.append(
            _parse_quote(
                r,
                sym,
            )
        )

    return results
@app.get("/api/quote")
async def get_quote(symbol: str, exchange: str = "nse_cm"):
    if not neo.connected:
        raise HTTPException(status_code=403, detail="Broker not connected. Please login first.")
    sym_def = next((s for s in NSE_SYMBOLS if s["symbol"] == symbol), None)
    token = sym_def["token"] if sym_def else symbol
    raw = neo.quotes([{"instrument_token": token, "exchange_segment": exchange}])
    return _parse_quote(raw[0] if raw else {}, symbol)


@app.get("/api/market-status")
async def market_status():
    from datetime import datetime, timezone, timedelta
    ist = timezone(timedelta(hours=5, minutes=30))
    now = datetime.now(ist)
    hour, minute = now.hour, now.minute
    day = now.weekday()  # Monday=0 .. Sunday=6
    is_weekday = 0 <= day <= 4
    total_min = hour * 60 + minute
    is_open = is_weekday and 555 <= total_min <= 930
    phase = "closed"
    if is_weekday:
        if total_min < 555:
            phase = "pre_open"
        elif total_min < 570:
            phase = "pre_open"
        elif total_min <= 930:
            phase = "open"
    return {
        "market_open": is_open,
        "status": "OPEN" if is_open else "CLOSED",
        "phase": phase,
        "exchange": "NSE",
        "timestamp": int(time.time() * 1000),
        "next_open": "09:15",
        "next_close": "15:30",
        "ist_time": now.strftime("%H:%M:%S"),
    }


@app.get("/api/search-scrip")
async def search_scrip(segment: str = "nse_cm", symbol: str = ""):
    if not neo.connected:
        raise HTTPException(status_code=403, detail="Broker not connected.")
    return neo.search_scrip(segment=segment, symbol=symbol)


@app.get("/api/scrip-master")
async def scrip_master(segment: str = ""):
    if not neo.connected:
        raise HTTPException(status_code=403, detail="Broker not connected.")
    return neo.scrip_master(exchange_segment=segment)


@app.get("/api/historical")
async def get_historical(symbol: str, exchange: str = "nse_cm", interval: str = "1m", count: int = 200):
    if not neo.connected:
        raise HTTPException(status_code=403, detail="Broker not connected. Please login first.")
    bars = _bars_from_quotes(symbol, count)
    return {
        "symbol": symbol,
        "exchange": exchange,
        "interval": interval,
        "data_source": "synthetic_fallback",
        "warning": (
            "These candles are generated from current quote OHLC data "
            "and are NOT genuine historical market candles."
        ),
        "bars": [
            {
                "timestamp": b.timestamp,
                "date": b.date,
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
                "volume": b.volume,
            }
            for b in bars
        ],
    }


# â”€â”€â”€ Indicators â”€â”€â”€

@app.get("/api/indicators")
async def get_indicators(symbol: str, exchange: str = "nse_cm", timeframe: str = "1m", bars: int = 100):
    if not neo.connected:
        raise HTTPException(status_code=403, detail="Broker not connected. Please login first.")
    ohlc_bars = _bars_from_quotes(symbol, max(bars + 50, 200))
    if not ohlc_bars:
        raise HTTPException(status_code=404, detail=f"No data for symbol {symbol}")

    result = compute_all_indicators(ohlc_bars)
    indicator_list = [
        {"name": k, "value": v, "group": _group_for(k), "description": _desc_for(k)}
        for k, v in result.items()
    ]
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "bars": len(ohlc_bars),
        "data_source": "synthetic_fallback",
        "warning": (
            "Indicators are currently calculated from generated "
            "fallback candles, not genuine historical candles."
        ),
        "indicators": indicator_list,
        "computed_at": int(time.time() * 1000),
    }


def _group_for(name: str) -> str:
    technicals = {"ema_", "sma_", "vwap", "wma_", "hma_", "dema_", "tema_"}
    if any(name.startswith(p) for p in technicals):
        return "technicals"
    if name.startswith("bb_"):
        return "volatility"
    if name.startswith("macd"):
        return "momentum"
    if name.startswith("rsi") or name in ("stoch_rsi", "stoch_k", "stoch_d", "roc", "momentum", "williams_r", "cci", "ultimate_osc", "tsi", "price_accel"):
        return "momentum"
    if name.startswith("atr"):
        return "volatility"
    if name.startswith("adx") or name in ("plus_di", "minus_di", "di_diff"):
        return "trend"
    if name.startswith("volume") or name in ("obv", "cmf", "mfi", "vpt", "adl"):
        return "volume"
    if name.startswith("ichimoku") or name in ("psar", "supertrend", "kama_10", "vortex_pos", "vortex_neg", "aroon_up", "aroon_down", "aroon_osc"):
        return "trend"
    if name.startswith("oi_") or name in ("long_buildup", "short_buildup", "long_unwinding", "short_covering", "pcr"):
        return "oi"
    if name in ("max_pain", "support", "resistance", "pivot_point", "fib_382", "fib_618"):
        return "market_structure"
    return "technicals"


def _desc_for(name: str) -> str:
    descs = {
        "ema_9": "9-period EMA", "ema_21": "21-period EMA", "ema_50": "50-period EMA",
        "ema_100": "100-period EMA", "ema_200": "200-period EMA",
        "sma_10": "10-period SMA", "sma_20": "20-period SMA", "sma_50": "50-period SMA", "sma_200": "200-period SMA",
        "vwap": "Volume Weighted Average Price", "vwap_dev": "VWAP deviation %",
        "bb_upper": "Upper Bollinger Band", "bb_middle": "Middle Bollinger Band", "bb_lower": "Lower Bollinger Band",
        "bb_width": "Bollinger Band width", "bb_pct": "Bollinger %B",
        "macd_line": "MACD line", "macd_signal": "MACD signal", "macd_hist": "MACD histogram",
        "rsi_7": "7-period RSI", "rsi_14": "14-period RSI", "rsi_21": "21-period RSI",
        "atr_14": "14-period ATR", "atr_pct": "ATR % of price",
        "adx_14": "Average Directional Index", "plus_di": "+DI", "minus_di": "-DI",
        "supertrend": "Supertrend", "psar": "Parabolic SAR",
        "pcr": "Put-Call Ratio", "oi_change_pct": "OI change %",
    }
    return descs.get(name, name.replace("_", " ").title())


# â”€â”€â”€ Strategies â”€â”€â”€

@app.get("/api/strategies")
async def get_strategies():
    return STRATEGY_DEFINITIONS


@app.get("/api/strategy/run")
async def run_strategy_endpoint(strategy_id: str, symbol: str, exchange: str = "nse_cm", timeframe: str = "1m"):
    if not neo.connected:
        raise HTTPException(status_code=403, detail="Broker not connected. Please login first.")
    bars = _bars_from_quotes(symbol, 200)
    if not bars:
        raise HTTPException(status_code=404, detail=f"No data for symbol {symbol}")
    result = run_strategy(
        strategy_id,
        symbol,
        bars,
    )

    if isinstance(result, dict):

        result["data_source"] = "synthetic_fallback"

        result["warning"] = (
            "This strategy result is currently calculated from "
            "generated fallback candles, not genuine historical candles."
        )

    return result


# â”€â”€â”€ Scanner â”€â”€â”€

class ScanRequest(BaseModel):
    symbols: list[str] = []
    strategies: list[str] = []
    min_confidence: int = 50
    timeframe: str = "5m"


@app.post("/api/scan")
async def scan_market(req: ScanRequest):
    if not neo.connected:
        raise HTTPException(status_code=403, detail="Broker not connected. Please login first.")
    results = []
    for sym in req.symbols:
        bars = _bars_from_quotes(sym, 200)
        if not bars:
            continue
        # Run each selected strategy, pick the one with highest confidence
        best = None
        for strat_id in req.strategies:
            try:
                sr = run_strategy(strat_id, sym, bars)
                if best is None or sr["confidence"] > best["confidence"]:
                    best = sr
            except Exception:
                continue
        if best and best["confidence"] >= req.min_confidence:
            results.append({
                "symbol": sym,
                "exchange": "nse_cm",
                "ltp": bars[-1].close,
                "signal": best["signal"],
                "strategy": best["name"],
                "confidence": best["confidence"],
                "change_pct": ((bars[-1].close - bars[-2].close) / bars[-2].close * 100) if len(bars) > 1 else 0.0,
                "volume": bars[-1].volume,
                "indicators": {},
                "timestamp": int(time.time() * 1000),
            })
    results.sort(
        key=lambda r: r["confidence"],
        reverse=True,
    )

    return {
        "data_source": "synthetic_fallback",
        "warning": (
            "Scanner signals are currently calculated from generated "
            "fallback candles, not genuine historical market candles."
        ),
        "results": results,
    }


# â”€â”€â”€ Orders â”€â”€â”€

class OrderReq(BaseModel):
    exchange_segment: str = "nse_cm"
    product: str = "MIS"
    price: str = "0"
    order_type: str = "MKT"
    quantity: str = "10"
    validity: str = "DAY"
    trading_symbol: str = ""
    transaction_type: str = "B"
    amo: str = "NO"
    disclosed_quantity: str = "0"
    market_protection: str = "0"
    trigger_price: str = "0"
    tag: str | None = None


@app.post("/api/orders")
async def place_order(req: OrderReq):
    if not neo.connected:
        raise HTTPException(status_code=403, detail="Broker not connected. Please login first.")
    try:
        result = neo.place_order(
            exchange_segment=req.exchange_segment,
            product=req.product,
            price=req.price,
            order_type=req.order_type,
            quantity=req.quantity,
            validity=req.validity,
            trading_symbol=req.trading_symbol,
            transaction_type=req.transaction_type,
            amo=req.amo,
            disclosed_quantity=req.disclosed_quantity,
            market_protection=req.market_protection,
            pf="N",
            trigger_price=req.trigger_price,
            tag=req.tag,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class ModifyReq(BaseModel):
    order_id: str
    price: str | None = None
    quantity: str | None = None
    order_type: str | None = None
    validity: str | None = None
    trigger_price: str | None = None
    disclosed_quantity: str | None = None


@app.post("/api/orders/modify")
async def modify_order(req: ModifyReq):
    if not neo.connected:
        raise HTTPException(status_code=403, detail="Broker not connected.")
    kwargs = {k: v for k, v in req.model_dump().items() if v is not None and k != "order_id"}
    try:
        return neo.modify_order(req.order_id, **kwargs)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class CancelReq(BaseModel):
    order_id: str


@app.post("/api/orders/cancel")
async def cancel_order(req: CancelReq):
    if not neo.connected:
        raise HTTPException(status_code=403, detail="Broker not connected.")
    try:
        return neo.cancel_order(req.order_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/orders")
async def get_orders():
    if not neo.connected:
        raise HTTPException(status_code=403, detail="Broker not connected.")
    return neo.order_report()


@app.get("/api/trades")
async def get_trades():
    if not neo.connected:
        raise HTTPException(status_code=403, detail="Broker not connected.")
    return neo.trade_report()


# â”€â”€â”€ Portfolio â”€â”€â”€

@app.get("/api/positions")
async def get_positions():
    if not neo.connected:
        raise HTTPException(status_code=403, detail="Broker not connected.")
    return neo.positions()


@app.get("/api/holdings")
async def get_holdings():
    if not neo.connected:
        raise HTTPException(status_code=403, detail="Broker not connected.")
    return neo.holdings()


@app.get("/api/limits")
async def get_limits(segment: str = "ALL", exchange: str = "ALL", product: str = "ALL"):
    if not neo.connected:
        raise HTTPException(status_code=403, detail="Broker not connected.")
    return neo.limits(segment=segment, exchange=exchange, product=product)


# â”€â”€â”€ WebSocket for live ticks â”€â”€â”€

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    _active_ws_clients.append(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            if msg_type == "subscribe":
                tokens = data.get("symbols", [])
                is_index = any(t.get("isIndex", False) for t in tokens)
                if neo.connected:
                    neo.subscribe(tokens, isIndex=is_index)
                await websocket.send_json({"type": "connection", "data": {"status": "subscribed", "count": len(tokens)}})
            elif msg_type == "unsubscribe":
                tokens = data.get("symbols", [])
                if neo.connected:
                    neo.unsubscribe(tokens)
                await websocket.send_json({"type": "connection", "data": {"status": "unsubscribed", "count": len(tokens)}})
            elif msg_type == "ping":
                await websocket.send_json({"type": "pong", "data": {"ts": int(time.time() * 1000)}})
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if websocket in _active_ws_clients:
            _active_ws_clients.remove(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


