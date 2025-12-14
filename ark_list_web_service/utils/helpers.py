from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional


def sanitize(obj):
    """Recursively replace non-finite floats (NaN/inf) with None for JSON safety."""
    if isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize(v) for v in obj]
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    return obj


def parse_date(value: str) -> date:
    """Parse YYYY-MM-DD strings into date objects."""
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:  # noqa: B904
        raise ValueError("Invalid date format; expected YYYY-MM-DD") from exc


def normalize_symbol(symbol: str) -> str:
    """Normalize ticker symbols (upper-case and strip commas/whitespace/encoding)."""
    if not symbol:
        return ""
    sym = str(symbol).replace("%20", " ").replace(",", " ").strip().split()
    return sym[0].upper() if sym else ""


def asset_data_dir(assetclass: str, data_dir: Path) -> Path:
    """Return the asset-class-specific data directory."""
    asset = (assetclass or "stocks").lower()
    if asset == "etf":
        return data_dir / "etf"
    if asset == "holdings":
        return data_dir / "holdings"
    return data_dir / "stocks"


def parse_symbol_list(raw: Optional[str]) -> List[str]:
    """Parse comma/space separated tickers into a normalized list."""
    if not raw:
        return []
    symbols = []
    for part in raw.replace(";", ",").replace("|", ",").split(","):
        token = part.strip().upper()
        if token:
            symbols.append(token)
    return symbols


def is_fresh(path: Path, ttl_hours: int = 3) -> bool:
    """Check if a file is newer than a TTL window."""
    if not path.exists():
        return False
    return datetime.now() - datetime.fromtimestamp(path.stat().st_mtime) < timedelta(hours=ttl_hours)


def compute_metrics_from_points(points: List[Dict[str, object]]) -> Dict[str, object]:
    """Compute basic metrics (last close, MA21) from OHLC rows."""
    closes = [float(item["close"]) for item in points if "close" in item]
    if not closes:
        return {}
    last_close = closes[-1]
    ma_window = 21
    ma_vals: List[float] = []
    acc = 0.0
    for idx, val in enumerate(closes):
        acc += val
        if idx >= ma_window:
            acc -= closes[idx - ma_window]
        if idx >= ma_window - 1:
            ma_vals.append(acc / ma_window)
    ma21 = ma_vals[-1] if ma_vals else None
    return {
        "last_close": last_close,
        "ma21": ma21,
    }


def format_simple_plan(symbol: str, metrics: Dict[str, object]) -> str:
    """Build a simple trade plan string from computed metrics."""
    last_close = metrics.get("last_close")
    ma_val = metrics.get("ma21")
    if not isinstance(last_close, (int, float)):
        return f"No data to build a plan for {symbol.upper()}."
    buy = last_close * 0.98
    target = last_close * 1.05
    stop = last_close * 0.94
    note = f"MA21 {ma_val:.2f}" if isinstance(ma_val, (int, float)) else "based on latest close"
    return f"Buy: {buy:.2f} | Target: {target:.2f} | Stop: {stop:.2f} | Note: {note}"
