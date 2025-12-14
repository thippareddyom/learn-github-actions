# yahoo_data_loader.py
import json
import re
import math
from datetime import date
from pathlib import Path
from typing import Dict, Optional, Tuple

import warnings
import pandas as pd
import pandas_ta as ta
from yahooquery import Ticker

# Suppress pandas_ta MACD warning about unorderable values
warnings.filterwarnings("ignore", message="The values in the array are unorderable", category=RuntimeWarning)

# Always write under the service-level data directory
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
STOCKS_DIR = DATA_DIR / "stocks"
ETF_DIR = DATA_DIR / "etf"


def _asset_dir(assetclass: str) -> Path:
    ac = (assetclass or "stocks").lower()
    if ac == "stocks":
        return STOCKS_DIR
    if ac == "etf":
        return ETF_DIR
    return DATA_DIR

def download_with_indicators(symbol: str, period="12mo", interval="1d", assetclass="stocks"):
    ticker = Ticker(symbol)
    df = ticker.history(period=period, interval=interval)
    if df.empty:
        raise ValueError(f"No data for {symbol}")

    # Flatten and normalize column names
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = ["_".join([str(x) for x in tup if x]).strip("_") for tup in df.columns]
    df.columns = [str(c).lower() for c in df.columns]

    # Map columns that might include ticker prefixes/suffixes
    col_map = {}
    def _find_column(targets):
        for target in targets:
            if target in df.columns:
                return target
        return next((c for c in df.columns if any(target in c for target in targets)), None)

    col_map["open"] = _find_column(["open"])
    col_map["high"] = _find_column(["high"])
    col_map["low"] = _find_column(["low"])
    col_map["close"] = _find_column(["adjclose", "close"])
    col_map["volume"] = _find_column(["volume"])

    for key, val in col_map.items():
        if val is None:
            raise ValueError(f"Missing required column '{key}' in downloaded data for {symbol}")

    df["open"] = df[col_map["open"]]
    df["high"] = df[col_map["high"]]
    df["low"] = df[col_map["low"]]
    df["close"] = df[col_map["close"]]
    df["volume"] = df[col_map["volume"]]

    # Indicators
    df.ta.sma(length=20, append=True)
    df.ta.sma(length=50, append=True)
    df.ta.sma(length=200, append=True)
    df.ta.rsi(length=14, append=True)
    df.ta.macd(append=True, sort=False)
    df.ta.bbands(append=True)
    df.ta.atr(append=True)

    # Fundamentals & sentiment snapshot from Yahoo
    try:
        fundamentals, raw_modules, raw_vm_rows = _extract_fundamentals(
            ticker=ticker,
            last_close=float(df["close"].iloc[-1]),
            latest_volume=float(df["volume"].iloc[-1]),
            avg_volume_30=float(df["volume"].tail(30).mean()),
            last_sma50=_to_num(df["SMA_50"].iloc[-1]),
            last_rsi=_to_num(df["RSI_14"].iloc[-1]),
        )
    except Exception:
        # Best-effort download; continue even if valuation modules fail
        fundamentals, raw_modules, raw_vm_rows = {}, {}, []
    # summary_valuations already merged inside _extract_fundamentals

    # Normalize columns we care about
    rows = []
    for idx, row in df.iterrows():
        idx_val = idx[1] if isinstance(idx, tuple) and len(idx) > 1 else idx
        rows.append({
            "date": pd.to_datetime(idx_val).strftime("%Y-%m-%d"),
            "open": _to_num(row["open"]),
            "high": _to_num(row["high"]),
            "low": _to_num(row["low"]),
            "close": _to_num(row["close"]),
            "volume": _to_num(row["volume"]),
            "sma20": _to_num(row.get("SMA_20")),
            "sma50": _to_num(row.get("SMA_50")),
            "sma200": _to_num(row.get("SMA_200")),
            "rsi14": _to_num(row.get("RSI_14")),
            "macd": _to_num(row.get("MACD_12_26_9")),
            "macd_signal": _to_num(row.get("MACDs_12_26_9")),
            "macd_hist": _to_num(row.get("MACDh_12_26_9")),
            "bb_upper": _to_num(row.get("BBU_20_2.0")),
            "bb_lower": _to_num(row.get("BBL_20_2.0")),
            "atr14": _to_num(row.get("ATRr_14")),
        })

    target_dir = _asset_dir(assetclass)
    out_path = target_dir / f"{symbol.upper()}_{assetclass.lower()}_data.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "symbol": symbol.upper(),
        "assetclass": assetclass,
        "rows": rows,
        "fundamentals": fundamentals,
        "modules": raw_modules,
        "valuation_measures": raw_vm_rows,
    }
    safe_payload = _sanitize_for_json(payload)
    out_path.write_text(json.dumps(safe_payload, indent=2, allow_nan=False))
    return out_path

def _to_num(val):
    try:
        f = float(val)
        return f if math.isfinite(f) else None
    except Exception:
        return None


def _sanitize_for_json(obj):
    """Recursively replace non-finite numbers with None so json.dumps(allow_nan=False) succeeds."""
    try:
        import numpy as np  # optional
    except Exception:  # noqa: BLE001
        np = None

    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_for_json(v) for v in obj]
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if np is not None and isinstance(obj, (np.floating, np.integer)):
        val = float(obj)
        return val if math.isfinite(val) else None
    return obj


def _extract_valuation_measures(ticker: Ticker) -> Tuple[Dict[str, float], list]:
    """Extract valuation measures like EV/EBITDA and Price/Book from Yahoo."""
    try:
        vm = ticker.valuation_measures
    except Exception:
        return {}, []
    try:
        df = vm if isinstance(vm, pd.DataFrame) else pd.DataFrame(vm)
    except Exception:
        return {}, []
    if getattr(df, "empty", True):
        return {}, []
    try:
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = ["_".join([str(x) for x in tup if x]).strip("_") for tup in df.columns]
        df.columns = [str(c).lower() for c in df.columns]
        df = df.reset_index(drop=True).dropna(how="all")
        if df.empty:
            return {}, []
        # Normalize timestamps to ISO strings for JSON safety
        def _clean_row(row):
            out_row = {}
            for k, v in row.items():
                if isinstance(v, pd.Timestamp):
                    out_row[k] = v.isoformat()
                else:
                    out_row[k] = v
            return out_row

        last = _clean_row(df.iloc[-1].to_dict())
        raw_rows = [_clean_row(r) for r in df.to_dict(orient="records")]
    except Exception:
        return {}, []

    def _clean_key(raw: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", raw.lower()).strip("_")

    rename = {
        "trailing_p_e": "trailing_pe",
        "forward_p_e": "forward_pe_vm",
        "peg_ratio_5_yr_expected": "peg_ratio",
        "price_book_mrq": "price_to_book",
        "price_sales_ttm": "price_to_sales",
        "enterprise_value_ebitda": "ev_to_ebitda",
        "enterprise_value_revenue": "ev_to_revenue",
    }

    out: Dict[str, float] = {}
    for raw_key, raw_val in last.items():
        key = rename.get(_clean_key(str(raw_key)), _clean_key(str(raw_key)))
        num = _to_num(raw_val)
        if num is None:
            continue
        if key not in out:
            out[key] = num

    if "pe_forward" not in out and "forward_pe_vm" in out:
        out["pe_forward"] = out["forward_pe_vm"]

    return out, raw_rows


def _extract_fundamentals(
    ticker: Ticker,
    last_close: float,
    latest_volume: float,
    avg_volume_30: float,
    last_sma50: Optional[float],
    last_rsi: Optional[float],
) -> Tuple[Dict[str, Optional[float]], Dict[str, object]]:
    symbol = ticker.symbol.upper() if hasattr(ticker, "symbol") else ""
    symbol_key = symbol.upper()
    try:
        modules = ticker.get_modules([
            "summaryDetail",
            "financialData",
            "price",
            "defaultKeyStatistics",
            "assetProfile",
            "earningsTrend",
            "recommendationTrend",
        ])
    except Exception:
        modules = {}
    # Second attempt with the core set only (matches scripts/yahoo.py) if initial call is empty
    if not modules:
        try:
            modules = ticker.get_modules(
                ["financialData", "recommendationTrend", "defaultKeyStatistics", "summaryDetail", "price"]
            )
        except Exception:
            modules = {}
    # Normalize modules to the per-symbol dict (yahooquery returns {SYM: {...}})
    if isinstance(modules, dict):
        if symbol_key in modules:
            modules = modules.get(symbol_key) or {}
        elif symbol_key.lower() in modules:
            modules = modules.get(symbol_key.lower()) or {}
        elif len(modules) == 1:
            modules = next(iter(modules.values()))

    def _coerce_dict(data):
        if isinstance(data, dict):
            if symbol_key in data:
                return data.get(symbol_key)
            if symbol_key.lower() in data:
                return data.get(symbol_key.lower())
            if len(data) == 1:
                return next(iter(data.values()))
            return data
        return None

    def _get(mod: str, key: str):
        try:
            data = _coerce_dict(modules.get(mod) or {})
            if isinstance(data, dict):
                return data.get(key)
        except Exception:
            return None
        return None

    forward_pe = (
        _get("financialData", "forwardPE")
        or _get("defaultKeyStatistics", "forwardPE")
        or _get("summaryDetail", "forwardPE")
    )
    eps_growth = (
        _get("financialData", "earningsGrowth")
        or _get("earningsTrend", "earningsGrowth")
        or _get("earningsTrend", "growth")
    )
    roe = _get("financialData", "returnOnEquity") or _get("defaultKeyStatistics", "returnOnEquity")
    sector = _get("assetProfile", "sector") or _get("price", "sector")
    market_cap = _get("price", "marketCap") or _get("summaryDetail", "marketCap")
    target_mean = _get("financialData", "targetMeanPrice") or _get("summaryDetail", "targetMeanPrice")
    current_price = _get("financialData", "currentPrice") or last_close 
    # Recommendation trend
    buy_rating_pct = None
    try:
        rec_trend = modules.get("recommendationTrend") or {}
        if isinstance(rec_trend, dict):
            rec_trend = rec_trend.get(symbol.lower()) or rec_trend.get(symbol.upper()) or rec_trend
        trend_rows = rec_trend.get("trend") if isinstance(rec_trend, dict) else None
        if isinstance(trend_rows, list) and trend_rows:
            latest = trend_rows[0]
            buys = float(latest.get("buy", 0)) + float(latest.get("strongBuy", 0))
            total = buys + float(latest.get("hold", 0)) + float(latest.get("sell", 0)) + float(latest.get("strongSell", 0))
            if total > 0:
                buy_rating_pct = (buys / total) * 100
    except Exception:
        buy_rating_pct = None

    target_upside_pct = None
    try:
        if target_mean and current_price:
            target_upside_pct = ((float(target_mean) - float(current_price)) / float(current_price)) * 100
    except Exception:
        target_upside_pct = None

    volume_trend = None
    try:
        if avg_volume_30 and latest_volume:
            volume_trend = latest_volume / avg_volume_30
    except Exception:
        volume_trend = None

    def _fallback_num(val, default=0.0):
        num = _to_num(val)
        return num if num is not None else default

    fundamentals = {
        "sector": sector or "Unknown",
        "market_cap": market_cap if market_cap is not None else 0,
        "pe_forward": _fallback_num(forward_pe),
        "eps_growth_yoy": _fallback_num(eps_growth),
        "roe": _fallback_num(roe),
        "sma50": _fallback_num(last_sma50),
        "rsi14": _fallback_num(last_rsi),
        "volume_trend": _fallback_num(volume_trend, 1.0 if volume_trend is None else volume_trend),
        "buy_rating_pct": _fallback_num(buy_rating_pct),
        # Do NOT fall back target_mean_price to last_close; leave None if missing so we can detect "no target".
        "target_mean_price": _fallback_num(target_mean, None),
        "target_upside_pct": _fallback_num(target_upside_pct, None),
        "current_price": _fallback_num(current_price, last_close),
    }
    valuations, valuation_rows = _extract_valuation_measures(ticker)
    if valuations:
        fundamentals.update(valuations)
        # If primary market_cap missing/zero, fall back to valuation_measures.marketcap when present
        if (
            (fundamentals.get("market_cap") in (None, 0))
            and isinstance(valuations.get("marketcap"), (int, float))
        ):
            fundamentals["market_cap"] = valuations["marketcap"]
    return fundamentals, modules, valuation_rows
