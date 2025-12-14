import React from "react";

const PortfolioStats = ({
  cashBalance,
  marketValue,
  equity,
  totalPct,
  formatDollars,
  formatPct,
  loading,
  portfolioError,
  tradeError,
}) => (
  <>
    <div className="panel__header panel__header--between">
      <div>
        <p className="eyebrow">Model Portfolio</p>
        <h2>Cash + Positions</h2>
      </div>
      <div className="panel__meta">
        {loading && <span className="status status--loading">Syncing...</span>}
        {portfolioError && <span className="status status--error">{portfolioError}</span>}
        {tradeError && <span className="status status--error">{tradeError}</span>}
      </div>
    </div>
    <div className="chip-row">
      <span className="pill">Cash: {formatDollars(cashBalance)}</span>
      <span className="pill">Market Value: {formatDollars(marketValue)}</span>
      <span className="pill">Equity: {formatDollars(equity)}</span>
      <span className="pill">Total P/L: {formatPct(totalPct)}</span>
    </div>
  </>
);

export default PortfolioStats;
