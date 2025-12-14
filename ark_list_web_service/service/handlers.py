from __future__ import annotations

import json
import os
from datetime import date, datetime
import math
from typing import Dict, List, Optional, Tuple

from flask import abort, jsonify, request

from service.classes.recommender import LocalRecommender, build_allocation_prompt, score_and_allocate
from utils.ai_helper import build_bulk_prompt, deterministic_bulk_summary
from utils.data import (
    download_fund_holdings,
    collect_portfolio_data,
    known_symbols,
    list_latest_indicator_rows,
    load_funds,
    load_holdings,
    load_or_fetch_ticker_history,
    tickers_from_holdings,
)
from utils.helpers import asset_data_dir, normalize_symbol, parse_date, parse_symbol_list, sanitize
from utils.paths import DATA_DIR, HOLDINGS_DIR
from utils.yahoo_data_loader import download_with_indicators

try:  # optional local LLM
    from llama_cpp import Llama  # type: ignore
except Exception:  # pragma: no cover
    Llama = None

recommender = LocalRecommender()
FUNDS: List[Dict[str, str]] = load_funds()
FUND_LOOKUP: Dict[str, Dict[str, str]] = {item["symbol"].upper(): item for item in FUNDS}
LLM_ENABLED = os.environ.get("ENABLE_LOCAL_LLM") == "1"


def _is_options_request() -> bool:
    return getattr(request, "method", "GET") == "OPTIONS"


def add_cors_headers(response):
    # Allow local dev frontend by default; fall back to wildcard
    origin = request.headers.get("Origin", "*")
    response.headers["Access-Control-Allow-Origin"] = origin or "*"
    response.headers["Vary"] = "Origin"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response


def health():
    return jsonify({"status": "ok"})


def list_funds():
    if _is_options_request():
        return "", 204
    return jsonify(FUNDS)


def get_fund(symbol: str):
    if _is_options_request():
        return "", 204
    item = FUND_LOOKUP.get(symbol.upper())
    if not item:
        abort(404, description="Fund not found")
    return jsonify(item)


def get_fund_holdings(symbol: str):
    if _is_options_request():
        return "", 204

    day = request.args.get("day")
    if day:
        try:
            parse_date(day)
        except ValueError as exc:
            abort(400, description=str(exc))

    holdings = load_holdings(symbol, day)
    if not holdings:
        return (
            jsonify(
                {
                    "symbol": symbol.upper(),
                    "date": None,
                    "count": 0,
                    "rows": [],
                    "footnote": "",
                }
            ),
        )

    return jsonify(holdings)


def get_ticker_history(symbol: str):
    if _is_options_request():
        return "", 204

    try:
        assetclass = request.args.get("assetclass") or "stocks"
        history = load_or_fetch_ticker_history(symbol, assetclass=assetclass)
    except Exception as exc:  # noqa: BLE001
        abort(500, description=f"Unexpected error: {exc}")

    if isinstance(history, dict) and "rows" in history:
        history.setdefault("points", history.get("rows"))
    return jsonify(history)


def get_ticker_recommendation(symbol: str):
    if _is_options_request():
        return "", 204

    req_asset = request.args.get("assetclass")
    assetclass = (
        req_asset.lower()
        if req_asset
        else ("etf" if symbol.upper() in FUND_LOOKUP else "stocks")
    )
    try:
        history = load_or_fetch_ticker_history(symbol, assetclass=assetclass)
        points = history.get("rows") if isinstance(history, dict) else None
    except FileNotFoundError as exc:
        abort(404, description=str(exc))
    except Exception as exc:  # noqa: BLE001
        abort(500, description=f"Failed to generate recommendation: {exc}")

    if not isinstance(points, list) or not points:
        return jsonify({"symbol": symbol.upper(), "recommendation": "No data to build a plan."})

    from utils.helpers import compute_metrics_from_points, format_simple_plan

    metrics = compute_metrics_from_points(points)
    metrics["assetclass"] = assetclass

    # Prefer local LLM if available, but fail soft to a deterministic plan
    if (not LLM_ENABLED) or os.environ.get("DISABLE_LOCAL_LLM") or Llama is None:
        text = format_simple_plan(symbol, metrics)
        return jsonify({"symbol": symbol.upper(), "recommendation": text})

    try:
        recommender.ensure_model()
        text = recommender.generate(symbol, metrics)
    except Exception:
        text = format_simple_plan(symbol, metrics)

    return jsonify({"symbol": symbol.upper(), "recommendation": text})


def download_holdings():
    if _is_options_request():
        return "", 204

    symbol = (
        (request.args.get("symbol") or request.args.get("sym") or request.args.get("ticker") or "")
        if request.args
        else ""
    )
    if not symbol and request.is_json:
        payload = request.get_json(silent=True) or {}
        symbol = payload.get("symbol") or payload.get("sym") or payload.get("ticker") or ""
    symbol = (symbol or "").strip()
    if not symbol:
        abort(400, description="symbol is required (use ?symbol=ARKF or JSON {symbol:\"ARKF\"})")

    try:
        path = download_fund_holdings(symbol)
        try:
            saved = json.loads(Path(path).read_text())
        except Exception:
            saved = None
        return jsonify(
            {
                "symbol": symbol.upper(),
                "status": "ok",
                "path": str(path),
                "count": (saved or {}).get("count"),
                "as_of": (saved or {}).get("as_of"),
            }
        )
    except Exception as exc:  # noqa: BLE001
        # Return a JSON error so the client can see the cause (e.g., network block, bad symbol)
        return (
            jsonify(
                {
                    "error": "download_failed",
                    "message": f"Failed to download holdings for {symbol}: {exc}",
                }
            ),
            500,
        )


def get_bulk_recommendation():
    if _is_options_request():
        return "", 204

    assetclass = (request.args.get("assetclass") or "stocks").lower()
    symbols = parse_symbol_list(request.args.get("symbols") or request.args.get("tickers"))
    items = list_latest_indicator_rows(assetclass=assetclass, symbols=symbols)

    # Enforce ETF uptrend filter (price must be above both SMA50 and SMA200)
    if assetclass == "etf":
        def _num(val):
            try:
                f = float(val)
                return f if math.isfinite(f) else None
            except Exception:
                return None

        filtered = []
        for item in items:
            row = item.get("row") if isinstance(item, dict) else {}
            close = _num((row or {}).get("close"))
            sma50 = _num((row or {}).get("sma50"))
            sma200 = _num((row or {}).get("sma200"))
            if close is None or sma50 is None or sma200 is None:
                continue
            if close <= sma50 or close <= sma200:
                continue
            filtered.append(item)
        items = filtered

    if not items:
        msg = "No tickers with data found" if not symbols else f"No data found for symbols: {', '.join(symbols)}"
        return jsonify({"error": "not_found", "message": msg}), 404

    prompt = build_bulk_prompt(items, assetclass=assetclass)

    if (not LLM_ENABLED) or os.environ.get("DISABLE_LOCAL_LLM") or Llama is None:
        summary = deterministic_bulk_summary(items)
        return jsonify({"tickers": [i["symbol"] for i in items], "recommendation": summary, "prompt": prompt})

    text = ""
    rows: List[Dict[str, str]] = []
    try:
        recommender.ensure_model()
        if hasattr(recommender.model, "create_completion"):
            out = recommender.model(
                prompt,
                max_tokens=512,
                temperature=0.6,
                top_p=0.9,
                repeat_penalty=1.1,
                echo=False,
            )
            text = out["choices"][0]["text"].strip()
        elif hasattr(recommender.model, "create_chat_completion"):
            out = recommender.model.create_chat_completion(
                messages=[
                    {"role": "system", "content": "You are a concise swing-trade helper."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=512,
                temperature=0.6,
                top_p=0.9,
                repeat_penalty=1.1,
            )
            text = out["choices"][0]["message"]["content"].strip()
        else:
            text, rows = deterministic_bulk_summary(items)
    except Exception:
        text, rows = deterministic_bulk_summary(items)

    bad = text.lower()
    ticker_hits = [sym for sym in [i["symbol"] for i in items] if sym in text]
    if (
        not text
        or "screenshot" in bad
        or len(text) < 50
        or not ticker_hits
    ):
        text, rows = deterministic_bulk_summary(items)

    return jsonify({"tickers": [i["symbol"] for i in items], "recommendation": text, "prompt": prompt, "rows": rows})


def get_ai_portfolio():
    if _is_options_request():
        return "", 204

    assetclass = (request.args.get("assetclass") or "stocks").lower()
    symbols = parse_symbol_list(request.args.get("symbols") or request.args.get("tickers"))
    data = collect_portfolio_data(assetclass=assetclass, symbols=symbols)
    if not data:
        msg = "No portfolio data available" if not symbols else f"No data found for symbols: {', '.join(symbols)}"
        return jsonify({"error": "not_found", "message": msg}), 404
    data = sanitize(data)

    payloads = []
    for row in data:
        payloads.append(
            {
                "ticker": row.get("ticker") or row.get("symbol") or "",
                "fundamentals": row.get("fundamentals") or {},
                "modules": row.get("modules") or {},
                "reason": row.get("Reason") or row.get("reason"),
            }
        )
    fundamentals_lookup = {p["ticker"]: p.get("fundamentals") or {} for p in payloads if p.get("ticker")}
    modules_lookup = {p["ticker"]: p.get("modules") or {} for p in payloads if p.get("ticker")}
    all_tickers = [p["ticker"] for p in payloads if p.get("ticker")]
    scored = score_and_allocate(payloads, top_n=10)
    prompt = build_allocation_prompt(payloads)

    reason_lookup = {p["ticker"]: p.get("reason") for p in payloads if p.get("ticker")}

    def _num(val):
        try:
            f = float(val)
            return f if f == f else None  # NaN guard
        except Exception:
            return None

    def _buy_pct(mods: dict) -> float:
        trend_rows = []
        if isinstance(mods, dict):
            trend_rows = (mods.get("recommendationTrend") or {}).get("trend") or []
        if not isinstance(trend_rows, list) or not trend_rows:
            return 0.0
        first = trend_rows[0] or {}
        total = sum((first.get(k) or 0) for k in ("strongBuy", "buy", "hold", "sell", "strongSell"))
        buy_sum = (first.get("strongBuy") or 0) + (first.get("buy") or 0)
        return float(buy_sum / total * 100) if total else 0.0

    def _fallback_reason(sym: str, breakdown):
        fundamentals = fundamentals_lookup.get(sym) or {}
        modules = modules_lookup.get(sym) or {}
        parts = []
        ups = _num(getattr(breakdown, "upside_pct", None))
        rating = _num(fundamentals.get("buy_rating_pct")) or _buy_pct(modules)
        vol = _num(fundamentals.get("volume_trend"))
        rsi = _num(fundamentals.get("rsi14"))
        if ups is not None:
            parts.append(f"Upside {ups:.1f}%")
        if rating is not None and rating > 0:
            parts.append(f"Rating {rating:.0f}%")
        if vol is not None:
            parts.append(f"Vol {vol:.2f}x")
        if rsi is not None:
            parts.append(f"RSI {rsi:.0f}")
        return " | ".join(parts)

    def _to_row(idx, s):
        b = s.breakdown
        reason = reason_lookup.get(s.ticker) or _fallback_reason(s.ticker, b) or (
            f"score {s.score:.1f}; up {b.upside_points:.1f}; "
            f"earn {b.earnings_points:.1f}; analyst {b.analyst_points:.1f}; tech {b.technical_points:.1f}"
        )
        return {
            "rank": idx,
            "ticker": s.ticker,
            "upside": s.upside_pct,
            "allocation": s.allocation_pct,
            "beta": s.beta,
            "sector": s.sector,
            "forwardPE": s.forward_pe,
            "reason": reason,
        }

    rows = [_to_row(idx + 1, s) for idx, s in enumerate(scored)]
    tickers = [s.ticker for s in scored]

    text = ""
    try:
        if (not LLM_ENABLED) or os.environ.get("DISABLE_LOCAL_LLM") or Llama is None:
            raise RuntimeError("local model disabled")
        recommender.ensure_model()
        if hasattr(recommender.model, "create_chat_completion"):
            out = recommender.model.create_chat_completion(
                messages=[
                    {"role": "system", "content": "You are a concise investment assistant."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=420,
                temperature=0.5,
                top_p=0.9,
                repeat_penalty=1.05,
            )
            text = out["choices"][0]["message"]["content"].strip()
        elif hasattr(recommender.model, "create_completion"):
            out = recommender.model(
                prompt,
                max_tokens=420,
                temperature=0.5,
                top_p=0.9,
                repeat_penalty=1.05,
                echo=False,
            )
            text = out["choices"][0]["text"].strip()
        else:
            raise RuntimeError("model missing completion API")
    except Exception:
        # Fall back to deterministic table
        return jsonify(
            {"recommendation": text or prompt, "rows": rows, "prompt": prompt, "tickers": tickers, "tickers_all": all_tickers}
        )

    return jsonify({"recommendation": text or prompt, "rows": rows, "prompt": prompt, "tickers": tickers, "tickers_all": all_tickers})


def regenerate_data():
    if _is_options_request():
        return "", 204

    assetclass = (request.args.get("assetclass") or "stocks").lower()
    symbols: List[str] = []
    symbols_from_files = known_symbols(assetclass=assetclass)
    holdings_syms = tickers_from_holdings(assetclass=assetclass)
    symbols = sorted(set(symbols_from_files).union(holdings_syms))
    if not symbols:
        return jsonify({"error": "not_found", "message": "No symbols found to regenerate"}), 404

    results = []
    today = date.today()
    for sym in symbols:
        try:
            asset_dir = asset_data_dir(assetclass, DATA_DIR)
            target_path = asset_dir / f"{sym}_{assetclass}_data.json"
            if target_path.exists():
                mtime = datetime.fromtimestamp(target_path.stat().st_mtime).date()
                if mtime >= today:
                    results.append({"symbol": sym, "status": "skipped", "path": str(target_path), "reason": "up-to-date"})
                    continue
            path = download_with_indicators(symbol=sym, assetclass=assetclass)
            results.append({"symbol": sym, "status": "ok", "path": str(path)})
        except Exception as exc:  # noqa: BLE001
            results.append({"symbol": sym, "status": "error", "message": str(exc)})

    return jsonify({"assetclass": assetclass, "symbols": symbols, "results": results})


def handle_not_found(error):
    return jsonify({"error": "not_found", "message": getattr(error, "description", "Not found")}), 404


def handle_server_error(error):
    return jsonify({"error": "server_error", "message": "Unexpected server error"}), 500


__all__ = [
    "add_cors_headers",
    "health",
    "list_funds",
    "get_fund",
    "get_fund_holdings",
    "get_ticker_history",
    "get_ticker_recommendation",
    "get_bulk_recommendation",
    "get_ai_portfolio",
    "regenerate_data",
    "download_holdings",
    "handle_not_found",
    "handle_server_error",
]
