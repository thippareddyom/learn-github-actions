from __future__ import annotations

import json
import math
from typing import Dict, List

from utils.paths import PORTFOLIO_FILE, TRADE_LOG_FILE, TRADES_DIR
from utils.helpers import normalize_symbol, sanitize
from utils.data import collect_portfolio_data


def load_portfolio(default_cash: float = 100000.0) -> Dict[str, object]:
    """Load the model portfolio JSON, creating defaults if missing."""
    TRADES_DIR.mkdir(parents=True, exist_ok=True)
    if not PORTFOLIO_FILE.exists():
        default = {"cash_balance": default_cash, "open_positions": [], "closed_trades": []}
        PORTFOLIO_FILE.write_text(json.dumps(default, indent=2))
        return default
    try:
        return json.loads(PORTFOLIO_FILE.read_text())
    except Exception:
        return {"cash_balance": default_cash, "open_positions": [], "closed_trades": []}


def save_portfolio(payload: Dict[str, object]) -> None:
    """Persist the portfolio JSON."""
    TRADES_DIR.mkdir(parents=True, exist_ok=True)
    PORTFOLIO_FILE.write_text(json.dumps(payload, indent=2))


def append_trade_log(entry: Dict[str, object]) -> None:
    """Append a trade entry to trade_log.json with sanitization."""
    TRADES_DIR.mkdir(parents=True, exist_ok=True)
    try:
        if TRADE_LOG_FILE.exists():
            log = json.loads(TRADE_LOG_FILE.read_text())
        else:
            log = []
    except Exception:
        log = []
    log.append(sanitize(entry))
    TRADE_LOG_FILE.write_text(json.dumps(log, indent=2))


def portfolio_equity(portfolio: Dict[str, object]) -> float:
    """Compute total equity = cash + marked value of open positions."""
    cash = float(portfolio.get("cash_balance", 0) or 0)
    open_positions = portfolio.get("open_positions") or []
    market_val = 0.0
    for pos in open_positions:
        try:
            shares = float(pos.get("shares") or 0)
            mark = float(pos.get("mark_price") if pos.get("mark_price") is not None else pos.get("entry_price"))
            market_val += shares * mark
        except Exception:
            continue
    return cash + market_val


def refresh_mark_prices(portfolio: Dict[str, object], assetclass: str = "stocks") -> Dict[str, object]:
    """Update open position mark prices using latest closes from local data."""
    if not portfolio:
        return portfolio
    open_positions: List[Dict[str, object]] = portfolio.get("open_positions") or []
    symbols = [normalize_symbol(p.get("symbol")) for p in open_positions if normalize_symbol(p.get("symbol"))]
    if not symbols:
        return portfolio

    latest_data = collect_portfolio_data(assetclass=assetclass, symbols=symbols)
    latest_map = {}
    for row in latest_data:
        sym = normalize_symbol(row.get("ticker") or row.get("symbol"))
        latest = row.get("latest") if isinstance(row, dict) else None
        latest_map[sym] = latest if isinstance(latest, dict) else {}

    updated_positions: List[Dict[str, object]] = []
    for pos in open_positions:
        sym = normalize_symbol(pos.get("symbol"))
        latest = latest_map.get(sym, {})
        close_val = latest.get("close") if isinstance(latest, dict) else None
        mark_price = pos.get("mark_price") or pos.get("entry_price")
        try:
            if close_val is not None and math.isfinite(float(close_val)):
                mark_price = float(close_val)
        except Exception:
            pass
        pos["mark_price"] = mark_price
        updated_positions.append(pos)

    portfolio["open_positions"] = updated_positions
    return portfolio
