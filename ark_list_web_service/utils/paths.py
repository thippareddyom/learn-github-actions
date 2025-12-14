from __future__ import annotations

from pathlib import Path

# Base directories
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CONFIG_DIR = ROOT / "configs"

# Sub-directories
TRADES_DIR = DATA_DIR / "trades"
STOCKS_DIR = DATA_DIR / "stocks"
ETF_DIR = DATA_DIR / "etf"
HOLDINGS_DIR = DATA_DIR / "holdings"
MODELS_DIR = DATA_DIR / "models"

# Core files
DATA_FILE = CONFIG_DIR / "ark-urls.json"
LEGACY_DATA_FILE = DATA_DIR / "ark-urls.json"
PORTFOLIO_FILE = TRADES_DIR / "portfolio.json"
TRADE_LOG_FILE = TRADES_DIR / "trade_log.json"
