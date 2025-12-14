from __future__ import annotations

"""
Centralized prompt builders used by the service.

Used by:
- build_bulk_prompt_text: /ai/bulk-recommendation (utils.ai_helper)
- build_portfolio_prompt_text: /ai/portfolio (utils.ai_helper)
- swing_prompt_stock / swing_prompt_etf: LocalRecommender (service.classes.recommender)
"""

import json
from typing import Dict, List


def build_bulk_prompt_text(items: List[Dict[str, object]]) -> str:
    """Swing-trader prompt for /ai/bulk-recommendation."""
    lines = []
    for item in items:
        sym = item["symbol"]
        row = item["row"]
        lines.append(
            f"{sym}: close {row.get('close')}, volume {row.get('volume')}, "
            f"sma20 {row.get('sma20')}, sma50 {row.get('sma50')}, sma200 {row.get('sma200')}, "
            f"rsi14 {row.get('rsi14')}, macd {row.get('macd')}, macd_hist {row.get('macd_hist')}, "
            f"bb_upper {row.get('bb_upper')}, bb_lower {row.get('bb_lower')}, atr14 {row.get('atr14')}"
        )
    base = (
        "You are a highly disciplined, data-driven quantitative swing trader with 15+ years of experience trading "
        "U.S. equities and ETFs. Your edge comes from strict rule-based technical analysis combined with volume, "
        "momentum, and volatility signals. You never guess and you never give financial advice—only objective "
        "technical analysis. Treat the provided rows as your full data context; do not invent missing values.\n\n"
        "For each ticker below, analyze ONLY the latest daily timeframe chart and the following indicators:\n"
        "- Price action & candlestick structure and key support/resistance levels\n"
        "- Volume trend and any volume spikes\n"
        "- MA20, MA50, MA200 (position of price relative to them + any recent crosses)\n"
        "- RSI(14) — current value and whether overbought (>70), oversold (<30), or showing divergence\n"
        "- MACD(12,26,9) — histogram, signal line cross, zero-line context, and divergence\n"
        "- Bollinger Bands (20,2) — price position (upper/lower band, squeeze, expansion)\n"
        "- ATR(14) — current value and whether volatility is expanding or contracting\n\n"
        "Finally, for any ticker rated Strong Bullish or Strong Bearish, suggest a logical swing-trade setup including "
        "entry zone, stop-loss, initial target, and risk-reward (>=2:1).\n"
        "Analyze these tickers:\n"
    )
    guide = (
        "\nFor each ticker, provide 1-2 sentences covering trend, S/R, structure, and volume confirmation. "
        "Then rank the top 3-5 strongest bullish setups with brief reasons. Only recommend clear uptrends or breakouts "
        "with volume.\n"
    )
    return base + "\n".join(lines) + "\n" + guide


def build_portfolio_prompt_text(data: List[Dict[str, object]], as_of: str, tickers_for_prompt: str) -> str:
    """Portfolio allocation prompt for /ai/portfolio."""
    return (
        "You are SwingEdge Elite — $200M prop swing desk. 100% offline. Use ONLY the JSONs I provide.\n\n"
        "Task: Rank the stocks and allocate capital (total = exactly 100%). Raw upside is intentionally capped so earnings trends, analyst conviction, and technical confluence dominate the sizing.\n\n"
        "Scoring Logic (strict order — total max 100 points):\n\n"
        "1. Raw Upside Contribution (max 40 points)\n"
        "   Upside % = [(financialData.targetMeanPrice or target_mean_price) - current_price] / current_price × 100\n"
        "   Points = min(Upside %, 120%) × (40 / 120)   — max 40 points even for 300%+ upside\n\n"
        "2. Earnings Growth Power (max 25 points)\n"
        "   Use earningsTrend.trend — look for \"0y\" (current FY) and \"+1y\" (next FY)\n"
        "   Points = (current year growth % × 0.5) + (next year growth % × 0.5)  \n"
        "   — capped at +25; negative growth = 0\n\n"
        "3. Analyst Conviction (max 15 points)\n"
        "   Buy % = (strongBuy + buy) from recommendationTrend.trend[0] ÷ total analysts × 100\n"
        "   90—100% → 15 pts | 70—89% → 10 pts | 50—69% → 5 pts | <50% → 0 pts\n\n"
        "4. Technical Confluence (max 20 points)\n"
        "   +7 if latest close > summaryDetail.fiftyDayAverage (or sma50)\n"
        "   +7 if latest RSI14 between 38—62 (accumulation zone)\n"
        "   +6 if avg volume last 7 days > avg volume previous 14 days (expanding interest)\n\n"
        "5. Final Score = sum of above (max 100)\n\n"
        "6. Allocation % = (Individual Final Score / Sum of all Final Scores) × 100\n"
        "   — Round to nearest 1%, last row forced to make total exactly 100%\n"
        "   — Stocks scoring <30 total points get 0% allocation and are excluded from table\n\n"
        "Output ONLY this exact table — nothing else:\n\n"
        "| Rank | Ticker | Upside % | Allocation % | Short Reason (max 22 words)                                    |\n"
        "|------|--------|----------|--------------|----------------------------------------------------------------|\n"
        "| 1    | BEAM   | +69%     | 21%          | Strong earnings growth, 88% buy ratings, perfect technicals   |\n"
        "| 2    | CERS   | +125%    | 18%          | Explosive earnings trend, expanding volume, above SMA50        |\n"
        "| ...  | ...    | ...      | ...          | ...                                                            |\n"
        "|      | TOTAL  |          | 100%         |                                                                |\n\n"
        f"Tickers: {tickers_for_prompt or 'the provided list'}\n\n"
        f"Data provided (as of {as_of}): {json.dumps(data, indent=2)}"
    )


def swing_prompt_stock(symbol: str, metrics: Dict[str, object]) -> str:
    """CANSLIM-like swing prompt for individual stocks (LocalRecommender)."""
    last_close = metrics.get("last_close")
    ma21 = metrics.get("ma21")
    fifty_two_high = metrics.get("fifty_two_high")
    today_vol = metrics.get("volume")
    avg_vol = metrics.get("avg_volume")
    latest_eps_g = metrics.get("latest_eps_growth")
    next_eps_g = metrics.get("next_eps_growth")
    ytd_pct = metrics.get("ytd_pct")
    buy_rating_pct = metrics.get("buy_rating_pct")
    return (
        f"You are a strict IBD CANSLIM swing trade expert. Ticker: {symbol}. "
        f"Last close: {last_close}. MA21: {ma21}. "
        f"52w high: {fifty_two_high}. Today vol: {today_vol}, Avg vol(50): {avg_vol}. "
        f"Latest EPS growth: {latest_eps_g}, Next EPS growth: {next_eps_g}, YTD%: {ytd_pct}, "
        f"Buy rating %: {buy_rating_pct}. "
        "Only reply if ALL CANSLIM rules are met using ONLY these fields: "
        "C: latest quarter EPS growth >=25% AND sales growth >=25% (if sales are missing, treat as a fail). "
        "A: annual EPS growth >=25% and ROE >=17% if provided; missing data fails the rule. "
        "N: price is within 5% of, or breaking, the 52-week high. "
        "S: today volume >= 1.5x averageVolume(50). "
        "L: relative strength proxy: YTD% must be positive (ideally >20%); negative/zero fails. "
        "I: institutional sponsorship proxy: buy_rating_pct >=50%. "
        "M: assume market is acceptable (Confirmed Uptrend/Under Pressure). "
        "Buy only if price is within 5% above a valid base pivot implied by being near the 52w high. "
        "Reply EXACTLY in one line: "
        "Buy: <price> | Target: <price> | Stop: <price> | Note: <<=20 words>. "
        "If ANY rule fails or data is missing, reply only: 'NO CANSLIM SETUP' — nothing else."
    )


def swing_prompt_etf(symbol: str, metrics: Dict[str, object]) -> str:
    """Swing prompt for ETFs (LocalRecommender)."""
    current_price = metrics.get("current_price")
    sma50 = metrics.get("sma50")
    fifty_two_high = metrics.get("fifty_two_high")
    today_vol = metrics.get("today_vol") or metrics.get("volume")
    avg_vol = metrics.get("avg_vol") or metrics.get("avg_volume")
    three_year_return = metrics.get("three_year_return")
    ytd_pct = metrics.get("ytd_pct")
    buy_rating_pct = metrics.get("buy_rating_pct")
    rsi14 = metrics.get("rsi14")
    volume_trend = metrics.get("volume_trend")
    total_assets_billions = metrics.get("total_assets_billions")
    two_hundred_day_avg = metrics.get("two_hundred_day_avg") or metrics.get("sma200")
    return (
        f"You are a strict ETF swing trade expert. Ticker: {symbol}. "
        f"Current price: {current_price}. SMA50: {sma50}. "
        f"52w high: {fifty_two_high}. Today vol: {today_vol}, Avg vol: {avg_vol}. "
        f"3Y return: {three_year_return}%, YTD%: {ytd_pct}, "
        f"Buy rating %: {buy_rating_pct}. RSI14: {rsi14}. Volume trend: {volume_trend}. "
        f"Total assets (B): {total_assets_billions}. 200D MA: {two_hundred_day_avg}. "
        "Only reply if ALL swing rules are met using ONLY these fields: "
        "C: Current momentum - RSI14 between 50 and 70 (bullish but not overbought). "
        "A: Annual performance - three_year_return >=20%. "
        "N: Near 52-week high - current_price >= 0.95 * fifty_two_high. "
        "S: Supply/demand - volume_trend >=1.2 (increased interest). "
        "L: Leader - ytd_pct >=15% (outperforming). "
        "I: Institutional proxy - total_assets_billions >=100. "
        "M: Market trend - current_price > sma50 and current_price > two_hundred_day_avg (uptrend). "
        "Hard filter: if current_price <= sma50 OR sma50 <= two_hundred_day_avg, immediately reply 'NO SWING SETUP'. "
        "Buy only if price is above SMA50 with momentum, implying a trend-following or breakout setup. "
        "Reply EXACTLY in one line: "
        "Buy: <price> | Target: <price> | Stop: <price> | Note: <<=20 words>. "
        "If ANY rule fails or data is missing, reply only: 'NO SWING SETUP' — nothing else."
    )
