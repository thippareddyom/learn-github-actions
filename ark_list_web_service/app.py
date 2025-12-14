from __future__ import annotations

import os
import sys
from pathlib import Path

from flask import Flask

from service.handlers import (
    add_cors_headers,
    get_ai_portfolio,
    get_bulk_recommendation,
    get_fund,
    get_fund_holdings,
    get_ticker_history,
    get_ticker_recommendation,
    download_holdings,
    handle_not_found,
    handle_server_error,
    health,
    list_funds,
    regenerate_data,
)
from service.portfolio import get_portfolio, portfolio_buy, portfolio_sell
from service.routes import register_routes
from service.portfolio import rebalance_portfolio

# Support running as a script without package installation
try:
    from utils.paths import ROOT  # noqa: F401
except ImportError:  # pragma: no cover
    HERE = Path(__file__).resolve().parent
    sys.path.append(str(HERE))
    sys.path.append(str(HERE / "utils"))
    from ark_list_web_service.utils.paths import ROOT  # type: ignore  # noqa: F401


def create_app() -> Flask:
    app = Flask(__name__)
    register_routes(
        app,
        {
            "add_cors_headers": add_cors_headers,
            "health": health,
            "list_funds": list_funds,
            "get_fund": get_fund,
            "get_fund_holdings": get_fund_holdings,
            "get_ticker_history": get_ticker_history,
            "get_ticker_recommendation": get_ticker_recommendation,
            "get_bulk_recommendation": get_bulk_recommendation,
            "get_ai_portfolio": get_ai_portfolio,
            "regenerate_data": regenerate_data,
            "download_holdings": download_holdings,
            "get_portfolio": get_portfolio,
            "portfolio_buy": portfolio_buy,
            "portfolio_sell": portfolio_sell,
            "rebalance_portfolio": rebalance_portfolio,
            "handle_not_found": handle_not_found,
            "handle_server_error": handle_server_error,
        },
    )
    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
