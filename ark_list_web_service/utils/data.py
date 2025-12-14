from __future__ import annotations

import csv
import json
import math
import os
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

import requests
from yahooquery import Ticker as YqTicker
from flask import abort

from utils.helpers import asset_data_dir, is_fresh, normalize_symbol, parse_date, sanitize
from utils.paths import DATA_DIR, DATA_FILE, ETF_DIR, HOLDINGS_DIR, LEGACY_DATA_FILE, STOCKS_DIR
from utils.yahoo_data_loader import download_with_indicators


def load_funds() -> List[Dict[str, str]]:
    """Load and normalize fund metadata from the bundled JSON file."""
    source_path = DATA_FILE if DATA_FILE.exists() else LEGACY_DATA_FILE
    if not source_path.exists():
        raise FileNotFoundError(f"Missing data file: {DATA_FILE}")

    with source_path.open(encoding="utf-8") as fp:
        data = json.load(fp)

    funds: List[Dict[str, str]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("symbol", "")).upper()
        name = item.get("name") or ""
        url = item.get("url") or ""
        if symbol and name and url:
            funds.append({"symbol": symbol, "name": name, "url": url})
    return funds


def load_holdings(symbol: str, day: Optional[str]) -> Optional[Dict[str, object]]:
    """Load holdings for a fund symbol, downloading legacy sources if needed."""
    _ = day  # date argument no longer used; kept for compatibility

    def _latest_legacy(symbol_upper: str) -> Optional[Path]:
        latest: Optional[tuple[date, Path]] = None
        for root_dir in (HOLDINGS_DIR, DATA_DIR):
            for path in root_dir.glob(f"{symbol_upper}-*.json"):
                if path.name.endswith("_data.json"):
                    continue
                parts = path.stem.split("-", 1)
                if len(parts) != 2:
                    continue
                try:
                    stamp = parse_date(parts[1])
                except ValueError:
                    continue
                if latest is None or stamp > latest[0]:
                    latest = (stamp, path)
        return latest[1] if latest else None

    symbol_upper = symbol.upper()
    path = HOLDINGS_DIR / f"{symbol_upper}-holdings.json"
    found_date: Optional[date] = None

    if not path.exists():
        legacy_path = _latest_legacy(symbol_upper)
        if legacy_path:
            path = legacy_path
            try:
                found_date = parse_date(path.stem.split("-", 1)[1])
            except Exception:
                found_date = None
        else:
            return None

    with path.open(encoding="utf-8") as fp:
        loaded = json.load(fp)

    # Support both legacy list payloads and newer dict payloads with metadata
    meta = loaded if isinstance(loaded, dict) else {}
    rows = meta.get("rows") if isinstance(meta, dict) else loaded
    as_of = meta.get("as_of") or meta.get("downloaded_at") or meta.get("date")
    if as_of and not found_date:
        try:
            found_date = parse_date(str(as_of).split("T")[0])
        except Exception:
            found_date = None

    footnote = ""
    cleaned_rows: List[Dict[str, object]] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        date_text = str(row.get("date", "") or "").lower()
        ticker = row.get("ticker") or row.get("Ticker")
        if not ticker and "investors should carefully consider" in date_text:
            footnote = row.get("date") or ""
            continue
        cleaned_rows.append(row)

    return {
        "symbol": (meta.get("symbol") or symbol or "").upper(),
        "date": found_date.isoformat() if found_date else None,
        "count": len(cleaned_rows),
        "rows": cleaned_rows,
        "footnote": footnote,
    }


def load_or_fetch_ticker_history(symbol: str, assetclass: str = "stocks") -> Dict[str, object]:
    """Return history + latest row for a ticker, downloading if missing/stale.

    If a fresh download fails, we fall back to the latest on-disk copy so callers
    still receive data instead of a hard 500.
    """
    safe_symbol = normalize_symbol(symbol)
    safe_assetclass = (assetclass or "stocks").lower()
    asset_dir = asset_data_dir(safe_assetclass, DATA_DIR)
    legacy_path = DATA_DIR / f"{safe_symbol}_data.json"  # backward compatibility
    json_path = asset_dir / f"{safe_symbol}_{safe_assetclass}_data.json"

    existing_path: Optional[Path] = None
    stale_path: Optional[Path] = None
    for candidate in (json_path, legacy_path):
        if not candidate.exists():
            continue
        if is_fresh(candidate):
            existing_path = candidate
            break
        stale_path = candidate

    if existing_path is None:
        try:
            download_with_indicators(symbol=safe_symbol, assetclass=safe_assetclass)
            existing_path = json_path
        except Exception:
            # Fall back to the most recent stale file if available
            if stale_path and stale_path.exists():
                existing_path = stale_path
            else:
                abort(500, description=f"Failed to refresh data for '{safe_symbol}'")

    if not existing_path or not existing_path.exists():
        abort(404, description=f"Price history for '{safe_symbol}' not found")

    try:
        raw_data = json.loads(existing_path.read_text())
    except Exception:
        raw_data = None
        try:
            download_with_indicators(symbol=safe_symbol, assetclass=safe_assetclass)
            existing_path = json_path
            raw_data = json.loads(existing_path.read_text())
        except Exception:
            # If refresh fails again, reuse the stale data if we have it
            if stale_path and stale_path.exists():
                try:
                    raw_data = json.loads(stale_path.read_text())
                    existing_path = stale_path
                except Exception:
                    raw_data = None
            else:
                raw_data = None
    if raw_data is not None:
        raw_data = sanitize(raw_data)

    def _num(val) -> Optional[float]:
        try:
            fval = float(val)
            return fval if math.isfinite(fval) else None
        except Exception:
            return None

    fundamentals = raw_data.get("fundamentals") if isinstance(raw_data, dict) else None
    modules = raw_data.get("modules") if isinstance(raw_data, dict) else None
    points: List[Dict[str, object]] = []
    latest: Optional[Dict[str, object]] = None
    try:
        if isinstance(raw_data, dict) and isinstance(raw_data.get("rows"), list):
            rows = raw_data["rows"]
            for row in rows:
                if not isinstance(row, dict):
                    continue
                date_val = row.get("date")
                close_val = _num(row.get("close"))
                if not date_val or close_val is None:
                    continue
                point: Dict[str, object] = {"date": str(date_val), "close": close_val}
                for key in [
                    "open",
                    "high",
                    "low",
                    "volume",
                    "sma20",
                    "sma50",
                    "sma200",
                    "rsi14",
                    "macd",
                    "macd_signal",
                    "macd_hist",
                    "bb_upper",
                    "bb_lower",
                    "atr14",
                ]:
                    val = _num(row.get(key))
                    if val is not None:
                        point[key] = val
                points.append(point)
            latest = next(
                (row for row in reversed(rows) if isinstance(row, dict) and _num(row.get("close")) is not None),
                None,
            )
    except Exception:
        points = []
        latest = None

    if not points:
        abort(404, description=f"No price rows for '{safe_symbol}'")

    def _coerce_dict(data):
        if not isinstance(data, dict):
            return None
        if safe_symbol in data:
            return data.get(safe_symbol)
        if safe_symbol.lower() in data:
            return data.get(safe_symbol.lower())
        if len(data) == 1:
            return next(iter(data.values()))
        return data

    def _mod(name: str) -> Dict[str, object]:
        if not isinstance(modules, dict):
            return {}
        return _coerce_dict(modules.get(name) or {}) or {}

    def _num_first(*vals):
        for val in vals:
            num = _num(val)
            if num is not None:
                return num
        return None

    latest_extended = dict(latest or {})
    price_mod = _mod("price")
    summary_mod = _mod("summaryDetail")
    stats_mod = _mod("defaultKeyStatistics")
    fin_mod = _mod("financialData")

    earnings_date = None
    ex_div_date = None
    forward_dividend = None
    try:
        ed = summary_mod.get("earningsDate") or fin_mod.get("earningsDate")
        if isinstance(ed, list) and ed:
            earnings_date = ed[0] if not isinstance(ed[0], dict) else ed[0].get("fmt") or ed[0].get("raw")
        elif isinstance(ed, dict):
            earnings_date = ed.get("fmt") or ed.get("raw")
        elif ed:
            earnings_date = ed
    except Exception:
        earnings_date = None
    try:
        div = summary_mod.get("dividendRate") or summary_mod.get("dividendYield")
        if isinstance(div, dict):
            forward_dividend = div.get("fmt") or div.get("raw")
        else:
            forward_dividend = div
    except Exception:
        forward_dividend = None
    try:
        exd = summary_mod.get("exDividendDate")
        if isinstance(exd, dict):
            ex_div_date = exd.get("fmt") or exd.get("raw")
        else:
            ex_div_date = exd
    except Exception:
        ex_div_date = None

    latest_extended.update(
        {
            "prevClose": _num_first(price_mod.get("regularMarketPreviousClose"), summary_mod.get("previousClose")),
            "open": _num_first(price_mod.get("regularMarketOpen"), latest_extended.get("open")),
            "high": _num_first(price_mod.get("regularMarketDayHigh"), latest_extended.get("high")),
            "low": _num_first(price_mod.get("regularMarketDayLow"), latest_extended.get("low")),
            "bid": _num_first(price_mod.get("bid")),
            "bidSize": _num_first(price_mod.get("bidSize")),
            "ask": _num_first(price_mod.get("ask")),
            "askSize": _num_first(price_mod.get("askSize")),
            "avgVolume": _num_first(
                price_mod.get("averageDailyVolume3Month"),
                summary_mod.get("averageDailyVolume3Month"),
                summary_mod.get("averageDailyVolume10Day"),
            ),
            "marketCap": _num_first(
                price_mod.get("marketCap"),
                summary_mod.get("marketCap"),
                fin_mod.get("marketCap"),
                (fundamentals or {}).get("market_cap") if isinstance(fundamentals, dict) else None,
            ),
            "beta": _num_first(summary_mod.get("beta"), stats_mod.get("beta")),
            "trailingPE": _num_first(
                summary_mod.get("trailingPE"), price_mod.get("trailingPE"), stats_mod.get("trailingPE")
            ),
            "forwardPE": _num_first(
                summary_mod.get("forwardPE"),
                price_mod.get("forwardPE"),
                stats_mod.get("forwardPE"),
                (fundamentals or {}).get("pe_forward") if isinstance(fundamentals, dict) else None,
            ),
            "fiftyTwoWeekLow": _num_first(price_mod.get("fiftyTwoWeekLow"), summary_mod.get("fiftyTwoWeekLow")),
            "fiftyTwoWeekHigh": _num_first(price_mod.get("fiftyTwoWeekHigh"), summary_mod.get("fiftyTwoWeekHigh")),
            "allTimeHigh": _num_first(price_mod.get("allTimeHigh")),
            "allTimeLow": _num_first(price_mod.get("allTimeLow")),
            "targetMeanPrice": _num_first(
                price_mod.get("targetMeanPrice"),
                fin_mod.get("targetMeanPrice"),
                summary_mod.get("targetMeanPrice"),
                (fundamentals or {}).get("target_mean_price") if isinstance(fundamentals, dict) else None,
            ),
            "peRatio": _num_first(
                summary_mod.get("trailingPE"), price_mod.get("trailingPE"), stats_mod.get("trailingPE")
            ),
            "eps": _num_first(
                stats_mod.get("trailingEps"),
                fin_mod.get("epsCurrentYear"),
                price_mod.get("epsCurrentYear"),
            ),
            "forwardDividend": forward_dividend,
            "exDividendDate": ex_div_date,
            "earningsDate": earnings_date,
        }
    )

    return {
        "symbol": safe_symbol,
        "assetclass": safe_assetclass,
        "rows": points,
        "latest": latest_extended,
        "fundamentals": fundamentals,
        "modules": modules,
        "path": str(existing_path),
    }


def list_latest_indicator_rows(
    assetclass: str = "stocks", symbols: Optional[List[str]] = None
) -> List[Dict[str, object]]:
    """Collect latest row with indicators from Yahoo-enriched files or requested symbols."""
    results: List[Dict[str, object]] = []
    target_symbols = [normalize_symbol(sym) for sym in (symbols or []) if normalize_symbol(sym)]

    def _num(val):
        try:
            f = float(val)
            return f if math.isfinite(f) else None
        except Exception:
            return None

    def _coerce_mod(mods: dict, name: str, symbol: str):
        if not isinstance(mods, dict):
            return {}
        mod = mods.get(name) or {}
        if not isinstance(mod, dict):
            return {}
        if symbol in mod:
            mod = mod.get(symbol) or {}
        elif symbol.lower() in mod:
            mod = mod.get(symbol.lower()) or {}
        elif len(mod) == 1:
            mod = next(iter(mod.values())) or {}
        return mod if isinstance(mod, dict) else {}

    if target_symbols:
        for sym in target_symbols:
            try:
                history = load_or_fetch_ticker_history(sym, assetclass=assetclass)
            except Exception:
                continue
            latest = history.get("latest") if isinstance(history, dict) else None
            if not isinstance(latest, dict):
                continue
            close_val = latest.get("close")
            if close_val is None or not isinstance(close_val, (int, float)) or not math.isfinite(close_val):
                continue
            fundamentals = history.get("fundamentals") if isinstance(history, dict) else {}
            modules = history.get("modules") if isinstance(history, dict) else {}
            stats_mod = _coerce_mod(modules, "defaultKeyStatistics", sym)
            summary_mod = _coerce_mod(modules, "summaryDetail", sym)
            price_mod = _coerce_mod(modules, "price", sym)
            # Compute 52w high / avg vol from history rows if available
            rows_hist = history.get("rows") if isinstance(history, dict) else []
            closes_hist = [
                r.get("close")
                for r in rows_hist
                if isinstance(r, dict) and isinstance(r.get("close"), (int, float)) and math.isfinite(r.get("close"))
            ]
            f2h_series = max(closes_hist[-252:], default=None) if closes_hist else None
            vols_hist = [
                r.get("volume")
                for r in rows_hist
                if isinstance(r, dict) and isinstance(r.get("volume"), (int, float)) and math.isfinite(r.get("volume"))
            ]
            avg_vol_hist = sum(vols_hist[-50:]) / len(vols_hist[-50:]) if vols_hist[-50:] else None

            if isinstance(fundamentals, dict):
                if fundamentals.get("ytd_pct") is None:
                    ytd_raw = stats_mod.get("ytdReturn")
                    if ytd_raw is not None:
                        fundamentals["ytd_pct"] = ytd_raw * (100 if abs(ytd_raw) < 5 else 1)
                if fundamentals.get("beta") is None:
                    fundamentals["beta"] = _num(stats_mod.get("beta")) or _num(summary_mod.get("beta"))
                if fundamentals.get("forwardPE") is None and fundamentals.get("forward_pe") is None:
                    fpe = _num(summary_mod.get("forwardPE")) or _num(stats_mod.get("forwardPE"))
                    if fpe is not None:
                        fundamentals["forwardPE"] = fpe
                        fundamentals["forward_pe"] = fpe
                if fundamentals.get("sector") is None and stats_mod.get("category"):
                    fundamentals["sector"] = stats_mod.get("category")
                    fundamentals["sectorDisp"] = stats_mod.get("category")
                # Add fifty_two_week_high for upside calc
                if fundamentals.get("fifty_two_week_high") is None:
                    f2h = _num(
                        summary_mod.get("fiftyTwoWeekHigh")
                        or price_mod.get("fiftyTwoWeekHigh")
                        or stats_mod.get("fiftyTwoWeekHigh")
                    )
                    if f2h is not None:
                        fundamentals["fifty_two_week_high"] = f2h
                if fundamentals.get("fifty_two_week_high") is None and f2h_series is not None:
                    fundamentals["fifty_two_week_high"] = f2h_series
                if fundamentals.get("avg_volume") is None and avg_vol_hist is not None:
                    fundamentals["avg_volume"] = avg_vol_hist
            results.append({"symbol": sym, "row": latest, "fundamentals": fundamentals})
        return results

    asset_dir = asset_data_dir(assetclass, DATA_DIR)
    for path in asset_dir.glob(f"*_{assetclass.lower()}_data.json"):
        try:
            data = json.loads(path.read_text())
        except Exception:
            continue
        rows = data.get("rows")
        if not isinstance(rows, list) or not rows:
            continue
        last = rows[-1]
        close_val = last.get("close")
        if close_val is None or not isinstance(close_val, (int, float)) or not math.isfinite(close_val):
            continue
        symbol = normalize_symbol(data.get("symbol") or path.name.split("_")[0])
        fundamentals = data.get("fundamentals") if isinstance(data.get("fundamentals"), dict) else {}
        modules = data.get("modules") if isinstance(data.get("modules"), dict) else {}

        def _num(val):
            try:
                f = float(val)
                return f if math.isfinite(f) else None
            except Exception:
                return None

        def _coerce_mod(mods: dict, name: str, symbol: str):
            if not isinstance(mods, dict):
                return {}
            mod = mods.get(name) or {}
            if not isinstance(mod, dict):
                return {}
            if symbol in mod:
                mod = mod.get(symbol) or {}
            elif symbol.lower() in mod:
                mod = mod.get(symbol.lower()) or {}
            elif len(mod) == 1:
                mod = next(iter(mod.values())) or {}
            return mod if isinstance(mod, dict) else {}

        summary_mod = _coerce_mod(modules, "summaryDetail", symbol)
        stats_mod = _coerce_mod(modules, "defaultKeyStatistics", symbol)
        price_mod = _coerce_mod(modules, "price", symbol)

        # Compute 52w high and volume avg from series for safety
        closes = [r.get("close") for r in rows if isinstance(r, dict) and isinstance(r.get("close"), (int, float, float))]
        closes = [c for c in closes if isinstance(c, (int, float)) and math.isfinite(c)]
        f2h_series = max(closes[-252:], default=None) if closes else None
        volumes = [r.get("volume") for r in rows if isinstance(r, dict) and isinstance(r.get("volume"), (int, float))]
        volumes = [v for v in volumes if isinstance(v, (int, float)) and math.isfinite(v)]
        avg_vol_50 = sum(volumes[-50:]) / len(volumes[-50:]) if volumes[-50:] else None

        if isinstance(fundamentals, dict):
            if fundamentals.get("ytd_pct") is None:
                ytd_raw = stats_mod.get("ytdReturn")
                if ytd_raw is not None:
                    fundamentals["ytd_pct"] = ytd_raw * (100 if abs(ytd_raw) < 5 else 1)
            if fundamentals.get("target_upside_pct") is None and fundamentals.get("ytd_pct") is not None:
                fundamentals["target_upside_pct"] = fundamentals.get("ytd_pct")
            if fundamentals.get("beta") is None:
                fundamentals["beta"] = _num(stats_mod.get("beta")) or _num(summary_mod.get("beta"))
            if fundamentals.get("forwardPE") is None and fundamentals.get("forward_pe") is None:
                fpe = _num(summary_mod.get("forwardPE")) or _num(stats_mod.get("forwardPE"))
                if fpe is not None:
                    fundamentals["forwardPE"] = fpe
                    fundamentals["forward_pe"] = fpe
            if fundamentals.get("sector") is None and stats_mod.get("category"):
                fundamentals["sector"] = stats_mod.get("category")
                fundamentals["sectorDisp"] = stats_mod.get("category")
            if fundamentals.get("fifty_two_week_high") is None and f2h_series is not None:
                fundamentals["fifty_two_week_high"] = f2h_series
            if fundamentals.get("avg_volume") is None and avg_vol_50 is not None:
                fundamentals["avg_volume"] = avg_vol_50
            if fundamentals.get("fifty_two_week_high") is None:
                f2h = _num(
                    summary_mod.get("fiftyTwoWeekHigh")
                    or price_mod.get("fiftyTwoWeekHigh")
                    or stats_mod.get("fiftyTwoWeekHigh")
                )
                if f2h is not None:
                    fundamentals["fifty_two_week_high"] = f2h

        results.append({"symbol": symbol, "row": last, "fundamentals": fundamentals})
    return results


def collect_portfolio_data(assetclass: str = "stocks", symbols: Optional[List[str]] = None) -> List[Dict[str, object]]:
    """Gather enriched fundamentals + tech snapshot for AI portfolio prompt."""
    rows: List[Dict[str, object]] = []
    target_symbols = [normalize_symbol(sym) for sym in (symbols or []) if normalize_symbol(sym)]
    safe_assetclass = assetclass.lower()
    known_highs = {"IWM": 269.80, "QQQ": 637.01, "SPY": 714.34, "VUG": 505.40}

    candidate_paths: List[Path] = []
    asset_dir = asset_data_dir(safe_assetclass, DATA_DIR)
    if target_symbols:
        for sym in target_symbols:
            safe_symbol = normalize_symbol(sym)
            try:
                load_or_fetch_ticker_history(sym, assetclass=safe_assetclass)
            except Exception:
                continue
            json_path = asset_dir / f"{safe_symbol}_{safe_assetclass}_data.json"
            legacy_path = DATA_DIR / f"{safe_symbol}_data.json"
            path = json_path if json_path.exists() else legacy_path
            if path.exists():
                candidate_paths.append(path)
        if not candidate_paths:
            return rows
    else:
        # Optional refresh: only attempt downloads when explicitly enabled to avoid slowing requests
        if os.getenv("AUTO_REFRESH_HOLDINGS", "0") == "1":
            try:
                from utils.yahoo_data_loader import download_with_indicators

                for sym in tickers_from_holdings(assetclass=safe_assetclass):
                    try:
                        download_with_indicators(symbol=normalize_symbol(sym), assetclass=safe_assetclass)
                    except Exception:
                        continue
            except Exception:
                pass
        candidate_paths = list(asset_dir.glob(f"*_{safe_assetclass}_data.json"))

    for path in candidate_paths:
        try:
            payload = json.loads(path.read_text())
        except Exception:
            continue
        payload = sanitize(payload)
        if not isinstance(payload, dict):
            continue
        symbol = normalize_symbol(payload.get("symbol") or path.name.split("_")[0])
        series = payload.get("rows")
        if not isinstance(series, list) or not series:
            continue
        fundamentals = payload.get("fundamentals") if isinstance(payload.get("fundamentals"), dict) else {}
        modules = payload.get("modules") if isinstance(payload.get("modules"), dict) else {}
        last = next((r for r in reversed(series) if isinstance(r, dict)), None) or {}

        def _num(val):
            try:
                v = float(val)
                return v if math.isfinite(v) else None
            except Exception:
                return None

        def _ytd_pct(series_rows: List[Dict[str, object]]) -> Optional[float]:
            if not series_rows:
                return None
            try:
                ordered = sorted(series_rows, key=lambda r: r.get("date", ""))
            except Exception:
                ordered = series_rows
            last_row = next((r for r in reversed(ordered) if _num(r.get("close")) is not None), None)
            if not last_row:
                return None
            last_year = str(last_row.get("date") or "")[:4]
            start_row = next(
                (
                    r
                    for r in ordered
                    if str(r.get("date") or "").startswith(last_year) and _num(r.get("close")) is not None
                ),
                None,
            ) or ordered[0]
            start_close = _num(start_row.get("close"))
            last_close = _num(last_row.get("close"))
            if start_close is None or last_close is None or start_close == 0:
                return None
            return ((last_close - start_close) / start_close) * 100

        ytd_pct = _ytd_pct(series if isinstance(series, list) else [])
        sma50 = _num(last.get("sma50")) or _num(fundamentals.get("sma50"))
        rsi = _num(last.get("rsi14")) or _num(fundamentals.get("rsi14"))
        volumes = [_num(r.get("volume")) for r in series if isinstance(r, dict) and _num(r.get("volume")) is not None]
        volume_trend = _num(fundamentals.get("volume_trend"))
        if volume_trend is None and volumes:
            latest_vol = volumes[-1]
            avg30 = sum(volumes[-30:]) / max(1, len(volumes[-30:]))
            if latest_vol is not None and avg30:
                volume_trend = latest_vol / avg30
        # Enrich fundamentals with beta/forward PE/sector if available from modules
        def _first(*vals):
            for val in vals:
                num = _num(val)
                if num is not None:
                    return num
            return None

        def _coerce_mod(mods: dict, name: str):
            if not isinstance(mods, dict):
                return {}
            mod = mods.get(name) or {}
            if not isinstance(mod, dict):
                return {}
            if symbol in mod:
                mod = mod.get(symbol) or {}
            elif symbol.lower() in mod:
                mod = mod.get(symbol.lower()) or {}
            elif len(mod) == 1:
                mod = next(iter(mod.values())) or {}
            return mod if isinstance(mod, dict) else {}

        summary_mod = _coerce_mod(modules, "summaryDetail")
        stats_mod = _coerce_mod(modules, "defaultKeyStatistics")
        price_mod = _coerce_mod(modules, "price")
        asset_profile = _coerce_mod(modules, "assetProfile")

        # ETF-specific enrichments from payload/modules if missing
        if safe_assetclass == "etf" and isinstance(fundamentals, dict):
            stats_mod = stats_mod or {}
            summary_mod = summary_mod or {}
            if fundamentals.get("current_price") is None and _num(last.get("close")) is not None:
                fundamentals["current_price"] = _num(last.get("close"))
            sector_existing = fundamentals.get("sector") or fundamentals.get("sectorDisp")
            if not sector_existing or str(sector_existing).lower() in ("unknown", "n/a", "na"):
                sector_val = (
                    payload.get("category")
                    or stats_mod.get("category")
                    or summary_mod.get("category")
                    or sector_existing
                )
                if sector_val:
                    fundamentals["sector"] = sector_val
                    fundamentals["sectorDisp"] = sector_val
            if fundamentals.get("beta") is None:
                fundamentals["beta"] = payload.get("beta3Year") if payload.get("beta3Year") is not None else stats_mod.get("beta3Year")
            if fundamentals.get("forward_pe") is None:
                fp = payload.get("trailingPE")
                if fp is None:
                    fp = summary_mod.get("trailingPE") or stats_mod.get("trailingPE")
                if fp is not None:
                    fundamentals["forward_pe"] = fp
                    fundamentals["forwardPE"] = fp
            ytd_return_raw = payload.get("ytdReturn") or stats_mod.get("ytdReturn")
            if fundamentals.get("ytd_pct") is None and ytd_return_raw is not None:
                fundamentals["ytd_pct"] = ytd_return_raw * (100 if abs(ytd_return_raw) < 5 else 1)
        summary_mod = summary_mod or {}
        stats_mod = stats_mod or {}
        price_mod = price_mod or {}
        asset_profile = asset_profile or {}

        beta_val = _first(
            fundamentals.get("beta") if isinstance(fundamentals, dict) else None,
            summary_mod.get("beta"),
            stats_mod.get("beta"),
        )
        forward_pe_val = _first(
            fundamentals.get("forward_pe") if isinstance(fundamentals, dict) else None,
            fundamentals.get("forwardPE") if isinstance(fundamentals, dict) else None,
            summary_mod.get("forwardPE"),
            price_mod.get("forwardPE"),
            stats_mod.get("forwardPE"),
        )
        sector_val = (
            fundamentals.get("sectorDisp")
            or fundamentals.get("sector")
            or asset_profile.get("sector")
            or None
        )
        if isinstance(fundamentals, dict):
            if beta_val is not None:
                fundamentals["beta"] = beta_val
            if forward_pe_val is not None:
                fundamentals["forward_pe"] = forward_pe_val
                fundamentals["forwardPE"] = forward_pe_val
            if sector_val:
                fundamentals["sector"] = sector_val
                fundamentals["sectorDisp"] = sector_val
        latest_ohlc = next(
            (r for r in reversed(series) if isinstance(r, dict) and _num(r.get("close")) is not None),
            last,
        ) or {}
        # Ensure ETF fundamentals have a current_price value for scoring/allocations
        if safe_assetclass == "etf" and isinstance(fundamentals, dict):
            if fundamentals.get("current_price") is None and _num(latest_ohlc.get("close")) is not None:
                fundamentals["current_price"] = _num(latest_ohlc.get("close"))
        # Derived snapshot metrics for ranking/LLM friendliness
        closes = [_num(r.get("close")) for r in series if isinstance(r, dict) and _num(r.get("close")) is not None]
        latest_close = _num(latest_ohlc.get("close"))
        latest_vol = _num(latest_ohlc.get("volume"))
        avg_vol = None
        if volumes:
            avg_vol = sum(volumes[-50:]) / max(1, len(volumes[-50:]))
        sma20_val = _num(latest_ohlc.get("sma20")) or _num(fundamentals.get("sma20"))
        sma50_val = _num(latest_ohlc.get("sma50")) or _num(fundamentals.get("sma50"))
        sma200_val = _num(latest_ohlc.get("sma200")) or _num(fundamentals.get("sma200"))
        macd_hist_val = _num(latest_ohlc.get("macd_hist"))
        bb_upper_val = _num(latest_ohlc.get("bb_upper"))
        bb_lower_val = _num(latest_ohlc.get("bb_lower"))
        atr14_val = _num(latest_ohlc.get("atr14"))
        fifty_two_high = None
        try:
            fifty_two_high = max(closes[-252:]) if closes else None
        except Exception:
            fifty_two_high = None
        pct_from_52w_high = None
        if latest_close is not None and fifty_two_high not in (None, 0):
            pct_from_52w_high = ((latest_close - fifty_two_high) / fifty_two_high) * 100
        volume_ratio = None
        if latest_vol is not None and avg_vol:
            volume_ratio = latest_vol / avg_vol
        price_vs_sma20 = (latest_close - sma20_val) / sma20_val * 100 if latest_close is not None and sma20_val else None
        price_vs_sma50 = (latest_close - sma50_val) / sma50_val * 100 if latest_close is not None and sma50_val else None
        price_vs_sma200 = (
            (latest_close - sma200_val) / sma200_val * 100 if latest_close is not None and sma200_val else None
        )
        atr_pct = (atr14_val / latest_close * 100) if atr14_val is not None and latest_close else None
        # Attach these to fundamentals so downstream consumers see them
        if isinstance(fundamentals, dict):
            fundamentals.setdefault("close", latest_close)
            fundamentals.setdefault("volume", latest_vol)
            fundamentals.setdefault("avg_volume", avg_vol)
            fundamentals.setdefault("sma20", sma20_val)
            fundamentals.setdefault("sma50", sma50_val)
            fundamentals.setdefault("sma200", sma200_val)
            fundamentals.setdefault("rsi14", _num(latest_ohlc.get("rsi14")) or fundamentals.get("rsi14"))
            fundamentals.setdefault("macd_hist", macd_hist_val)
            fundamentals.setdefault("atr14", atr14_val)
            fundamentals.setdefault("bb_upper", bb_upper_val)
            fundamentals.setdefault("bb_lower", bb_lower_val)
            fundamentals.setdefault("fifty_two_week_high", fifty_two_high)
            fundamentals.setdefault("pct_from_52w_high", pct_from_52w_high)
            fundamentals.setdefault("volume_ratio", volume_ratio)
            fundamentals.setdefault("price_vs_sma20_pct", price_vs_sma20)
            fundamentals.setdefault("price_vs_sma50_pct", price_vs_sma50)
            fundamentals.setdefault("price_vs_sma200_pct", price_vs_sma200)
            fundamentals.setdefault("atr_pct", atr_pct)
        rows.append(
            {
                "ticker": symbol,
                "fundamentals": fundamentals,
                "modules": modules,
                "latest": latest_ohlc,
                "ytd_pct": ytd_pct,
                "rsi14": rsi,
                "sma50": sma50,
                "volume_trend": volume_trend,
                "Reason": payload.get("Reason") or payload.get("reason"),
            }
        )

    return rows


def known_symbols(assetclass: str = "stocks") -> List[str]:
    """Return symbols discovered from existing data files for the given asset class."""
    symbols: set[str] = set()
    asset_dir = asset_data_dir(assetclass, DATA_DIR)
    for path in asset_dir.glob(f"*_{assetclass.lower()}_data.json"):
        try:
            payload = json.loads(path.read_text())
            sym = payload.get("symbol") if isinstance(payload, dict) else None
            if not sym:
                sym = path.name.split("_")[0]
            if sym:
                symbols.add(str(sym).upper())
        except Exception:
            continue
    return sorted(symbols)


def tickers_from_holdings(assetclass: str = "stocks") -> List[str]:
    """Collect tickers from holdings/config files to drive bulk regeneration.

    For ETFs, we use the curated list in etf_holdings.json (if present).
    For stocks, we read any *_holdings.json lists and traditional *-holdings.json files.
    """
    from utils.paths import HOLDINGS_DIR  # local import to avoid cycles

    symbols: set[str] = set()
    safe_asset = (assetclass or "stocks").lower()

    def _add(sym: str | None) -> None:
        if not sym:
            return
        token = normalize_symbol(sym)
        if token and token != "-":
            symbols.add(token)

    def _from_rows(rows):
        if not isinstance(rows, list):
            return
        for row in rows:
            if not isinstance(row, dict):
                continue
            ticker = (
                row.get("ticker")
                or row.get("Ticker")
                or row.get("TICKER")
                or row.get("Symbol")
                or row.get("symbol")
            )
            _add(ticker)

    # ETF list file support (plain list or dict with rows)
    if safe_asset == "etf":
        for name in ("etf_holdings.json", "etf-holdings.json"):
            path = HOLDINGS_DIR / name
            if not path.exists():
                continue
            try:
                payload = json.loads(path.read_text())
            except Exception:
                continue
            if isinstance(payload, list):
                for item in payload:
                    _add(item)
            elif isinstance(payload, dict):
                _from_rows(payload.get("rows"))
        return sorted(symbols)

    # Stocks: support curated list file plus legacy *-holdings payloads
    for name in ("stocks_holdings.json", "stocks-holdings.json"):
        path = HOLDINGS_DIR / name
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text())
        except Exception:
            continue
        if isinstance(payload, list):
            for item in payload:
                _add(item)
        elif isinstance(payload, dict):
            _from_rows(payload.get("rows"))

    for fund_path in HOLDINGS_DIR.glob("*-holdings.json"):
        try:
            payload = json.loads(fund_path.read_text())
        except Exception:
            continue
        rows = payload.get("rows") if isinstance(payload, dict) else payload
        _from_rows(rows)

    return sorted(symbols)


def download_fund_holdings(symbol: str) -> Path:
    """
    Download ETF holdings using etfpy (full holdings) and persist to holdings folder.

    The resulting file is saved as <SYMBOL>-holdings.json under HOLDINGS_DIR and
    contains the full holdings (not just top 10) when available.
    """
    safe_symbol = normalize_symbol(symbol)
    if not safe_symbol:
        raise ValueError("Symbol is required")

    rows = []
    as_of = None
    source = "yahooquery"

    # Use yahooquery fund_holding_info for ETFs
    try:
        t = YqTicker(safe_symbol)
        info = t.fund_holding_info or {}
        fund_info = info.get(safe_symbol) or info.get(safe_symbol.lower()) or {}
        holdings = fund_info.get("holdings") or fund_info.get("equityHoldings") or []
        rows = holdings if isinstance(holdings, list) else []
        as_of = fund_info.get("asOfDate") or fund_info.get("as_of_date") or fund_info.get("as_of")
    except Exception:
        rows = []
        as_of = None

    if not rows:
        raise RuntimeError(f"No holdings rows returned for {safe_symbol}")

    HOLDINGS_DIR.mkdir(parents=True, exist_ok=True)
    path = HOLDINGS_DIR / f"{safe_symbol}-holdings.json"
    payload = {"symbol": safe_symbol, "as_of": as_of, "count": len(rows), "rows": rows, "source": source}
    path.write_text(json.dumps(payload, indent=2))
    return path
