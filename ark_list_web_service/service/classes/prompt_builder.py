from __future__ import annotations

from typing import List

from .types import ScoreResult


def build_allocation_table(scores: List[ScoreResult]) -> str:
    """Create a simple markdown table for ranked scores."""
    headers = "| Rank | Ticker | Upside % | Allocation % | Short Description |\n|------|--------|----------|--------------|-------------------|"
    rows = []
    for idx, s in enumerate(scores, start=1):
        rows.append(
            f"| {idx} | {s.ticker} | {s.upside_pct:+.1f}% | {s.allocation_pct:.0f}% | {s.reason or 'Ranked by score'} |"
        )
    rows.append("|      | TOTAL  |          | 100%         | |")
    return "\n".join([headers, *rows])


def build_summary(scores: List[ScoreResult]) -> str:
    """Provide a one-line summary per ticker using breakdown fields."""
    parts = []
    for s in scores:
        b = s.breakdown
        parts.append(
            f"{s.ticker}: score {s.score:.1f}; up {b.upside_points:.1f}; "
            f"earn {b.earnings_points:.1f}; analyst {b.analyst_points:.1f}; tech {b.technical_points:.1f}"
        )
    return " | ".join(parts)

