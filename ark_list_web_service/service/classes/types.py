from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, TypedDict, Union


class Fundamentals(TypedDict, total=False):
    current_price: float
    target_mean_price: float
    target_upside_pct: float
    buy_rating_pct: float
    rsi14: float
    sma50: float
    volume_trend: float
    eps_growth_yoy: float
    roe: float
    ytd_pct: float
    beta: float
    forward_pe: float
    sector: str


class TrendRow(TypedDict, total=False):
    period: str
    strongBuy: int
    buy: int
    hold: int
    sell: int
    strongSell: int


class Modules(TypedDict, total=False):
    fundamentals: Fundamentals
    recommendationTrend: Dict[str, List[TrendRow]]
    earningsTrend: Dict[str, object]


class TickerPayload(TypedDict, total=False):
    ticker: str
    fundamentals: Fundamentals
    modules: Modules


@dataclass
class ScoreBreakdown:
    upside_pct: float
    upside_points: float
    earnings_points: float
    analyst_points: float
    technical_points: float


@dataclass
class ScoreResult:
    ticker: str
    score: float
    upside_pct: float
    allocation_pct: float
    breakdown: ScoreBreakdown
    reason: str = ""
    beta: Optional[float] = None
    sector: Optional[str] = None
    forward_pe: Optional[float] = None


# Generic metrics map for prompt helpers / LLM fallbacks
Metrics = Dict[str, Union[str, float, int, None]]
