from __future__ import annotations
import csv
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICE_ROOT = REPO_ROOT / "ark_list_web_service"
DATA_DIR = SERVICE_ROOT / "data"
CONFIG_DIR = SERVICE_ROOT / "configs"
URLS_FILE = CONFIG_DIR / "ark-urls.json"
HOLDINGS_DIR = DATA_DIR / "holdings"
START_DATE = date(2025, 11, 26)


def load_funds() -> Dict[str, str]:
    with URLS_FILE.open(encoding="utf-8") as fp:
        data = json.load(fp)
    return {item["symbol"].upper(): item["url"] for item in data}


def business_days(start: date, end: date) -> Iterable[date]:
    current = start
    while current <= end:
        if current.weekday() < 5:  # Mon-Fri
            yield current
        current += timedelta(days=1)


def fetch_csv(url: str) -> List[Dict[str, str]]:
    resp = requests.get(url, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}")
    text = resp.text.strip()
    if not text:
        raise RuntimeError("empty response")
    reader = csv.DictReader(text.splitlines())
    return list(reader)


def save_json(path: Path, rows: List[Dict[str, str]]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fp:
        json.dump(rows, fp, indent=2)


def main(target_end: date | None = None) -> int:
    """
    Fetch latest holdings for each fund and save as <SYMBOL>-holdings.json.
    This overwrites the previous snapshot, so running daily keeps files fresh.
    """
    _ = target_end  # kept for compatibility; not used in the new scheme
    funds = load_funds()

    for symbol, url in funds.items():
        out_file = HOLDINGS_DIR / f"{symbol}-holdings.json"
        try:
            rows = fetch_csv(url)
        except Exception as exc:  # noqa: BLE001
            print(f"miss {symbol}: {exc}")
            continue
        save_json(out_file, rows)
        print(f"saved {out_file} ({len(rows)} rows)")

    return 0


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    target = datetime.strptime(arg, "%Y-%m-%d").date() if arg else None
    raise SystemExit(main(target))
