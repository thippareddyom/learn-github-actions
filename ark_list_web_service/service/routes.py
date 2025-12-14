from __future__ import annotations

from flask import Flask


def register_routes(app: Flask, handlers: dict) -> None:
    """
    Register all HTTP routes, after-request hooks, and error handlers.

    Expected keys in handlers:
      add_cors_headers, health, list_funds, get_fund, get_fund_holdings,
      get_ticker_history, get_ticker_recommendation, get_bulk_recommendation,
      get_ai_portfolio, regenerate_data, download_holdings, get_portfolio, portfolio_buy,
      portfolio_sell, handle_not_found, handle_server_error
    """

    # After-request hook
    app.after_request(handlers["add_cors_headers"])

    # Core routes
    app.add_url_rule("/health", "health", handlers["health"], methods=["GET", "OPTIONS"])
    app.add_url_rule("/funds", "list_funds", handlers["list_funds"], methods=["GET", "OPTIONS"])
    app.add_url_rule(
        "/funds/<symbol>",
        "get_fund",
        handlers["get_fund"],
        methods=["GET", "OPTIONS"],
    )
    app.add_url_rule(
        "/funds/<symbol>/holdings",
        "get_fund_holdings",
        handlers["get_fund_holdings"],
        methods=["GET", "OPTIONS"],
    )
    app.add_url_rule(
        "/tickers/<symbol>/history",
        "get_ticker_history",
        handlers["get_ticker_history"],
        methods=["GET", "OPTIONS"],
    )
    app.add_url_rule(
        "/tickers/<symbol>/recommendation",
        "get_ticker_recommendation",
        handlers["get_ticker_recommendation"],
        methods=["GET", "OPTIONS"],
    )
    app.add_url_rule(
        "/ai/bulk-recommendation",
        "get_bulk_recommendation",
        handlers["get_bulk_recommendation"],
        methods=["GET", "OPTIONS"],
    )
    app.add_url_rule(
        "/ai/portfolio",
        "get_ai_portfolio",
        handlers["get_ai_portfolio"],
        methods=["GET", "OPTIONS"],
    )
    app.add_url_rule(
        "/admin/regenerate-data",
        "regenerate_data",
        handlers["regenerate_data"],
        methods=["GET", "POST", "OPTIONS"],
    )
    app.add_url_rule(
        "/admin/download-holdings",
        "download_holdings",
        handlers["download_holdings"],
        methods=["GET", "POST", "OPTIONS"],
    )
    app.add_url_rule("/portfolio", "get_portfolio", handlers["get_portfolio"], methods=["GET", "OPTIONS"])
    app.add_url_rule("/portfolio/buy", "portfolio_buy", handlers["portfolio_buy"], methods=["POST", "OPTIONS"])
    app.add_url_rule("/portfolio/sell", "portfolio_sell", handlers["portfolio_sell"], methods=["POST", "OPTIONS"])
    if "rebalance_portfolio" in handlers:
        app.add_url_rule(
            "/admin/rebalance-portfolio",
            "rebalance_portfolio",
            handlers["rebalance_portfolio"],
            methods=["POST", "GET", "OPTIONS"],
        )

    # Error handlers
    app.register_error_handler(404, handlers["handle_not_found"])
    app.register_error_handler(500, handlers["handle_server_error"])
