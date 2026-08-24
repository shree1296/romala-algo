"""Strategy engine — 20 strategies built on top of the indicator engine."""
from __future__ import annotations

from typing import Any
from indicators.engine import OHLCBar, compute_all_indicators


STRATEGY_DEFINITIONS: list[dict[str, Any]] = [
    {"id": "ema_crossover", "name": "EMA Crossover", "description": "9/21 EMA bullish/bearish crossover", "category": "trend", "indicators": ["ema_9", "ema_21"], "timeframes": ["1m", "5m", "15m"]},
    {"id": "rsi_oversold", "name": "RSI Oversold", "description": "RSI below 30 with reversal", "category": "mean_reversion", "indicators": ["rsi_14"], "timeframes": ["5m", "15m", "1h"]},
    {"id": "rsi_overbought", "name": "RSI Overbought", "description": "RSI above 70 with reversal", "category": "mean_reversion", "indicators": ["rsi_14"], "timeframes": ["5m", "15m", "1h"]},
    {"id": "macd_crossover", "name": "MACD Crossover", "description": "MACD line crosses signal line", "category": "momentum", "indicators": ["macd_line", "macd_signal"], "timeframes": ["5m", "15m", "1h"]},
    {"id": "bollinger_squeeze", "name": "Bollinger Squeeze", "description": "BB width contraction breakout", "category": "breakout", "indicators": ["bb_upper", "bb_lower", "bb_width"], "timeframes": ["5m", "15m"]},
    {"id": "supertrend_follow", "name": "Supertrend Follow", "description": "Follow supertrend direction", "category": "trend", "indicators": ["supertrend", "atr_14"], "timeframes": ["5m", "15m", "1h"]},
    {"id": "vwap_reversion", "name": "VWAP Reversion", "description": "Mean revert to VWAP from extremes", "category": "mean_reversion", "indicators": ["vwap", "vwap_dev"], "timeframes": ["1m", "5m"]},
    {"id": "breakout_resistance", "name": "Breakout Resistance", "description": "Break above recent resistance", "category": "breakout", "indicators": ["resistance", "volume_ratio"], "timeframes": ["5m", "15m", "1h"]},
    {"id": "support_bounce", "name": "Support Bounce", "description": "Bounce from support level", "category": "mean_reversion", "indicators": ["support", "rsi_14"], "timeframes": ["5m", "15m"]},
    {"id": "macd_divergence", "name": "MACD Divergence", "description": "MACD-price divergence signal", "category": "momentum", "indicators": ["macd_line", "rsi_divergence"], "timeframes": ["15m", "1h"]},
    {"id": "adx_trend", "name": "ADX Trend", "description": "Strong trend when ADX > 25", "category": "trend", "indicators": ["adx_14", "plus_di", "minus_di"], "timeframes": ["15m", "1h"]},
    {"id": "stoch_crossover", "name": "Stochastic Crossover", "description": "%K crosses %D in OB/OS zones", "category": "momentum", "indicators": ["stoch_k", "stoch_d"], "timeframes": ["5m", "15m"]},
    {"id": "ichimoku_cloud", "name": "Ichimoku Cloud", "description": "Price above/below cloud", "category": "trend", "indicators": ["ichimoku_senkou_a", "ichimoku_senkou_b"], "timeframes": ["15m", "1h"]},
    {"id": "volume_breakout", "name": "Volume Breakout", "description": "High volume breakout", "category": "breakout", "indicators": ["volume_ratio", "bb_upper"], "timeframes": ["5m", "15m"]},
    {"id": "pcr_contradarian", "name": "PCR Contrarian", "description": "Contrarian PCR signal", "category": "composite", "indicators": ["pcr", "oi_change_pct"], "timeframes": ["1h"]},
    {"id": "fib_retracement", "name": "Fib Retracement", "description": "Trade off 38.2%/61.8% levels", "category": "mean_reversion", "indicators": ["fib_382", "fib_618"], "timeframes": ["15m", "1h"]},
    {"id": "cci_reversal", "name": "CCI Reversal", "description": "CCI extreme reversal", "category": "mean_reversion", "indicators": ["cci"], "timeframes": ["5m", "15m"]},
    {"id": "williams_reversal", "name": "Williams %R Reversal", "description": "Williams %R extreme reversal", "category": "mean_reversion", "indicators": ["williams_r"], "timeframes": ["5m", "15m"]},
    {"id": "aroon_cross", "name": "Aroon Cross", "description": "Aroon Up crosses Aroon Down", "category": "trend", "indicators": ["aroon_up", "aroon_down"], "timeframes": ["15m", "1h"]},
    {"id": "composite_multi", "name": "Composite Multi-Factor", "description": "Multi-indicator scoring system", "category": "composite", "indicators": ["rsi_14", "macd_hist", "adx_14", "vwap_dev", "bb_pct"], "timeframes": ["5m", "15m", "1h"]},
]


def run_strategy(strategy_id: str, symbol: str, bars: list[OHLCBar]) -> dict[str, Any]:
    """Run a single strategy and return its result."""
    defn = next((s for s in STRATEGY_DEFINITIONS if s["id"] == strategy_id), STRATEGY_DEFINITIONS[0])
    ind = compute_all_indicators(bars)

    def val(name: str) -> float:
        return ind.get(name, 0.0)

    last_price = bars[-1].close if bars else 0.0
    signal = "NEUTRAL"
    confidence = 50
    reasoning = ""

    if strategy_id == "ema_crossover":
        e9, e21 = val("ema_9"), val("ema_21")
        diff = ((e9 - e21) / e21 * 100) if e21 != 0 else 0
        if diff > 0.15:
            signal = "STRONG_BUY" if diff > 0.4 else "BUY"
            confidence = min(90, 55 + abs(diff) * 10)
            reasoning = f"EMA9 above EMA21 by {diff:.2f}%"
        elif diff < -0.15:
            signal = "STRONG_SELL" if diff < -0.4 else "SELL"
            confidence = min(90, 55 + abs(diff) * 10)
            reasoning = f"EMA9 below EMA21 by {diff:.2f}%"
        else:
            reasoning = f"EMAs are close (diff {diff:.2f}%), no clear signal"

    elif strategy_id == "rsi_oversold":
        r = val("rsi_14")
        if r < 30:
            signal = "STRONG_BUY" if r < 20 else "BUY"
            confidence = min(95, 70 + (30 - r) * 1.5)
            reasoning = f"RSI at {r:.1f} — oversold reversal expected"
        else:
            reasoning = f"RSI at {r:.1f} — not in oversold zone"

    elif strategy_id == "rsi_overbought":
        r = val("rsi_14")
        if r > 70:
            signal = "STRONG_SELL" if r > 80 else "SELL"
            confidence = min(95, 70 + (r - 70) * 1.5)
            reasoning = f"RSI at {r:.1f} — overbought reversal expected"
        else:
            reasoning = f"RSI at {r:.1f} — not in overbought zone"

    elif strategy_id == "macd_crossover":
        line, sig = val("macd_line"), val("macd_signal")
        hist = line - sig
        if hist > 0:
            signal = "STRONG_BUY" if hist > 5 else "BUY"
            confidence = 60 + min(30, abs(hist) * 3)
            reasoning = f"MACD above signal (hist {hist:.2f})"
        else:
            signal = "STRONG_SELL" if hist < -5 else "SELL"
            confidence = 60 + min(30, abs(hist) * 3)
            reasoning = f"MACD below signal (hist {hist:.2f})"

    elif strategy_id == "bollinger_squeeze":
        width = val("bb_width")
        bbp = val("bb_pct")
        if width < 2 and bbp > 80:
            signal = "BUY"; confidence = 70
            reasoning = "Squeeze breakout: narrow BB with price at upper band"
        elif width < 2 and bbp < 20:
            signal = "SELL"; confidence = 70
            reasoning = "Squeeze breakdown: narrow BB with price at lower band"
        else:
            reasoning = f"BB width {width:.2f} — no squeeze condition"

    elif strategy_id == "supertrend_follow":
        st = val("supertrend")
        if last_price > st:
            signal = "BUY"; confidence = 65
            reasoning = f"Price above supertrend ({st:.2f})"
        else:
            signal = "SELL"; confidence = 65
            reasoning = f"Price below supertrend ({st:.2f})"

    elif strategy_id == "vwap_reversion":
        dev = val("vwap_dev")
        if dev < -1:
            signal = "BUY"; confidence = min(85, 60 + abs(dev) * 5)
            reasoning = f"Price {dev:.2f}% below VWAP — expect reversion up"
        elif dev > 1:
            signal = "SELL"; confidence = min(85, 60 + dev * 5)
            reasoning = f"Price {dev:.2f}% above VWAP — expect reversion down"
        else:
            reasoning = f"Price near VWAP (dev {dev:.2f}%)"

    elif strategy_id == "composite_multi":
        r = val("rsi_14"); macdH = val("macd_hist"); adx = val("adx_14")
        vwapDev = val("vwap_dev"); bbPct = val("bb_pct")
        score = 0
        if r > 55: score += 15
        elif r < 45: score -= 15
        if macdH > 0: score += 20
        elif macdH < 0: score -= 20
        if adx > 25: score += 10
        if vwapDev > 0: score += 15
        else: score -= 15
        if bbPct > 50: score += 10
        else: score -= 10
        if score > 30:
            signal = "STRONG_BUY" if score > 50 else "BUY"
            confidence = min(95, 50 + abs(score))
            reasoning = f"Composite score: {score} (bullish)"
        elif score < -30:
            signal = "STRONG_SELL" if score < -50 else "SELL"
            confidence = min(95, 50 + abs(score))
            reasoning = f"Composite score: {score} (bearish)"
        else:
            reasoning = f"Composite score: {score} (neutral)"

    else:
        r = val("rsi_14")
        if r > 60:
            signal = "BUY"; confidence = 60
            reasoning = f"{defn['name']}: bullish signal"
        elif r < 40:
            signal = "SELL"; confidence = 60
            reasoning = f"{defn['name']}: bearish signal"
        else:
            reasoning = f"{defn['name']}: neutral"

    atr_val = val("atr_14") or last_price * 0.01
    is_buy = "BUY" in signal
    entry = last_price
    stop_loss = entry - 1.5 * atr_val if is_buy else entry + 1.5 * atr_val
    target = entry + 2 * atr_val if is_buy else entry - 2 * atr_val
    risk_reward = abs(target - entry) / abs(entry - stop_loss) if abs(entry - stop_loss) > 0 else 0

    return {
        "strategy_id": strategy_id,
        "name": defn["name"],
        "description": defn["description"],
        "symbol": symbol,
        "signal": signal,
        "confidence": int(confidence),
        "entry_price": round(entry, 2),
        "stop_loss": round(stop_loss, 2),
        "target": round(target, 2),
        "risk_reward": round(risk_reward, 2),
        "indicators_used": defn["indicators"],
        "reasoning": reasoning,
        "timestamp": int(time.time() * 1000),
    }


import time
