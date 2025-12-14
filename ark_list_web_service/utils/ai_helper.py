from __future__ import annotations

import json
import math
from typing import Dict, List, Optional, Tuple

from utils.data import known_symbols
from utils.prompts import (
    build_bulk_prompt_text,
    build_portfolio_prompt_text,
    swing_prompt_etf,
    swing_prompt_stock,
)


def build_bulk_prompt(items: List[Dict[str, object]], assetclass: str = "stocks") -> str:
    """Construct the swing-trader prompt; uses swing prompts per ticker when possible."""
    ac = (assetclass or "stocks").lower()
    etf_universe = set(known_symbols("etf"))
    prompt_lines: List[str] = []
    for item in items:
        sym = item.get("symbol") or item.get("ticker") or ""
        row = item.get("row") if isinstance(item, dict) else {}
        fundamentals = item.get("fundamentals") if isinstance(item, dict) else {}
        use_etf = ac == "etf" and sym in etf_universe
        if use_etf:
            metrics = {
                "current_price": (row or {}).get("close") or fundamentals.get("current_price"),
                "sma50": (row or {}).get("sma50") or fundamentals.get("sma50"),
                "fifty_two_high": fundamentals.get("fifty_two_week_high"),
                "today_vol": (row or {}).get("volume"),
                "avg_vol": fundamentals.get("avg_volume"),
                "three_year_return": fundamentals.get("three_year_return"),
                "ytd_pct": fundamentals.get("ytd_pct"),
                "buy_rating_pct": fundamentals.get("buy_rating_pct"),
                "rsi14": (row or {}).get("rsi14") or fundamentals.get("rsi14"),
                "volume_trend": fundamentals.get("volume_trend"),
                "total_assets_billions": fundamentals.get("total_assets_billions"),
                "two_hundred_day_avg": (row or {}).get("sma200") or fundamentals.get("sma200"),
            }
            prompt_lines.append(swing_prompt_etf(str(sym), metrics))
        else:
            metrics = {
                "last_close": (row or {}).get("close"),
                "ma21": (row or {}).get("sma20") or fundamentals.get("sma20"),
                "fifty_two_high": fundamentals.get("fifty_two_week_high"),
                "volume": (row or {}).get("volume"),
                "avg_volume": fundamentals.get("avg_volume"),
                "latest_eps_growth": fundamentals.get("latest_eps_growth"),
                "next_eps_growth": fundamentals.get("next_eps_growth"),
                "ytd_pct": fundamentals.get("ytd_pct"),
                "buy_rating_pct": fundamentals.get("buy_rating_pct"),
            }
            prompt_lines.append(swing_prompt_stock(str(sym), metrics))
    # Fallback to original bulk prompt if no per-ticker prompts were generated
    return "\n\n".join([p for p in prompt_lines if p]) or build_bulk_prompt_text(items)


def deterministic_bulk_summary(items: List[Dict[str, object]]) -> Tuple[str, List[Dict[str, str]]]:
    """Rank stocks per RankMaster rules when the model is unavailable."""

    def _num(val):
        try:
            f = float(val)
            return f if math.isfinite(f) else None
        except Exception:
            return None

    ranked: List[Tuple[Tuple, Dict[str, object]]] = []
    for item in items:
        row = item["row"]
        fundamentals = item.get("fundamentals") if isinstance(item, dict) else {}
        close = _num(fundamentals.get("current_price")) or _num(row.get("close"))
        fifty_two_high = _num(fundamentals.get("fifty_two_week_high"))
        target_mean = None  # no longer used for upside
        target_upside_pct = None
        buy_rating = _num(fundamentals.get("buy_rating_pct")) or 0
        rsi = _num(row.get("rsi14")) or _num(fundamentals.get("rsi14")) or 0
        volume_trend = _num(fundamentals.get("volume_trend"))
        sma50 = _num(row.get("sma50")) or _num(row.get("sma_50")) or _num(fundamentals.get("sma50"))
        sma200 = _num(row.get("sma200")) or _num(fundamentals.get("sma200"))
        ytd = _num(row.get("ytd_pct"))

        # Hard filter: price must be above both SMA50 and SMA200 for consideration (aligns with prompt rule M)
        if close is not None and ((sma50 is not None and close <= sma50) or (sma200 is not None and close <= sma200)):
            continue

        # Upside: (52w_high - close) / close * 100 (RankMaster Pro rule)
        if close is not None and fifty_two_high not in (None, 0):
            upside = ((fifty_two_high - close) / close) * 100
        else:
            upside = 0
        target = None

        neutral_rsi = 1 if 45 <= rsi <= 65 else 0
        vol_flag = 1 if volume_trend is not None and volume_trend > 1.0 else 0
        price_above = 1 if close is not None and sma50 is not None and close > sma50 else 0
        ytd_pos = 1 if ytd is not None and ytd > 0 else 0

        sort_key = (-upside, -buy_rating, -neutral_rsi, -vol_flag, -price_above, -ytd_pos)
        ranked.append(
            (
                sort_key,
                {
                    "symbol": item["symbol"],
                    "close": close,
                    "target": target,
                    "upside": upside,
                    "buy_rating": buy_rating,
                    "rsi": rsi,
                    "volume_trend": volume_trend,
                    "ytd": ytd,
                },
            )
        )

    ranked.sort(key=lambda x: x[0])

    rows: List[Dict[str, object]] = []
    for rank, (_, info) in enumerate(ranked[:10], start=1):
        close = info["close"]
        target = info["target"]
        upside = info["upside"]
        buy_rating = info["buy_rating"]
        volume_trend = info["volume_trend"]
        rsi = info["rsi"]
        parts = []
        if upside is not None:
            parts.append(f"Upside {upside:.1f}%")
        if buy_rating:
            parts.append(f"Rating {buy_rating:.0f}%")
        if volume_trend:
            parts.append(f"Vol {volume_trend:.2f}x")
        if rsi:
            parts.append(f"RSI {rsi:.0f}")
        reason = " | ".join(parts) if parts else "Data available"
        rows.append(
            {
                "Rank": rank,
                "Ticker": info["symbol"],
                "Close": close,
                "Target": target,
                "UpsidePct": upside,
                "Reason": reason[:80],
            }
        )

    text = "Ranked by upside per RankMaster rules."
    return text, rows


def build_portfolio_prompt(data: List[Dict[str, object]], as_of: str, tickers_for_prompt: str) -> str:
    """Compose the SwingEdge Elite prompt for the AI portfolio endpoint."""
    return build_portfolio_prompt_text(data, as_of, tickers_for_prompt)
    return (
        "You are SwingEdge Elite – $200M prop swing desk. 100% offline. Use ONLY the JSONs I provide.\n\n"
        "Task: Rank the stocks and allocate capital (total = exactly 100%). Raw upside is intentionally capped so earnings trends, analyst conviction, and technical confluence dominate the sizing.\n\n"
        "Scoring Logic (strict order – total max 100 points):\n\n"
        "1. Raw Upside Contribution (max 40 points)\n"
        "   Upside % = [(financialData.targetMeanPrice or target_mean_price) - current_price] / current_price × 100\n"
        "   Points = min(Upside %, 120%) × (40 / 120)   → max 40 points even for 300%+ upside\n\n"
        "2. Earnings Growth Power (max 25 points)\n"
        "   Use earningsTrend.trend → look for \"0y\" (current FY) and \"+1y\" (next FY)\n"
        "   Points = (current year growth % × 0.5) + (next year growth % × 0.5)  \n"
        "   → capped at +25; negative growth = 0\n\n"
        "3. Analyst Conviction (max 15 points)\n"
        "   Buy % = (strongBuy + buy) from recommendationTrend.trend[0] ÷ total analysts × 100\n"
        "   90–100% → 15 pts | 70–89% → 10 pts | 50–69% → 5 pts | <50% → 0 pts\n\n"
        "4. Technical Confluence (max 20 points)\n"
        "   +7 if latest close > summaryDetail.fiftyDayAverage (or sma50)\n"
        "   +7 if latest RSI14 between 38–62 (accumulation zone)\n"
        "   +6 if avg volume last 7 days > avg volume previous 14 days (expanding interest)\n\n"
        "5. Final Score = sum of above (max 100)\n\n"
        "6. Allocation % = (Individual Final Score / Sum of all Final Scores) × 100\n"
        "   → Round to nearest 1%, last row forced to make total exactly 100%\n"
        "   → Stocks scoring <30 total points get 0% allocation and are excluded from table\n\n"
        "Output ONLY this exact table – nothing else:\n\n"
        "| Rank | Ticker | Upside % | Allocation % | Short Reason (max 22 words)                                    |\n"
        "|------|--------|----------|--------------|----------------------------------------------------------------|\n"
        "| 1    | BEAM   | +69%     | 21%          | Strong earnings growth, 88% buy ratings, perfect technicals   |\n"
        "| 2    | CERS   | +125%    | 18%          | Explosive earnings trend, expanding volume, above SMA50        |\n"
        "| ...  | ...    | ...      | ...          | ...                                                            |\n"
        "|      | TOTAL  |          | 100%         |                                                                |\n\n"
        "JSON data (array of full stock objects):\n"
        f"Tickers: {tickers_for_prompt or 'the provided list'}\n\n"
        f"Data provided (as of {as_of}): {json.dumps(data, indent=2)}"
    )


def deterministic_portfolio_rank(data: List[Dict[str, object]]) -> Tuple[str, List[Dict[str, object]], List[str]]:
    """Deterministic SwingEdge-style fallback with allocation."""

    def _num(val: object) -> Optional[float]:
        try:
            f = float(val)
            return f if math.isfinite(f) else None
        except Exception:
            return None

    enriched: List[Dict[str, object]] = []
    for row in data:
        fundamentals = row.get("fundamentals") if isinstance(row, dict) else None
        modules = row.get("modules") if isinstance(row, dict) else None
        base = fundamentals if isinstance(fundamentals, dict) else row
        # Prefer nested fundamentals, fall back to top-level fields for backward compat
        def _g(key: str):
            return (base or {}).get(key) if isinstance(base, dict) else None

        close = _num(_g("current_price")) or _num(row.get("current_price")) or _num(row.get("close"))
        target = _num(_g("target_mean_price")) or _num(row.get("target_mean_price"))
        target_upside_pct = _num(_g("target_upside_pct")) or _num(row.get("target_upside_pct"))
        upside = target_upside_pct
        if upside is None and target is not None and close not in (None, 0):
            upside = ((target - close) / close) * 100 if target != close else 0
        if upside is None:
            upside = 0
        if target is None and close is not None and target_upside_pct is not None:
            target = close * (1 + target_upside_pct / 100)

        buy = _num(_g("buy_rating_pct")) or _num(row.get("buy_rating_pct")) or 0
        rsi = _num(_g("rsi14")) or _num(_g("rsi")) or _num(row.get("rsi"))
        vol_trend = _num(_g("volume_trend")) or _num(row.get("volume_trend"))
        sma50 = _num(_g("sma50")) or _num(_g("sma_50")) or _num(row.get("sma50")) or _num(row.get("sma_50"))
        beta = _num(_g("beta"))
        fpe = _num(_g("forwardPE")) or _num(_g("pe_forward")) or _num(row.get("forwardPE"))
        sector = (base or {}).get("sectorDisp") or (base or {}).get("sector")

        sym = (row.get("ticker") or row.get("symbol") or "").upper()

        def _mod_value(mods: dict, name: str, key: str):
            if not isinstance(mods, dict):
                return None
            val = mods.get(name)
            if isinstance(val, dict):
                if sym in val:
                    val = val.get(sym)
                elif sym.lower() in val:
                    val = val.get(sym.lower())
                elif len(val) == 1:
                    val = next(iter(val.values()))
            if isinstance(val, dict):
                return val.get(key)
            return None

        if beta is None and isinstance(modules, dict):
            beta = _num(
                _mod_value(modules, "summaryDetail", "beta")
                or _mod_value(modules, "defaultKeyStatistics", "beta")
                or _mod_value(modules, "price", "beta")
            )
        if fpe is None and isinstance(modules, dict):
            fpe = _num(
                _mod_value(modules, "summaryDetail", "forwardPE")
                or _mod_value(modules, "price", "forwardPE")
                or _mod_value(modules, "defaultKeyStatistics", "forwardPE")
            )
        enriched.append(
            {
                "Rank": None,
                "ticker": row.get("ticker") or row.get("symbol"),
                "fundamentals": fundamentals,
                "modules": modules if isinstance(modules, dict) else {},
                "currentPrice": close,
                "targetPrice": target,
                "upside": upside,
                "buy_rating_pct": buy,
                "rsi": rsi,
                "volume_trend": vol_trend,
                "sma50": sma50,
                "beta": beta,
                "forwardPE": fpe,
                "sector": sector,
            }
        )

    def _earn_points(item: Dict[str, object]) -> float:
        mods = item.get("modules") if isinstance(item.get("modules"), dict) else {}
        sym = str(item.get("ticker") or item.get("symbol") or "").upper()

        def _coerce_mod(name: str):
            try:
                mod = mods.get(name)
                if isinstance(mod, dict):
                    if sym and sym in mod:
                        mod = mod.get(sym)
                    elif sym and sym.lower() in mod:
                        mod = mod.get(sym.lower())
                    elif len(mod) == 1:
                        mod = next(iter(mod.values()))
                return mod
            except Exception:
                return None

        trend_mod = _coerce_mod("earningsTrend")
        trend = None
        if isinstance(trend_mod, dict):
            trend = trend_mod.get("trend")
        elif isinstance(trend_mod, list):
            trend = trend_mod

        growth0 = None
        growth1 = None
        if isinstance(trend, list):
            for row in trend:
                if not isinstance(row, dict):
                    continue
                period = str(row.get("period") or "").lower()
                val = row.get("growth")
                if period == "0y":
                    growth0 = val
                elif period == "+1y":
                    growth1 = val

        def _to_pct(val):
            try:
                f = float(val)
                if not math.isfinite(f):
                    return 0.0
                return f * 100 if abs(f) <= 1 else f
            except Exception:
                return 0.0

        g0 = max(0.0, _to_pct(growth0))
        g1 = max(0.0, _to_pct(growth1))

        # Fallback to financialData.earningsGrowth or fundamentals.eps_growth_yoy if trend missing
        if g0 == 0 and g1 == 0:
            fin = _coerce_mod("financialData") or {}
            fallback_growth = fin.get("earningsGrowth")
            if fallback_growth is None and isinstance(item.get("fundamentals"), dict):
                fallback_growth = item["fundamentals"].get("eps_growth_yoy")
            fg = _to_pct(fallback_growth)
            g0 = max(g0, max(0.0, fg))
            g1 = max(g1, max(0.0, fg))

        pts = (g0 * 0.5) + (g1 * 0.5)
        return min(25.0, pts)

    def _score(item: Dict[str, object]) -> Dict[str, float]:
        upside = _num(item.get("upside")) or 0
        # Upside contribution capped at 120% -> max 40 pts
        upside_pts = min(max(upside, 0), 120) * (40 / 120)
        close = _num(item.get("currentPrice"))
        sma50 = _num(item.get("sma50"))
        rsi = _num(item.get("rsi"))
        vol_trend = _num(item.get("volume_trend"))
        buy_pct = _num(item.get("buy_rating_pct")) or 0

        earn_pts = _earn_points(item)

        # Analyst conviction buckets
        if buy_pct >= 90:
            analyst_pts = 15
        elif buy_pct >= 70:
            analyst_pts = 10
        elif buy_pct >= 50:
            analyst_pts = 5
        else:
            analyst_pts = 0

        tech_pts = 0.0
        if close is not None and sma50 is not None and close > sma50:
            tech_pts += 7
        if rsi is not None and 38 <= rsi <= 62:
            tech_pts += 7
        if vol_trend is not None and vol_trend > 1:
            tech_pts += 6

        total = upside_pts + earn_pts + analyst_pts + tech_pts
        return {
            "total": total,
            "upside_pts": upside_pts,
            "earn_pts": earn_pts,
            "analyst_pts": analyst_pts,
            "tech_pts": tech_pts,
        }

    for item in enriched:
        comps = _score(item)
        item["score"] = comps["total"]
        item["score_components"] = comps

    scored = [r for r in enriched if (r.get("score") or 0) >= 30]  # drop weak scores
    scored.sort(key=lambda r: (-(r.get("score") or 0), -(r.get("upside") or 0)))

    total_score = sum(r.get("score") or 0 for r in scored) or 1.0
    max_rows = min(len(scored), 10)
    alloc_data = []
    for r in scored[:max_rows]:
        raw_pct = (r["score"] / total_score) * 100
        alloc_data.append({"raw": raw_pct, "row": r})

    rows: List[Dict[str, object]] = []
    tickers: List[str] = []

    # Round to nearest %, then adjust remainders to hit 100 exactly
    allocs = [int(round(item["raw"])) for item in alloc_data]
    total_alloc = sum(allocs)
    residual = 100 - total_alloc
    if residual != 0:
        # Use fractional parts to distribute residual, cycling until resolved
        fracs = [item["raw"] - int(item["raw"]) for item in alloc_data]
        if residual > 0:
            order = sorted(range(len(fracs)), key=lambda i: fracs[i], reverse=True)
            idx = 0
            while residual > 0 and order:
                i = order[idx % len(order)]
                allocs[i] += 1
                residual -= 1
                idx += 1
        else:  # residual < 0
            order = sorted(range(len(fracs)), key=lambda i: fracs[i])
            idx = 0
            while residual < 0 and order:
                i = order[idx % len(order)]
                if allocs[i] > 0:
                    allocs[i] -= 1
                    residual += 1
                idx += 1

    for idx, (item, alloc) in enumerate(zip(alloc_data, allocs), start=1):
        r = item["row"]
        reason_parts = []
        up_val = _num(r.get("upside"))
        if up_val is not None:
            reason_parts.append(f"Upside ~{up_val:.1f}%")
        buy_pct = _num(r.get("buy_rating_pct"))
        if buy_pct:
            reason_parts.append(f"{buy_pct:.0f}% buy ratings")
        rsi = _num(r.get("rsi"))
        if rsi is not None and 38 <= rsi <= 62:
            reason_parts.append("neutral RSI")
        vol_trend = _num(r.get("volume_trend"))
        if vol_trend and vol_trend > 1:
            reason_parts.append("expanding volume")
        sma50 = _num(r.get("sma50"))
        close = _num(r.get("currentPrice"))
        if close is not None and sma50 is not None and close > sma50:
            reason_parts.append("above SMA50")
        comps = r.get("score_components") or {}
        comp_text = (
            f"pts: up {comps.get('upside_pts', 0):.1f}, earn {comps.get('earn_pts', 0):.1f}, "
            f"analyst {comps.get('analyst_pts', 0):.1f}, tech {comps.get('tech_pts', 0):.1f}, "
            f"total {comps.get('total', 0):.1f}"
        )
        reason_parts.append(comp_text)
        reason = "; ".join(reason_parts)[:200]

        rows.append(
            {
                "rank": idx,
                "ticker": r.get("ticker"),
                "UpsidePct": r.get("upside"),
                "AllocationPct": alloc,
                "reason": reason or "Data-driven ranking",
                "buy_rating_pct": r.get("buy_rating_pct"),
                "beta": r.get("beta"),
                "sector": r.get("sector"),
                "forwardPE": r.get("forwardPE"),
            }
        )
        if r.get("ticker"):
            tickers.append(r.get("ticker"))

    # Ensure tickers reflects all input symbols, not just the scored subset
    for row in data:
        sym = ""
        if isinstance(row, dict):
            sym = (row.get("ticker") or row.get("symbol") or row.get("Ticker") or "").strip().upper()
        if sym:
            tickers.append(sym)
    tickers = list(dict.fromkeys(tickers))  # preserve order, remove dupes

    text = "Deterministic selection with allocations."
    return text, rows, tickers


__all__ = [
    "build_bulk_prompt",
    "build_portfolio_prompt",
    "deterministic_bulk_summary",
    "deterministic_portfolio_rank",
]
