from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from flask import jsonify, request

from utils.helpers import normalize_symbol
from utils.portfolio import append_trade_log, load_portfolio, portfolio_equity, refresh_mark_prices, save_portfolio
from utils.data import collect_portfolio_data, load_or_fetch_ticker_history
from utils.ai_helper import deterministic_portfolio_rank


def _is_options_request() -> bool:
    return getattr(request, "method", "GET") == "OPTIONS"


def get_portfolio():
    if _is_options_request():
        return "", 204
    portfolio = load_portfolio()
    portfolio = refresh_mark_prices(portfolio, assetclass="stocks")
    save_portfolio(portfolio)
    return jsonify(portfolio)


def portfolio_buy():
    if _is_options_request():
        return "", 204
    try:
        payload = request.get_json(force=True, silent=True) or {}
        symbol = normalize_symbol(payload.get("symbol"))
        position_size = payload.get("position_size", "1/2")
        entry_price = payload.get("entry_price")
        mark_price = payload.get("mark_price") or entry_price
        assetclass = (payload.get("assetclass") or "stocks").lower()
        now = datetime.now().astimezone()
        if not symbol:
            return jsonify({"error": "invalid_symbol", "message": "Symbol is required"}), 400
        # Price fallback to latest close if not provided
        if entry_price is None:
            data = collect_portfolio_data(assetclass=assetclass, symbols=[symbol])
            if not data:
                return jsonify({"error": "invalid_price", "message": "No price available for that symbol"}), 400
            latest = data[0].get("latest") or {}
            entry_price = latest.get("close") or latest.get("price") or latest.get("regularMarketPrice")
            mark_price = mark_price or entry_price
        try:
            entry_val = float(entry_price)
            mark_val = float(mark_price) if mark_price is not None else entry_val
        except Exception:
            return jsonify({"error": "invalid_price", "message": "Entry price must be a number"}), 400
        if entry_val <= 0:
            return jsonify({"error": "invalid_price", "message": "Entry price must be positive"}), 400
        size_map = {"1": 0.1, "1/2": 0.05, "1/4": 0.025, "auto": 0.1}
        fraction = size_map.get(str(position_size), 0.1)
        portfolio = load_portfolio()
        cash = float(portfolio.get("cash_balance", 0) or 0)
        equity = portfolio_equity(portfolio)
        allocation = equity * fraction
        if allocation <= 0 or allocation > cash:
            return jsonify({"error": "insufficient_cash", "message": "Not enough cash to fund the position size allocation"}), 400
        shares = allocation / entry_val
        added_at = now.isoformat()
        position = {
            "id": f"{symbol}-{int(now.timestamp()*1000)}",
            "symbol": symbol,
            "size_label": position_size,
            "shares": shares,
            "entry_price": entry_val,
            "mark_price": mark_val,
            "added_at": added_at,
            "assetclass": assetclass,
        }
        open_positions = portfolio.get("open_positions") or []
        open_positions.append(position)
        portfolio["open_positions"] = open_positions
        portfolio["cash_balance"] = cash - allocation
        save_portfolio(portfolio)
        append_trade_log(
            {
                "id": position["id"],
                "symbol": symbol,
                "side": "buy",
                "shares": shares,
                "price": entry_val,
                "timestamp": added_at,
                "position_size": position_size,
            }
        )
        return jsonify(portfolio)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": "server_error", "message": f"Buy failed: {exc}"}), 500


def portfolio_sell():
    if _is_options_request():
        return "", 204
    try:
        payload = request.get_json(force=True, silent=True) or {}
        symbol = normalize_symbol(payload.get("symbol"))
        exit_price = payload.get("exit_price")
        assetclass = (payload.get("assetclass") or "stocks").lower()
        now = datetime.now().astimezone()
        if not symbol:
            return jsonify({"error": "invalid_symbol", "message": "Symbol is required"}), 400
        portfolio = load_portfolio()
        open_positions = portfolio.get("open_positions") or []
        position = next((p for p in open_positions if p.get("symbol") == symbol), None)
        if not position:
            return jsonify({"error": "not_found", "message": "No open position for that symbol"}), 404
        if exit_price is None:
            try:
                data = collect_portfolio_data(assetclass=assetclass, symbols=[symbol])
                latest = data[0].get("latest") if data else None
                exit_price = latest.get("close") or latest.get("price") or latest.get("regularMarketPrice")
            except Exception:
                exit_price = None
        try:
            exit_val = float(exit_price)
        except Exception:
            return jsonify({"error": "invalid_price", "message": "Exit price must be a number"}), 400
        if exit_val <= 0:
            return jsonify({"error": "invalid_price", "message": "Exit price must be positive"}), 400
        shares = float(position.get("shares") or 0)
        entry_price = float(position.get("entry_price") or 0)
        proceeds = shares * exit_val
        cost = shares * entry_price
        gain_pct = ((proceeds - cost) / cost) * 100 if cost else 0
        exit_at = now.isoformat()
        closed = {
            "symbol": symbol,
            "entry": position.get("added_at"),
            "exit": exit_at,
            "entry_price": entry_price,
            "exit_price": exit_val,
            "shares": shares,
            "trade_balance": proceeds,
            "gain_pct": gain_pct,
        }
        portfolio["open_positions"] = [p for p in open_positions if p.get("id") != position.get("id")]
        closed_trades = portfolio.get("closed_trades") or []
        closed_trades.insert(0, closed)
        portfolio["closed_trades"] = closed_trades
        portfolio["cash_balance"] = float(portfolio.get("cash_balance", 0) or 0) + proceeds
        save_portfolio(portfolio)
        append_trade_log(
            {
                "id": f"{symbol}-sell-{int(now.timestamp()*1000)}",
                "symbol": symbol,
                "side": "sell",
                "shares": shares,
                "price": exit_val,
                "timestamp": exit_at,
            }
        )
        return jsonify(portfolio)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": "server_error", "message": f"Sell failed: {exc}"}), 500


__all__ = ["get_portfolio", "portfolio_buy", "portfolio_sell"]


def rebalance_portfolio():
    """
    Admin route to align open positions with Stock portfolio picks (deterministic selection).

    Logic:
    - Fetch deterministic portfolio rows (stocks asset class).
    - Sell any open positions not in the target list at latest close.
    - Buy any missing target tickers using equal allocation of remaining cash (per new ticker).
    """
    if _is_options_request():
        return "", 204
    try:
        portfolio = load_portfolio()
        cash = float(portfolio.get("cash_balance", 0) or 0)
        open_positions: List[Dict[str, object]] = portfolio.get("open_positions") or []

        # Build target list from deterministic selection
        data = collect_portfolio_data(assetclass="stocks", symbols=None)
        _, target_rows, _ = deterministic_portfolio_rank(data)
        target_tickers = [row.get("ticker") for row in target_rows if row.get("ticker")]
        target_set = set(target_tickers)

        now = datetime.now().astimezone()

        # Sell positions not in target
        remaining_positions = []
        for pos in open_positions:
            sym = normalize_symbol(pos.get("symbol"))
            if not sym or sym in target_set:
                remaining_positions.append(pos)
                continue
            try:
                hist = load_or_fetch_ticker_history(sym, assetclass="stocks")
                latest = hist.get("latest") if isinstance(hist, dict) else None
                exit_price = float(latest.get("close")) if latest and latest.get("close") is not None else float(
                    pos.get("mark_price") or pos.get("entry_price")
                )
            except Exception:
                exit_price = float(pos.get("mark_price") or pos.get("entry_price") or 0)
            shares = float(pos.get("shares") or 0)
            proceeds = shares * exit_price
            cash += proceeds
            closed = {
                "symbol": sym,
                "entry": pos.get("added_at"),
                "exit": now.isoformat(),
                "entry_price": float(pos.get("entry_price") or 0),
                "exit_price": exit_price,
                "shares": shares,
                "trade_balance": proceeds,
                "gain_pct": ((proceeds - (shares * float(pos.get("entry_price") or 0))) / (shares * float(pos.get("entry_price") or 0)))
                * 100
                if shares and pos.get("entry_price")
                else 0,
            }
            closed_trades = portfolio.get("closed_trades") or []
            closed_trades.insert(0, closed)
            portfolio["closed_trades"] = closed_trades
            append_trade_log(
                {
                    "id": f"{sym}-sell-{int(now.timestamp()*1000)}",
                    "symbol": sym,
                    "side": "sell",
                    "shares": shares,
                    "price": exit_price,
                    "timestamp": now.isoformat(),
                }
            )

        open_positions = remaining_positions

        # Buy missing targets
        owned = {normalize_symbol(p.get("symbol")) for p in open_positions if p.get("symbol")}
        to_buy = [sym for sym in target_tickers if normalize_symbol(sym) not in owned]
        per_allocation = cash / len(to_buy) if to_buy else 0
        for sym in to_buy:
            try:
                hist = load_or_fetch_ticker_history(sym, assetclass="stocks")
                latest = hist.get("latest") if isinstance(hist, dict) else None
                entry_price = float(latest.get("close")) if latest and latest.get("close") is not None else None
            except Exception:
                entry_price = None
            if entry_price is None or entry_price <= 0:
                continue
            alloc = min(per_allocation, cash)
            if alloc <= 0:
                continue
            shares = alloc / entry_price
            pos = {
                "id": f"{sym}-{int(now.timestamp()*1000)}",
                "symbol": sym,
                "size_label": "auto",
                "shares": shares,
                "entry_price": entry_price,
                "mark_price": entry_price,
                "added_at": now.isoformat(),
            }
            open_positions.append(pos)
            cash -= alloc
            append_trade_log(
                {
                    "id": pos["id"],
                    "symbol": sym,
                    "side": "buy",
                    "shares": shares,
                    "price": entry_price,
                    "timestamp": now.isoformat(),
                    "position_size": "auto",
                }
            )

        portfolio["open_positions"] = open_positions
        portfolio["cash_balance"] = cash
        save_portfolio(portfolio)
        return jsonify({"status": "ok", "open_positions": open_positions, "cash_balance": cash})
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": "server_error", "message": f"Rebalance failed: {exc}"}), 500


__all__.append("rebalance_portfolio")
