from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import requests

from utils.data import list_latest_indicator_rows
from utils.helpers import asset_data_dir, normalize_symbol
from utils.paths import DATA_DIR, ETF_DIR

SPY_PATH = ETF_DIR / "SPY_etf_data.json"

WEIGHTS = {
    "momentum": 0.25,
    "rsi": 0.15,
    "macd": 0.20,
    "volume": 0.15,
    "volatility": 0.10,
    "upside": 0.15,
}
BOOST_RELATIVE_TO_SPY = 0.05
THRESHOLD = 0.6
MAX_PICKS = 5


@dataclass
class TickerSnapshot:
    symbol: str
    close: Optional[float] = None
    volume: Optional[float] = None
    sma20: Optional[float] = None
    sma50: Optional[float] = None
    sma200: Optional[float] = None
    rsi14: Optional[float] = None
    macd: Optional[float] = None
    macd_hist: Optional[float] = None
    atr14: Optional[float] = None
    volume_trend: Optional[float] = None
    upside_pct: Optional[float] = None
    extras: Dict[str, object] = field(default_factory=dict)

    @property
    def atr_pct(self) -> Optional[float]:
        if self.close is None or self.atr14 is None:
            return None
        return (self.atr14 / self.close) * 100


def _to_float(val: object) -> Optional[float]:
    try:
        fval = float(val)
    except Exception:
        return None
    return fval if math.isfinite(fval) else None


def _coerce_module(modules: dict, name: str, symbol: str) -> Dict[str, object]:
    if not isinstance(modules, dict):
        return {}
    mod = modules.get(name) or {}
    if not isinstance(mod, dict):
        return {}
    if symbol in mod:
        mod = mod.get(symbol) or {}
    elif symbol.lower() in mod:
        mod = mod.get(symbol.lower()) or {}
    elif len(mod) == 1:
        mod = next(iter(mod.values())) or {}
    return mod if isinstance(mod, dict) else {}


def parse_prompt_metrics(prompt: str) -> Dict[str, TickerSnapshot]:
    """Extract metrics from the LLM prompt text."""
    snapshots: Dict[str, TickerSnapshot] = {}
    key_pattern = re.compile(
        r"(close|volume|sma20|sma50|sma200|rsi14|macd_hist|macd|atr14)\s+([^\s,]+)", re.IGNORECASE
    )
    for line in (prompt or "").splitlines():
        if ":" not in line or "close" not in line.lower():
            continue
        try:
            ticker_part, rest = line.split(":", 1)
        except ValueError:
            continue
        ticker = ticker_part.strip().upper()
        if not ticker:
            continue
        values: Dict[str, Optional[float]] = {}
        for match in key_pattern.finditer(rest):
            key = match.group(1).lower()
            values[key] = _to_float(match.group(2))
        snapshots[ticker] = TickerSnapshot(
            symbol=ticker,
            close=values.get("close"),
            volume=values.get("volume"),
            sma20=values.get("sma20"),
            sma50=values.get("sma50"),
            sma200=values.get("sma200"),
            rsi14=values.get("rsi14"),
            macd=values.get("macd"),
            macd_hist=values.get("macd_hist"),
            atr14=values.get("atr14"),
        )
    return snapshots


def parse_recommendations(payload: Dict[str, object]) -> Dict[str, Dict[str, object]]:
    """Pull upside % and volume trends from the recommendation block."""
    results: Dict[str, Dict[str, object]] = {}
    rec_section = payload.get("recommendation")
    rows = rec_section[1] if isinstance(rec_section, list) and len(rec_section) > 1 else []
    if not rows:
        rows = payload.get("rows") or []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("Ticker") or "").upper()
        if not ticker:
            continue
        reason = row.get("Reason") or ""
        vol_ratio = None
        match = re.search(r"Vol\\s+([0-9.]+)x", reason)
        if match:
            vol_ratio = _to_float(match.group(1))
        results[ticker] = {
            "upside_pct": _to_float(row.get("UpsidePct")),
            "rank": row.get("Rank"),
            "volume_trend": vol_ratio,
        }
    return results


def load_spy_snapshot(upside_pct: Optional[float]) -> TickerSnapshot:
    """Use the freshest SPY row plus any available fundamentals."""
    payload = json.loads(SPY_PATH.read_text(encoding="utf-8"))
    rows = payload.get("rows") or []
    latest = rows[-1] if rows else {}
    fundamentals = payload.get("fundamentals") or {}
    modules = payload.get("modules") or {}

    summary_mod = _coerce_module(modules, "summaryDetail", "SPY")
    stats_mod = _coerce_module(modules, "defaultKeyStatistics", "SPY")
    volume_trend = fundamentals.get("volume_trend")
    if volume_trend is None and latest.get("volume"):
        vols = [
            _to_float(r.get("volume"))
            for r in rows
            if isinstance(r, dict) and _to_float(r.get("volume")) is not None
        ]
        if vols[-30:]:
            avg30 = sum(vols[-30:]) / len(vols[-30:])
            if avg30:
                volume_trend = _to_float(latest.get("volume")) / avg30

    extras = {
        "ytdReturn": stats_mod.get("ytdReturn"),
        "threeYearAverageReturn": stats_mod.get("threeYearAverageReturn"),
    }
    snap = TickerSnapshot(
        symbol="SPY",
        close=_to_float(latest.get("close")),
        volume=_to_float(latest.get("volume")),
        sma20=_to_float(latest.get("sma20")),
        sma50=_to_float(latest.get("sma50")),
        sma200=_to_float(latest.get("sma200")),
        rsi14=_to_float(latest.get("rsi14") or fundamentals.get("rsi14")),
        macd=_to_float(latest.get("macd")),
        macd_hist=_to_float(latest.get("macd_hist")),
        atr14=_to_float(latest.get("atr14")),
        volume_trend=_to_float(volume_trend),
        upside_pct=upside_pct,
        extras=extras,
    )
    if snap.upside_pct is None:
        high52 = _to_float(summary_mod.get("fiftyTwoWeekHigh"))
        if high52 and snap.close:
            snap.upside_pct = (high52 - snap.close) / snap.close * 100
    return snap


def fetch_ai_payload(base_url: str, assetclass: str, symbols: Optional[List[str]]) -> Dict[str, object]:
    """Call the bulk recommendation API to retrieve AI prompt and rows."""
    params = {"assetclass": assetclass}
    if symbols:
        params["symbols"] = ",".join(symbols)
    resp = requests.get(base_url, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def load_local_rows(assetclass: str, symbols: List[str]) -> Dict[str, dict]:
    """Load latest row from local data files to enrich missing fields."""
    rows: Dict[str, dict] = {}
    asset_dir = asset_data_dir(assetclass, DATA_DIR)
    for sym in symbols:
        safe_sym = normalize_symbol(sym)
        path = asset_dir / f"{safe_sym}_{assetclass}_data.json"
        legacy = DATA_DIR / f"{safe_sym}_data.json"
        chosen = path if path.exists() else legacy
        if not chosen.exists():
            continue
        try:
            data = json.loads(chosen.read_text())
            series = data.get("rows") or []
            latest = series[-1] if series else {}
            rows[sym] = latest
        except Exception:
            continue
    return rows


def _load_summary_f2h(assetclass: str, symbol: str) -> Optional[float]:
    """Read summaryDetail.fiftyTwoWeekHigh from the local JSON if available."""
    safe_sym = normalize_symbol(symbol)
    asset_dir = asset_data_dir(assetclass, DATA_DIR)
    path = asset_dir / f"{safe_sym}_{assetclass}_data.json"
    legacy = DATA_DIR / f"{safe_sym}_data.json"
    chosen = path if path.exists() else legacy
    if not chosen.exists():
        return None
    try:
        data = json.loads(chosen.read_text())
        modules = data.get("modules") or {}
        summary = _coerce_module(modules, "summaryDetail", symbol)
        return _to_float(summary.get("fiftyTwoWeekHigh") or summary.get("fifty_two_week_high"))
    except Exception:
        return None


def build_snapshots_from_items(items: List[Dict[str, object]], assetclass: str) -> Dict[str, TickerSnapshot]:
    """Create snapshots directly from local indicator rows."""
    snapshots: Dict[str, TickerSnapshot] = {}
    for item in items:
        row = item.get("row") if isinstance(item, dict) else {}
        fundamentals = item.get("fundamentals") if isinstance(item, dict) else {}
        symbol = str(item.get("symbol") or "").upper()
        if not symbol or not isinstance(row, dict):
            continue
        close = _to_float(row.get("close") or (fundamentals or {}).get("close"))
        summary = _coerce_module(item.get("modules") or {}, "summaryDetail", symbol)
        f2h = _to_float(
            summary.get("fiftyTwoWeekHigh")
            or (fundamentals or {}).get("fifty_two_week_high")
            or summary.get("fifty_two_week_high")
            or _load_summary_f2h(assetclass, symbol)
        )
        upside_pct = None
        if close not in (None, 0) and f2h not in (None, 0):
            upside_pct = ((f2h - close) / close) * 100
        snapshots[symbol] = TickerSnapshot(
            symbol=symbol,
            close=close,
            volume=_to_float(row.get("volume")),
            sma20=_to_float(row.get("sma20") or (fundamentals or {}).get("sma20")),
            sma50=_to_float(row.get("sma50") or (fundamentals or {}).get("sma50")),
            sma200=_to_float(row.get("sma200") or (fundamentals or {}).get("sma200")),
            rsi14=_to_float(row.get("rsi14") or (fundamentals or {}).get("rsi14")),
            macd=_to_float(row.get("macd") or (fundamentals or {}).get("macd")),
            macd_hist=_to_float(row.get("macd_hist") or (fundamentals or {}).get("macd_hist")),
            atr14=_to_float(row.get("atr14") or (fundamentals or {}).get("atr14")),
            volume_trend=_to_float((fundamentals or {}).get("volume_trend")),
            upside_pct=upside_pct,
            extras={"source": "local"},
        )
    return snapshots


def merge_snapshots(snapshots: Dict[str, TickerSnapshot], rec_info: Dict[str, Dict[str, object]], assetclass: str) -> None:
    """Attach rec info and fill gaps using local data files."""
    symbols = list(snapshots.keys())
    local_rows = load_local_rows(assetclass, symbols)
    for sym, snap in snapshots.items():
        rec = rec_info.get(sym, {})
        snap.upside_pct = rec.get("upside_pct")
        snap.volume_trend = snap.volume_trend or rec.get("volume_trend")
        snap.extras["rank"] = rec.get("rank")

        local = local_rows.get(sym) or {}
        if snap.atr14 is None:
            snap.atr14 = _to_float(local.get("atr14"))
        if snap.rsi14 is None:
            snap.rsi14 = _to_float(local.get("rsi14"))
        if snap.sma20 is None:
            snap.sma20 = _to_float(local.get("sma20"))
        if snap.sma50 is None:
            snap.sma50 = _to_float(local.get("sma50"))
        if snap.sma200 is None:
            snap.sma200 = _to_float(local.get("sma200"))


def load_dataset(
    assetclass: str = "stocks", symbols: Optional[List[str]] = None, base_url: Optional[str] = None, offline: bool = False
) -> Dict[str, TickerSnapshot]:
    """Build ticker snapshots using the bulk-recommendation API, with offline fallback to local data."""
    base = base_url or "http://localhost:5000/ai/bulk-recommendation"
    payload: Dict[str, object] = {}
    snapshots: Dict[str, TickerSnapshot] = {}
    rec_info: Dict[str, Dict[str, object]] = {}

    if not offline:
        try:
            payload = fetch_ai_payload(base, assetclass, symbols or [])
            snapshots = parse_prompt_metrics(payload.get("prompt", ""))
            rec_info = parse_recommendations(payload)
            merge_snapshots(snapshots, rec_info, assetclass)
        except Exception:
            if not snapshots:
                # Fallback to local data if API is unreachable
                offline = True

    if offline:
        items = list_latest_indicator_rows(assetclass=assetclass, symbols=symbols)
        if assetclass == "etf":
            filtered_items = []
            for item in items:
                row = item.get("row") if isinstance(item, dict) else {}
                close = _to_float((row or {}).get("close"))
                sma50 = _to_float((row or {}).get("sma50"))
                sma200 = _to_float((row or {}).get("sma200"))
                if close is None or sma50 is None or sma200 is None:
                    continue
                if close <= sma50 or close <= sma200:
                    continue
                filtered_items.append(item)
            items = filtered_items
        snapshots = build_snapshots_from_items(items, assetclass)

    spy_upside = rec_info.get("SPY", {}).get("upside_pct")
    snapshots["SPY"] = load_spy_snapshot(spy_upside)
    return snapshots


def factor_scores(s: TickerSnapshot) -> Dict[str, float]:
    """Compute factor-level scores with neutral defaults for missing data."""
    momentum = 0.5
    if s.close is not None and s.sma200 is not None:
        above_200 = s.close > s.sma200
        above_50 = s.close > (s.sma50 or -math.inf)
        above_20 = s.close > (s.sma20 or -math.inf)
        if above_20 and above_50 and above_200:
            momentum = 1.0
        elif above_50 and above_200:
            momentum = 0.7
        elif above_200:
            momentum = 0.4
        else:
            momentum = 0.0

    rsi_score = 0.5
    if s.rsi14 is not None:
        if 55 <= s.rsi14 < 70:
            rsi_score = 1.0
        elif 50 <= s.rsi14 < 55 or 70 <= s.rsi14 < 75:
            rsi_score = 0.7
        elif 40 <= s.rsi14 < 50 or 75 <= s.rsi14 <= 80:
            rsi_score = 0.5
        else:
            rsi_score = 0.0

    macd_score = 0.5
    if s.macd is not None or s.macd_hist is not None:
        macd_score = 0.0
        if (s.macd or 0) > 0 and (s.macd_hist or 0) > 0:
            macd_score = 1.0
        elif (s.macd or 0) > 0 or (s.macd_hist or 0) > 0:
            macd_score = 0.5

    vol_trend = s.volume_trend if s.volume_trend is not None else 0.8
    volume_score = 1.0 if vol_trend > 1 else 0.5 if vol_trend > 0.8 else 0.0

    vol_control = 0.5
    atr_pct = s.atr_pct
    if atr_pct is not None:
        if atr_pct < 1.5:
            vol_control = 1.0
        elif atr_pct < 3:
            vol_control = 0.5
        else:
            vol_control = 0.0

    upside_score = 0.5
    if s.upside_pct is not None:
        if s.upside_pct > 20:
            upside_score = 1.3
        elif s.upside_pct > 12:
            upside_score = 1.1
        elif s.upside_pct > 7:
            upside_score = 0.9
        elif s.upside_pct > 3:
            upside_score = 0.7
        elif s.upside_pct > 0:
            upside_score = 0.5
        else:
            upside_score = 0.0

    return {
        "momentum": momentum,
        "rsi": rsi_score,
        "macd": macd_score,
        "volume": volume_score,
        "volatility": vol_control,
        "upside": upside_score,
    }


def score_ticker(s: TickerSnapshot, spy: Optional[TickerSnapshot]) -> Dict[str, object]:
    """Aggregate weighted score and reasons for a ticker."""
    factors = factor_scores(s)
    score = sum(factors[name] * WEIGHTS[name] for name in WEIGHTS)

    boost_applied = False
    if spy and spy.symbol != s.symbol:
        if (s.rsi14 or 0) > (spy.rsi14 or 0) and (s.volume_trend or 0) > (spy.volume_trend or 0):
            score += BOOST_RELATIVE_TO_SPY
            boost_applied = True
    score = min(score, 1.0)

    reasons: List[str] = []
    if factors["momentum"] >= 1.0:
        reasons.append("Above SMA20/50/200")
    elif factors["momentum"] >= 0.7:
        reasons.append("Above SMA50/200")
    elif factors["momentum"] >= 0.4:
        reasons.append("Above SMA200")
    if factors["macd"] >= 1.0:
        reasons.append("MACD>0 with rising hist")
    elif factors["macd"] >= 0.5:
        reasons.append("MACD leaning bullish")
    if factors["rsi"] >= 1.0:
        reasons.append("RSI in bullish zone")
    if factors["volume"] >= 1.0:
        reasons.append("Volume trend rising")
    if factors["volatility"] >= 1.0:
        reasons.append("ATR% <1.5")
    elif factors["volatility"] == 0.0:
        reasons.append("ATR% elevated")
    if s.upside_pct is not None:
        reasons.append(f"Upside {s.upside_pct:.1f}%")
    if boost_applied:
        reasons.append("Outperforming SPY on RSI+vol")

    return {
        "symbol": s.symbol,
        "score": round(score, 3),
        "factors": factors,
        "atr_pct": s.atr_pct,
        "upside_pct": s.upside_pct,
        "volume_trend": s.volume_trend,
        "close": s.close,
        "extras": s.extras,
        "boosted": boost_applied,
        "swing_setup": build_swing_setup(s) if score >= 0.8 else None,
        "reasons": reasons,
    }


def build_swing_setup(s: TickerSnapshot) -> Optional[Dict[str, object]]:
    """Simple swing plan anchored to ATR for risk control."""
    if s.close is None:
        return None
    atr = s.atr14 or (s.close * 0.01)
    entry_low = s.close - 0.2 * atr
    entry_high = s.close + 0.2 * atr
    stop = s.close - 1.5 * atr
    target = s.close + 2.5 * atr
    mid_entry = (entry_low + entry_high) / 2
    rr = None
    if stop != mid_entry:
        rr = round((target - mid_entry) / (mid_entry - stop), 2)
    return {
        "entry": (round(entry_low, 2), round(entry_high, 2)),
        "stop": round(stop, 2),
        "target": round(target, 2),
        "rr": rr,
    }


def rank_tickers(
    assetclass: str = "stocks", symbols: Optional[List[str]] = None, base_url: Optional[str] = None, offline: bool = False
) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    """Produce full rankings and filtered top picks."""
    snapshots = load_dataset(assetclass=assetclass, symbols=symbols, base_url=base_url, offline=offline)
    spy = snapshots.get("SPY")
    scored = [score_ticker(snap, spy) for snap in snapshots.values()]
    scored.sort(
        key=lambda r: (
            -(r.get("score") or 0),
            -(r.get("upside_pct") or 0),
            r.get("atr_pct") if r.get("atr_pct") is not None else math.inf,
        )
    )
    picks = [row for row in scored if (row.get("score") or 0) > THRESHOLD][:MAX_PICKS]
    return scored, picks


def _format_row(row: Dict[str, object]) -> str:
    score = row.get("score")
    upside = row.get("upside_pct")
    atr_pct = row.get("atr_pct")
    parts = [
        f"{row.get('symbol'):<4}",
        f"Score {score:.2f}" if score is not None else "Score ?",
        f"Upside {upside:.1f}%" if upside is not None else "Upside n/a",
    ]
    if atr_pct is not None:
        parts.append(f"ATR% {atr_pct:.2f}")
    if row.get("volume_trend") is not None:
        parts.append(f"VolTrend {row['volume_trend']:.2f}x")
    return " | ".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description="Rank tickers using swing-style rules and bulk AI data.")
    parser.add_argument("--assetclass", default="stocks", choices=["stocks", "etf"], help="Asset class to score")
    parser.add_argument("--symbols", default="", help="Comma-separated symbols to restrict scoring")
    parser.add_argument("--base-url", default="http://localhost:5000/ai/bulk-recommendation", help="Bulk recommendation API base URL")
    parser.add_argument("--offline", action="store_true", help="Skip API call and use local data files only")
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()] if args.symbols else None

    scored, picks = rank_tickers(assetclass=args.assetclass, symbols=symbols, base_url=args.base_url, offline=args.offline)
    print("Top picks (score > 0.6):")
    for idx, row in enumerate(picks, start=1):
        print(f"{idx}. {_format_row(row)} :: {', '.join(row.get('reasons') or [])}")
        setup = row.get("swing_setup")
        if setup:
            entry = setup.get("entry") or ("?", "?")
            print(
                f"   Setup: entry {entry[0]} - {entry[1]}, stop {setup.get('stop')}, "
                f"target {setup.get('target')} (R:R {setup.get('rr')})"
            )

    print("\nFull ranking:")
    for row in scored:
        print(f"- {_format_row(row)}")


if __name__ == "__main__":
    main()
