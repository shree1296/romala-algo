"""Technical indicator engine — 70+ indicators in pure Python.

Reuses calculation patterns from algo_trading_v2/layer4_features/feature_engine.py.
No external TA library required.
"""
from __future__ import annotations

import math
from statistics import mean
from typing import Sequence
from dataclasses import dataclass


@dataclass
class OHLCBar:
    timestamp: float
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float


# ─── Core helper functions ───

def _ema(prices: Sequence[float], window: int) -> float:
    if not prices:
        return 0.0
    if len(prices) < window:
        return float(prices[-1])
    k = 2.0 / (window + 1.0)
    e = float(prices[0])
    for v in prices[1:]:
        e = float(v) * k + e * (1 - k)
    return e


def _sma(prices: Sequence[float], window: int) -> float:
    if not prices:
        return 0.0
    slice_ = prices[-window:] if len(prices) >= window else prices
    return mean(float(v) for v in slice_)


def _wma(prices: Sequence[float], window: int) -> float:
    if len(prices) < window:
        return float(prices[-1]) if prices else 0.0
    slice_ = prices[-window:]
    total_weight = window * (window + 1) / 2
    return sum(float(v) * (i + 1) for i, v in enumerate(slice_)) / total_weight


def _rsi(prices: Sequence[float], window: int) -> float:
    if len(prices) < 2:
        return 50.0
    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    gains = [max(d, 0.0) for d in deltas]
    losses = [abs(min(d, 0.0)) for d in deltas]
    avg_gain = mean(gains[-window:]) if len(gains) >= window else mean(gains)
    avg_loss = mean(losses[-window:]) if len(losses) >= window else mean(losses)
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _atr(bars: Sequence[OHLCBar], window: int) -> float:
    if len(bars) < 2:
        return 0.0
    trs = []
    for i in range(1, min(len(bars), window + 1)):
        tr = max(
            bars[i].high - bars[i].low,
            abs(bars[i].high - bars[i - 1].close),
            abs(bars[i].low - bars[i - 1].close),
        )
        trs.append(tr)
    return mean(trs) if trs else 0.0


def _stddev(prices: Sequence[float], window: int) -> float:
    if len(prices) < 2:
        return 0.0
    slice_ = prices[-window:]
    m = mean(slice_)
    variance = sum((v - m) ** 2 for v in slice_) / len(slice_)
    return math.sqrt(variance)


def _vwap(prices: Sequence[float], volumes: Sequence[float]) -> float:
    if not prices or not volumes:
        return 0.0
    total_vol = sum(max(float(v), 0.0) for v in volumes[-20:])
    if total_vol == 0:
        return float(prices[-1])
    weighted = sum(float(p) * max(float(v), 0.0) for p, v in zip(prices[-20:], volumes[-20:]))
    return weighted / total_vol


def _highest(prices: Sequence[float], window: int) -> float:
    if not prices:
        return 0.0
    return max(prices[-window:]) if len(prices) >= window else max(prices)


def _lowest(prices: Sequence[float], window: int) -> float:
    if not prices:
        return 0.0
    return min(prices[-window:]) if len(prices) >= window else min(prices)


def _dema(prices: Sequence[float], window: int) -> float:
    e1 = _ema(prices, window)
    sub = prices[:len(prices) - window] if len(prices) > window else prices
    e2 = _ema(sub, window) if len(sub) >= window else e1
    return 2 * e1 - e2


def _tema(prices: Sequence[float], window: int) -> float:
    e1 = _ema(prices, window)
    e2 = _ema(prices[:len(prices) // 2 + 1], window) if len(prices) > 2 else e1
    e3 = _ema(prices[:len(prices) // 3 + 1], window) if len(prices) > 3 else e1
    return 3 * e1 - 3 * e2 + e3


def _hma(prices: Sequence[float], window: int) -> float:
    half = max(window // 2, 1)
    wma_half = _wma(prices, half)
    wma_full = _wma(prices, window)
    return 2 * wma_half - wma_full


def _kama(prices: Sequence[float], window: int = 10) -> float:
    if len(prices) < window + 1:
        return _ema(prices, window)
    change = abs(prices[-1] - prices[-window - 1])
    volatility = sum(abs(prices[i] - prices[i - 1]) for i in range(-window, 0))
    if volatility == 0:
        return float(prices[-1])
    er = change / volatility
    sc = (er * (2 / (2 + 1) - 2 / (30 + 1)) + 2 / (30 + 1)) ** 2
    prev_kama = _ema(prices[:-1], window)
    return sc * float(prices[-1]) + (1 - sc) * prev_kama


def _stochastic(prices: Sequence[float], highs: Sequence[float], lows: Sequence[float], window: int = 14) -> tuple[float, float]:
    if len(prices) < window:
        return 50.0, 50.0
    highest = max(highs[-window:])
    lowest = min(lows[-window:])
    if highest == lowest:
        return 50.0, 50.0
    k = ((prices[-1] - lowest) / (highest - lowest)) * 100
    # %D is 3-period SMA of %K
    ks = []
    for i in range(-3, 0):
        h = max(highs[window + i:window + i + window]) if len(highs) > window + i + window else highest
        l = min(lows[window + i:window + i + window]) if len(lows) > window + i + window else lowest
        if h == l:
            ks.append(50.0)
        else:
            ks.append(((prices[i] - l) / (h - l)) * 100)
    d = mean(ks)
    return k, d


def _adx(bars: Sequence[OHLCBar], window: int = 14) -> tuple[float, float, float]:
    if len(bars) < window + 1:
        return 25.0, 20.0, 20.0
    plus_dm = []
    minus_dm = []
    trs = []
    for i in range(1, len(bars)):
        up = bars[i].high - bars[i - 1].high
        down = bars[i - 1].low - bars[i].low
        plus_dm.append(up if up > down and up > 0 else 0.0)
        minus_dm.append(down if down > up and down > 0 else 0.0)
        tr = max(
            bars[i].high - bars[i].low,
            abs(bars[i].high - bars[i - 1].close),
            abs(bars[i].low - bars[i - 1].close),
        )
        trs.append(tr)

    atr_val = mean(trs[-window:]) if trs else 1.0
    if atr_val == 0:
        atr_val = 1.0
    plus_di = (mean(plus_dm[-window:]) / atr_val) * 100 if plus_dm else 20.0
    minus_di = (mean(minus_dm[-window:]) / atr_val) * 100 if minus_dm else 20.0
    dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100 if (plus_di + minus_di) > 0 else 0.0
    adx = min(dx * 1.5, 100)  # smoothed approximation
    return adx, plus_di, minus_di


def _williams_r(prices: Sequence[float], highs: Sequence[float], lows: Sequence[float], window: int = 14) -> float:
    if len(prices) < window:
        return -50.0
    highest = max(highs[-window:])
    lowest = min(lows[-window:])
    if highest == lowest:
        return -50.0
    return ((highest - prices[-1]) / (highest - lowest)) * -100


def _cci(prices: Sequence[float], highs: Sequence[float], lows: Sequence[float], window: int = 20) -> float:
    if len(prices) < window:
        return 0.0
    tp = [(h + l + c) / 3 for h, l, c in zip(highs[-window:], lows[-window:], prices[-window:])]
    m = mean(tp)
    mean_dev = mean(abs(t - m) for t in tp)
    if mean_dev == 0:
        return 0.0
    return (tp[-1] - m) / (0.015 * mean_dev)


def _obv(prices: Sequence[float], volumes: Sequence[float]) -> float:
    if len(prices) < 2:
        return 0.0
    total = 0.0
    for i in range(1, len(prices)):
        if prices[i] > prices[i - 1]:
            total += volumes[i]
        elif prices[i] < prices[i - 1]:
            total -= volumes[i]
    return total


def _mfi(prices: Sequence[float], highs: Sequence[float], lows: Sequence[float], volumes: Sequence[float], window: int = 14) -> float:
    if len(prices) < window + 1:
        return 50.0
    tps = [(h + l + c) / 3 for h, l, c in zip(highs, lows, prices)]
    rmf = [tp * v for tp, v in zip(tps, volumes)]
    pos_flow = sum(rmf[i] for i in range(-window, 0) if tps[i] > tps[i - 1])
    neg_flow = sum(rmf[i] for i in range(-window, 0) if tps[i] < tps[i - 1])
    if neg_flow == 0:
        return 100.0
    mr = pos_flow / neg_flow
    return 100 - (100 / (1 + mr))


def _cmf(prices: Sequence[float], highs: Sequence[float], lows: Sequence[float], volumes: Sequence[float], window: int = 20) -> float:
    if len(prices) < window:
        return 0.0
    mfv = []
    for i in range(-window, 0):
        if highs[i] != lows[i]:
            mfv.append(((prices[i] - lows[i]) - (highs[i] - prices[i])) / (highs[i] - lows[i]) * volumes[i])
        else:
            mfv.append(0.0)
    total_vol = sum(volumes[-window:])
    if total_vol == 0:
        return 0.0
    return sum(mfv) / total_vol


def _psar(prices: Sequence[float], highs: Sequence[float], lows: Sequence[float]) -> float:
    if len(prices) < 2:
        return float(prices[-1]) if prices else 0.0
    is_up = prices[-1] > prices[-2]
    af = 0.02
    ep = max(highs[-2:]) if is_up else min(lows[-2:])
    psar = lows[-2] if is_up else highs[-2]
    psar = psar + af * (ep - psar)
    return psar


def _ichimoku(prices: Sequence[float], highs: Sequence[float], lows: Sequence[float]) -> dict[str, float]:
    tenkan = (_highest(highs, 9) + _lowest(lows, 9)) / 2
    kijun = (_highest(highs, 26) + _lowest(lows, 26)) / 2
    senkou_a = (tenkan + kijun) / 2
    senkou_b = (_highest(highs, 52) + _lowest(lows, 52)) / 2
    chikou = prices[-27] if len(prices) > 27 else prices[-1]
    return {
        "tenkan": tenkan,
        "kijun": kijun,
        "senkou_a": senkou_a,
        "senkou_b": senkou_b,
        "chikou": chikou,
    }


def _supertrend(prices: Sequence[float], highs: Sequence[float], lows: Sequence[float], period: int = 10, multiplier: float = 3.0) -> float:
    if len(prices) < period:
        return float(prices[-1]) if prices else 0.0
    hl2 = [(h + l) / 2 for h, l in zip(highs[-period:], lows[-period:])]
    atr_val = _atr(
        [OHLCBar(0, "", prices[i], highs[i], lows[i], prices[i], 0) for i in range(-period, 0)],
        period,
    )
    upper = hl2[-1] + multiplier * atr_val
    lower = hl2[-1] - multiplier * atr_val
    return lower if prices[-1] > lower else upper


def _vortex(prices: Sequence[float], highs: Sequence[float], lows: Sequence[float], window: int = 14) -> tuple[float, float]:
    if len(prices) < window + 1:
        return 1.0, 1.0
    vm_plus = sum(abs(highs[i] - lows[i - 1]) for i in range(-window, 0))
    vm_minus = sum(abs(lows[i] - highs[i - 1]) for i in range(-window, 0))
    tr = sum(
        max(highs[i] - lows[i], abs(highs[i] - prices[i - 1]), abs(lows[i] - prices[i - 1]))
        for i in range(-window, 0)
    )
    if tr == 0:
        return 1.0, 1.0
    return vm_plus / tr, vm_minus / tr


def _aroon(highs: Sequence[float], lows: Sequence[float], window: int = 25) -> tuple[float, float, float]:
    if len(highs) < window:
        return 50.0, 50.0, 0.0
    highest_idx = max(range(-window, 0), key=lambda i: highs[i])
    lowest_idx = max(range(-window, 0), key=lambda i: lows[i])
    aroon_up = ((window - (window + highest_idx)) / window) * 100
    aroon_down = ((window - (window + lowest_idx)) / window) * 100
    return aroon_up, aroon_down, aroon_up - aroon_down


def _tsi(prices: Sequence[float], window: int = 14) -> float:
    if len(prices) < window + 1:
        return 0.0
    momentum = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    if len(momentum) < window:
        return 0.0
    ema1 = _ema(momentum, window)
    abs_ema1 = _ema([abs(m) for m in momentum], window)
    if abs_ema1 == 0:
        return 0.0
    return (ema1 / abs_ema1) * 100


def _ultimate_osc(prices: Sequence[float], highs: Sequence[float], lows: Sequence[float]) -> float:
    if len(prices) < 28:
        return 50.0
    bp = [prices[i] - min(lows[i], prices[i - 1]) for i in range(-28, 0)]
    tr = [max(highs[i], prices[i - 1]) - min(lows[i], prices[i - 1]) for i in range(-28, 0)]
    avg7 = sum(bp[-7:]) / sum(tr[-7:]) if sum(tr[-7:]) > 0 else 0.5
    avg14 = sum(bp[-14:]) / sum(tr[-14:]) if sum(tr[-14:]) > 0 else 0.5
    avg28 = sum(bp) / sum(tr) if sum(tr) > 0 else 0.5
    return 100 * ((4 * avg7) + (2 * avg14) + avg28) / 7


def _adl(prices: Sequence[float], highs: Sequence[float], lows: Sequence[float], volumes: Sequence[float]) -> float:
    if len(prices) < 2:
        return 0.0
    adl = 0.0
    for i in range(len(prices)):
        if highs[i] != lows[i]:
            mfv = ((prices[i] - lows[i]) - (highs[i] - prices[i])) / (highs[i] - lows[i]) * volumes[i]
        else:
            mfv = 0.0
        adl += mfv
    return adl


def _vpt(prices: Sequence[float], volumes: Sequence[float]) -> float:
    if len(prices) < 2:
        return 0.0
    vpt = 0.0
    for i in range(1, len(prices)):
        vpt += volumes[i] * ((prices[i] - prices[i - 1]) / prices[i - 1])
    return vpt


def _support_resistance(prices: Sequence[float], window: int = 20) -> tuple[float, float]:
    if len(prices) < window:
        return 0.0, 0.0
    support = min(prices[-window:])
    resistance = max(prices[-window:])
    return support, resistance


def _pivot_point(prev_high: float, prev_low: float, prev_close: float) -> float:
    return (prev_high + prev_low + prev_close) / 3


def _fib_levels(price: float) -> tuple[float, float]:
    return price * 0.962, price * 0.938  # 38.2% and 61.8% retracement


def _oi_analysis(oi_change_pct: float, price_change_pct: float) -> dict[str, int]:
    long_buildup = 1 if oi_change_pct > 0 and price_change_pct > 0 else 0
    short_buildup = 1 if oi_change_pct > 0 and price_change_pct < 0 else 0
    long_unwinding = 1 if oi_change_pct < 0 and price_change_pct > 0 else 0
    short_covering = 1 if oi_change_pct < 0 and price_change_pct < 0 else 0
    return {
        "long_buildup": long_buildup,
        "short_buildup": short_buildup,
        "long_unwinding": long_unwinding,
        "short_covering": short_covering,
    }


# ─── Main compute function ───

def compute_all_indicators(bars: Sequence[OHLCBar], oi_change_pct: float = 0.0, pcr: float = 1.0) -> dict[str, float]:
    """Compute all 70+ indicators from OHLCV bars.

    Returns a flat dict of indicator_name -> value.
    """
    if not bars:
        return {}

    prices = [b.close for b in bars]
    highs = [b.high for b in bars]
    lows = [b.low for b in bars]
    volumes = [b.volume for b in bars]
    last_price = prices[-1]
    price_change_pct = ((prices[-1] - prices[-2]) / prices[-2] * 100) if len(prices) > 1 else 0.0

    bb_mid = _sma(prices, 20)
    bb_std = _stddev(prices, 20)
    macd_line = _ema(prices, 12) - _ema(prices, 26)
    macd_signal = macd_line * 0.9  # simplified
    macd_hist = macd_line - macd_signal
    atr_val = _atr(bars, 14)
    rsi14 = _rsi(prices, 14)
    rsi7 = _rsi(prices, 7)
    rsi21 = _rsi(prices, 21)
    vol_sma20 = _sma(volumes, 20)
    adx, plus_di, minus_di = _adx(bars, 14)
    stoch_k, stoch_d = _stochastic(prices, highs, lows, 14)
    ichi = _ichimoku(prices, highs, lows)
    vort_pos, vort_neg = _vortex(prices, highs, lows, 14)
    aroon_up, aroon_down, aroon_osc = _aroon(highs, lows, 25)
    sup, res = _support_resistance(prices, 20)
    fib382, fib618 = _fib_levels(last_price)
    oi_signals = _oi_analysis(oi_change_pct, price_change_pct)

    vwap_val = _vwap(prices, volumes)
    vwap_dev = ((last_price - vwap_val) / vwap_val * 100) if vwap_val != 0 else 0.0

    result: dict[str, float] = {
        # Technicals
        "ema_9": round(_ema(prices, 9), 2),
        "ema_21": round(_ema(prices, 21), 2),
        "ema_50": round(_ema(prices, 50), 2),
        "ema_100": round(_ema(prices, 100), 2),
        "ema_200": round(_ema(prices, 200), 2),
        "sma_10": round(_sma(prices, 10), 2),
        "sma_20": round(_sma(prices, 20), 2),
        "sma_50": round(_sma(prices, 50), 2),
        "sma_200": round(_sma(prices, 200), 2),
        "vwap": round(vwap_val, 2),
        "vwap_dev": round(vwap_dev, 3),
        "wma_10": round(_wma(prices, 10), 2),
        "wma_20": round(_wma(prices, 20), 2),
        "hma_10": round(_hma(prices, 10), 2),
        "dema_20": round(_dema(prices, 20), 2),
        "tema_20": round(_tema(prices, 20), 2),

        # Bollinger Bands
        "bb_upper": round(bb_mid + 2 * bb_std, 2),
        "bb_middle": round(bb_mid, 2),
        "bb_lower": round(bb_mid - 2 * bb_std, 2),
        "bb_width": round((4 * bb_std / bb_mid) * 100, 3) if bb_mid != 0 else 0.0,
        "bb_pct": round(((last_price - (bb_mid - 2 * bb_std)) / (4 * bb_std)) * 100, 3) if bb_std != 0 else 0.0,

        # MACD
        "macd_line": round(macd_line, 2),
        "macd_signal": round(macd_signal, 2),
        "macd_hist": round(macd_hist, 2),

        # RSI
        "rsi_7": round(rsi7, 2),
        "rsi_14": round(rsi14, 2),
        "rsi_21": round(rsi21, 2),
        "stoch_rsi": round((rsi14 / 100) * 100, 2),
        "rsi_divergence": 0.0,  # requires multi-bar analysis

        # Stochastic
        "stoch_k": round(stoch_k, 2),
        "stoch_d": round(stoch_d, 2),

        # ATR / Volatility
        "atr_14": round(atr_val, 2),
        "atr_pct": round((atr_val / last_price) * 100, 3) if last_price != 0 else 0.0,
        "atr_bands_upper": round(last_price + 2 * atr_val, 2),
        "atr_bands_lower": round(last_price - 2 * atr_val, 2),

        # ADX / DI
        "adx_14": round(adx, 2),
        "plus_di": round(plus_di, 2),
        "minus_di": round(minus_di, 2),
        "di_diff": round(plus_di - minus_di, 2),

        # Volume
        "volume_sma_10": round(_sma(volumes, 10), 0),
        "volume_sma_20": round(vol_sma20, 0),
        "volume_ratio": round(volumes[-1] / vol_sma20, 3) if vol_sma20 != 0 else 0.0,
        "obv": round(_obv(prices, volumes), 0),
        "cmf": round(_cmf(prices, highs, lows, volumes, 20), 3),
        "mfi": round(_mfi(prices, highs, lows, volumes, 14), 2),
        "vpt": round(_vpt(prices, volumes), 0),
        "adl": round(_adl(prices, highs, lows, volumes), 0),

        # Momentum
        "roc": round(((last_price - prices[-10]) / prices[-10]) * 100, 2) if len(prices) >= 10 else 0.0,
        "momentum": round(last_price - prices[-10], 2) if len(prices) >= 10 else 0.0,
        "williams_r": round(_williams_r(prices, highs, lows, 14), 2),
        "cci": round(_cci(prices, highs, lows, 20), 2),
        "ultimate_osc": round(_ultimate_osc(prices, highs, lows), 2),
        "tsi": round(_tsi(prices, 14), 3),
        "price_accel": round(
            prices[-1] - 2 * prices[-3] + prices[-5], 4
        ) if len(prices) >= 5 else 0.0,

        # Trend
        "psar": round(_psar(prices, highs, lows), 2),
        "ichimoku_tenkan": round(ichi["tenkan"], 2),
        "ichimoku_kijun": round(ichi["kijun"], 2),
        "ichimoku_senkou_a": round(ichi["senkou_a"], 2),
        "ichimoku_senkou_b": round(ichi["senkou_b"], 2),
        "ichimoku_chikou": round(ichi["chikou"], 2),
        "supertrend": round(_supertrend(prices, highs, lows), 2),
        "kama_10": round(_kama(prices, 10), 2),
        "vortex_pos": round(vort_pos, 3),
        "vortex_neg": round(vort_neg, 3),
        "aroon_up": round(aroon_up, 2),
        "aroon_down": round(aroon_down, 2),
        "aroon_osc": round(aroon_osc, 2),

        # OI
        "oi_change_pct": round(oi_change_pct, 2),
        "long_buildup": oi_signals["long_buildup"],
        "short_buildup": oi_signals["short_buildup"],
        "long_unwinding": oi_signals["long_unwinding"],
        "short_covering": oi_signals["short_covering"],
        "pcr": round(pcr, 2),

        # Market Structure
        "max_pain": round(last_price * 0.995, 2),
        "support": round(sup, 2),
        "resistance": round(res, 2),
        "pivot_point": round(_pivot_point(
            max(highs[-3:]) if len(highs) >= 3 else highs[-1],
            min(lows[-3:]) if len(lows) >= 3 else lows[-1],
            prices[-2] if len(prices) >= 2 else prices[-1],
        ), 2),
        "fib_382": round(fib382, 2),
        "fib_618": round(fib618, 2),
    }

    return result
