from __future__ import annotations

from typing import List, Optional, Tuple

from .types import Fundamentals, ScoreBreakdown, ScoreResult, TickerPayload, TrendRow


def _safe_num(val) -> Optional[float]:
    try:
        n = float(val)
    except Exception:  # noqa: BLE001
        return None
    return n if n == n else None  # NaN check


def compute_upside(fundamentals: Fundamentals) -> Optional[float]:
    current = _safe_num(
        fundamentals.get("current_price")
        or fundamentals.get("currentPrice")
        or fundamentals.get("close")
    )
    target = _safe_num(
        fundamentals.get("target_mean_price")
        or fundamentals.get("targetMeanPrice")
        or fundamentals.get("target")
    )
    # Use analyst target if available
    if current is not None and current != 0 and target is not None:
        return ((target - current) / current) * 100
    # Fallback: use 52-week high when target is missing (common for ETFs)
    fifty_two_high = _safe_num(fundamentals.get("fifty_two_week_high") or fundamentals.get("fiftyTwoWeekHigh"))
    if current is not None and current != 0 and fifty_two_high is not None:
        return ((fifty_two_high - current) / current) * 100
    return None


def parse_earnings_growth(modules) -> float:
    """Pull current/next FY earnings growth if available."""
    trend = modules.get("earningsTrend", {}).get("trend") if modules else None
    if not isinstance(trend, list):
        return 0.0
    current = next((t for t in trend if t.get("period") in ("0y", "0Y")), None)
    next_year = next((t for t in trend if t.get("period") in ("+1y", "+1Y")), None)
    cur_growth = _safe_num(current.get("growth")) if current else None
    next_growth = _safe_num(next_year.get("growth")) if next_year else None
    vals = [v for v in (cur_growth, next_growth) if v is not None]
    if not vals:
        return 0.0
    return max(0.0, sum(vals) / len(vals) * 100)


def compute_confluence(f: Fundamentals) -> Tuple[float, float, float]:
    """Return technical tuple: (structure_pts, rsi_pts, volume_pts)."""
    structure = 7 if (_safe_num(f.get("sma50")) is not None and _safe_num(f.get("current_price")) and _safe_num(f.get("current_price")) > _safe_num(f.get("sma50"))) else 0
    rsi_val = _safe_num(f.get("rsi14"))
    rsi_pts = 0
    if rsi_val is not None and 38 <= rsi_val <= 62:
        rsi_pts = 7
    vol_val = _safe_num(f.get("volume_trend"))
    volume_pts = 6 if vol_val and vol_val > 1.0 else 0
    return structure, rsi_pts, volume_pts


def score_ticker(payload: TickerPayload) -> Optional[ScoreResult]:
    ticker = (payload.get("ticker") or "").upper()
    fundamentals: Fundamentals = payload.get("fundamentals", {}) or {}
    modules = payload.get("modules", {}) or {}

    if not ticker:
        return None

    upside_pct = compute_upside(fundamentals) or fundamentals.get("target_upside_pct") or 0.0
    upside_points = min(max(upside_pct, 0), 120) * (40 / 120)  # cap contribution

    earnings_points = min(parse_earnings_growth(modules) * 0.5, 25)

    trend_rows: List[TrendRow] = modules.get("recommendationTrend", {}).get("trend") or []
    if trend_rows:
        first = trend_rows[0]
        total_analysts = sum(
            n or 0
            for n in (
                first.get("strongBuy"),
                first.get("buy"),
                first.get("hold"),
                first.get("sell"),
                first.get("strongSell"),
            )
        )
        buy_sum = (first.get("strongBuy") or 0) + (first.get("buy") or 0)
        buy_pct = (buy_sum / total_analysts * 100) if total_analysts else 0
        if buy_pct >= 90:
            analyst_points = 15
        elif buy_pct >= 70:
            analyst_points = 10
        elif buy_pct >= 50:
            analyst_points = 5
        else:
            analyst_points = 0
    else:
        analyst_points = 0

    structure_pts, rsi_pts, volume_pts = compute_confluence(fundamentals)
    technical_points = structure_pts + rsi_pts + volume_pts

    total_score = upside_points + earnings_points + analyst_points + technical_points
    breakdown = ScoreBreakdown(
        upside_pct=float(upside_pct or 0),
        upside_points=float(upside_points),
        earnings_points=float(earnings_points),
        analyst_points=float(analyst_points),
        technical_points=float(technical_points),
    )

    return ScoreResult(
        ticker=ticker,
        score=float(total_score),
        upside_pct=float(upside_pct or 0),
        allocation_pct=0.0,  # filled in by allocator
        breakdown=breakdown,
        beta=_safe_num(fundamentals.get("beta")),
        sector=fundamentals.get("sector"),
        forward_pe=_safe_num(fundamentals.get("forward_pe") or fundamentals.get("forwardPE")),
    )


def allocate(scores: List[ScoreResult]) -> List[ScoreResult]:
    """Proportionally allocate so the total is exactly 100% (integers), without negatives."""
    positive = [s for s in scores if s.score > 0]
    total = sum(s.score for s in positive)
    if not total:
        return scores

    # Largest remainder method (Hamilton) with a safety pass to avoid zeros on top names
    raw = [s.score / total * 100 for s in positive]
    floors = [int(v) for v in raw]
    remainder = 100 - sum(floors)

    alloc = floors[:]
    fracs = [(i, raw[i] - floors[i]) for i in range(len(raw))]
    fracs.sort(key=lambda t: t[1], reverse=True)

    if remainder > 0:
        for i in range(remainder):
            idx = fracs[i % len(fracs)][0]
            alloc[idx] += 1
    elif remainder < 0:
        # Remove excess starting from smallest fractional parts (least harmed)
        for i in range(-remainder):
            idx = fracs[-(i % len(fracs)) - 1][0]
            if alloc[idx] > 0:
                alloc[idx] -= 1

    # Ensure no zero allocations for top-weighted names if we have budget
    zero_indices = [i for i, v in enumerate(alloc) if v == 0]
    for zi in zero_indices:
        donor = max(range(len(alloc)), key=lambda i: alloc[i])
        if alloc[donor] > 1:
            alloc[donor] -= 1
            alloc[zi] += 1

    adjusted = []
    for pct, s in zip(alloc, positive):
        adjusted.append(
            ScoreResult(
                ticker=s.ticker,
                score=s.score,
                upside_pct=s.upside_pct,
                allocation_pct=float(pct),
                breakdown=s.breakdown,
                reason=s.reason,
                beta=s.beta,
                sector=s.sector,
                forward_pe=s.forward_pe,
            )
        )
    return adjusted
