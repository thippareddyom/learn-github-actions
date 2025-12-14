from __future__ import annotations

"""
Refresh local stock/ETF price data for tickers found in holdings files.

Usage:
    python ticker_data_refresh.py               # refresh stocks from holdings
    python ticker_data_refresh.py --assetclass etf
    python ticker_data_refresh.py --limit 50    # refresh first 50 tickers
"""

import argparse
from datetime import date, datetime
import sys
from pathlib import Path
from typing import List

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICE_ROOT = REPO_ROOT / "ark_list_web_service"
sys.path.append(str(SERVICE_ROOT))  # allow `utils` imports when run as a script

from utils.data import tickers_from_holdings  # noqa: E402
from utils.helpers import asset_data_dir, normalize_symbol  # noqa: E402
from utils.paths import DATA_DIR  # noqa: E402
from utils.yahoo_data_loader import download_with_indicators  # noqa: E402


def refresh_tickers(assetclass: str, tickers: List[str]) -> None:
    ok = 0
    miss = 0
    skipped = 0
    asset_dir = asset_data_dir(assetclass, DATA_DIR)
    today = date.today()
    for sym in tickers:
        safe = normalize_symbol(sym)
        if not safe or safe == "-":
            continue
        target_path = asset_dir / f"{safe}_{assetclass}_data.json"
        try:
            mdate = datetime.fromtimestamp(target_path.stat().st_mtime).date() if target_path.exists() else None
            if mdate and mdate >= today:
                skipped += 1
                print(f"skip {safe}: up-to-date ({mdate.isoformat()})")
                continue
        except Exception:
            pass
        try:
            download_with_indicators(symbol=safe, assetclass=assetclass)
            ok += 1
        except Exception as exc:  # pragma: no cover - best-effort download
            miss += 1
            print(f"miss {safe}: {exc}")
    print(f"Done. refreshed={ok}, skipped={skipped}, failed={miss}, total={len(tickers)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh local price data for holdings tickers.")
    parser.add_argument("--assetclass", default="stocks", choices=["stocks", "etf"], help="Asset class to refresh")
    parser.add_argument("--limit", type=int, default=0, help="Optional limit on number of tickers to refresh")
    args = parser.parse_args()

    tickers = tickers_from_holdings(assetclass=args.assetclass)
    if args.limit and args.limit > 0:
        tickers = tickers[: args.limit]
    if not tickers:
        print("No tickers found in holdings.")
        return 1
    print(f"Refreshing {len(tickers)} tickers for assetclass={args.assetclass} ...")
    refresh_tickers(args.assetclass, tickers)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
