from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, Optional, Union

try:
    from llama_cpp import Llama  # type: ignore
except Exception:  # noqa: BLE001
    Llama = None

from utils.helpers import format_simple_plan
from utils.paths import DATA_DIR
from utils.prompts import swing_prompt_stock, swing_prompt_etf

from .prompt_builder import build_allocation_table, build_summary
from .scoring import allocate, score_ticker
from .types import ScoreResult, TickerPayload


def _resolve_model_path(model_path: Optional[str]) -> Path:
    """Find a usable local model path, preferring env overrides then defaults."""
    default_candidates = [
        DATA_DIR / "models" / "Finance-Llama-8B-GGUF-q4_K_M.gguf",
        DATA_DIR / "models" / "Meta-Llama-3-8B-Instruct-Q8_0.gguf",
        DATA_DIR / "models" / "tiny-llm.gguf",
    ]
    if model_path:
        return Path(model_path)
    env_path = os.environ.get("LOCAL_LLM_MODEL")
    if env_path:
        return Path(env_path)
    return next((p for p in default_candidates if p.exists()), default_candidates[0])


def _build_prompt_v2(symbol: str, metrics: Dict[str, Union[str, float, int, None]]) -> str:
    """CANSLIM prompt that relies only on provided metrics."""
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


def _build_prompt(symbol: str, metrics: Dict[str, Union[str, float, int, None]]) -> str:
    """Create a CANSLIM-enforced, one-line swing prompt."""
    return swing_prompt_stock(symbol, metrics)


def _build_prompt_etf(symbol: str, metrics: Dict[str, Union[str, float, int, None]]) -> str:
    """Swing trade prompt for ETFs adapted from CANSLIM, using provided metrics."""
    return swing_prompt_etf(symbol, metrics)


class LocalRecommender:
    """Light wrapper around an optional local Llama model."""

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = str(_resolve_model_path(model_path))
        self.model = None

    def ensure_model(self):
        if Llama is None:
            raise RuntimeError("llama-cpp-python not installed")
        if self.model:
            return
        if not Path(self.model_path).exists():
            raise FileNotFoundError(f"Model not found at {self.model_path}")
        n_threads = int(os.environ.get("LLM_N_THREADS", max(os.cpu_count() or 2, 2)))
        n_gpu_layers = int(os.environ.get("LLM_N_GPU_LAYERS", "0"))
        self.model = Llama(
            model_path=self.model_path,
            n_threads=n_threads,
            n_ctx=1024,
            n_gpu_layers=n_gpu_layers,
        )
        if not hasattr(self.model, "sampler"):
            setattr(self.model, "sampler", None)

    def generate(self, symbol: str, metrics: Dict[str, Union[str, float, int, None]]) -> str:
        if os.environ.get("DISABLE_LOCAL_LLM"):
            return format_simple_plan(symbol, metrics)

        self.ensure_model()
        assetclass = str(metrics.get("assetclass") or "stocks").lower()
        base_prompt = _build_prompt_etf(symbol, metrics) if assetclass == "etf" else _build_prompt_v2(symbol, metrics)
        try:
            if hasattr(self.model, "create_chat_completion"):
                out = self.model.create_chat_completion(
                    messages=[
                        {"role": "system", "content": "You are a concise swing-trade helper."},
                        {"role": "user", "content": base_prompt},
                    ],
                    max_tokens=120,
                    temperature=0.6,
                    top_p=0.9,
                    repeat_penalty=1.1,
                )
                text = out["choices"][0]["message"]["content"]
            else:
                out = self.model(
                    base_prompt,
                    max_tokens=120,
                    temperature=0.6,
                    top_p=0.9,
                    repeat_penalty=1.1,
                    echo=False,
                )
                text = out["choices"][0]["text"]
            final = text.strip()
            lower_final = final.lower()
            digits = re.findall(r"\d", final)
            if (
                not final
                or "reply in one line" in lower_final
                or "you are" in lower_final
                or "buy" not in lower_final
                or "target" not in lower_final
                or "stop" not in lower_final
                or len(digits) < 3
            ):
                return format_simple_plan(symbol, metrics)
            return final
        except Exception:
            return format_simple_plan(symbol, metrics)


def score_and_allocate(payloads: list[TickerPayload], top_n: int = 10) -> list[ScoreResult]:
    """Score incoming payloads and allocate capital proportionally, keeping only top_n."""
    scored: list[ScoreResult] = []
    for p in payloads:
        result = score_ticker(p)
        if result:
            scored.append(result)
    scored = sorted(scored, key=lambda s: s.score, reverse=True)
    if top_n and top_n > 0:
        scored = scored[:top_n]
    scored = allocate(scored)
    return scored


def build_allocation_prompt(payloads: list[TickerPayload]) -> str:
    """Produce a markdown table and short summary for the allocator."""
    scored = score_and_allocate(payloads)
    table = build_allocation_table(scored)
    summary = build_summary(scored)
    return f"{table}\n\nSummary: {summary}"


__all__ = ["LocalRecommender", "score_and_allocate", "build_allocation_prompt"]



