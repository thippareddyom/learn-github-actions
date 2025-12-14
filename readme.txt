Ark List – Service and Web App
=============================

Overview
--------
This project has two parts:
- Backend (Flask) in `ark_list_web_service` that serves fund holdings, ticker price history, and AI recommendations.
- Frontend (React/Vite) in `ark_list_web_app` that consumes the API and renders the dashboards (Funds, Matrix, Ticker List, AI Recommendation).

Prerequisites
-------------
- Node.js 20+
- Python 3.11+
- Git

Optional (for local LLM):
- A GGUF model placed in `ark_list_web_service/data/models/` (tiny or Llama 3). If missing, the app will fall back to deterministic recommendations.

Install dependencies
--------------------
Frontend:
  cd ark_list_web_app
  npm ci

Backend:
  cd ark_list_web_service
  pip install -r requirements.txt

Running locally
---------------
Backend (port 5000 by default):
  cd ark_list_web_service
  python app.py

Frontend (port 5173 by default):
  cd ark_list_web_app
  npm run dev

API basics
----------
- List funds: GET /funds
- Fund holdings: GET /funds/<symbol>/holdings
  * If <symbol>-holdings.json is missing, the service will attempt to download it on demand from the CSV URL in data/ark-urls.json.
- Ticker history: GET /tickers/<symbol>/history?assetclass=stocks|etf
  * Uses *_stocks_data.json or *_etf_data.json files; includes `points` and `latest`.
- Single recommendation: GET /tickers/<symbol>/recommendation
- Bulk recommendations: GET /ai/bulk-recommendation
  * Returns { tickers, recommendation, prompt, rows } where rows is a structured top-3 table.

Service endpoints (full list)
-----------------------------
- GET /health
- GET /funds
- GET /funds/<symbol>
- GET /funds/<symbol>/holdings
- GET /tickers/<symbol>/history?assetclass=stocks|etf
- GET /tickers/<symbol>/recommendation?assetclass=stocks|etf
- GET /ai/bulk-recommendation?assetclass=stocks|etf&symbols=SYM1,SYM2 (symbols optional)
- GET /ai/portfolio?assetclass=stocks|etf&symbols=SYM1,SYM2 (symbols optional)
- POST /admin/regenerate-data?assetclass=stocks|etf
- GET/POST /admin/download-holdings?symbol=ARKF
- GET/POST /admin/rebalance-portfolio
- GET /portfolio (returns cash_balance, open_positions, closed_trades)
- POST /portfolio/buy  body: {symbol, position_size, entry_price, mark_price}
- POST /portfolio/sell body: {symbol, exit_price}

Data files
----------
- Funds metadata: ark_list_web_service/data/ark-urls.json
- Holdings: ark_list_web_service/data/<SYMBOL>-holdings.json (auto-downloaded if missing)
- Price/indicators: ark_list_web_service/data/*_stocks_data.json and *_etf_data.json
- Models (optional): ark_list_web_service/data/models/

Building
--------
Frontend:
  cd ark_list_web_app
  npm run build  (outputs to ark_list_web_app/dist)

Packaging both (local helper):
  scripts/pack.sh
  Result: dist/web (frontend) and dist/service (backend copy), with requirements.lock.txt and model pruned.

CI/CD (GitHub Actions)
----------------------
- .github/workflows/build.yml builds on push to main and PRs; outputs a dist artifact (web + service).
- .github/workflows/deply.yml is a build-only duplicate by default; adjust to deploy if needed.

Notes on AI
-----------
- If DISABLE_LOCAL_LLM is set or a model is missing, the backend returns deterministic fallback text and rows.
- AI Recommendation in the UI uses /ai/bulk-recommendation; the frontend renders the returned `rows` table and clickable tickers.

Common issues
-------------
- 404 on /funds/<symbol>/holdings: run backend once so it auto-downloads, or run scripts/fetch_holdings.py to create <SYMBOL>-holdings.json.
- Empty rows from /ai/bulk-recommendation: ensure the latest *_stocks_data.json has finite close/MA values; rerun data download if needed.
- Model download: large GGUF files are not stored in git; place them manually under data/models/ if you want local LLM responses.
- Bulk refresh uses curated lists: `ark_list_web_service/data/holdings/etf_holdings.json` (ETFs) and `ark_list_web_service/data/holdings/stocks-holdings.json` (stocks). `regenerate_data` and `scripts/ticker_data_refresh.py` read those files (plus any `*-holdings.json`) to decide which tickers to download.
- python scripts/ticker_data_refresh.py --assetclass etf and python scripts/ticker_data_refresh.py --assetclass stocks.
AI
---
https://huggingface.co/tarun7r/Finance-Llama-8B-q4_k_m-GGUF/resolve/main/Finance-Llama-8B-GGUF-q4_K_M.gguf
