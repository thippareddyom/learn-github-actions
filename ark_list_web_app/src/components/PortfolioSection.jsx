import React from "react";
import PortfolioStats from "./PortfolioStats";
import PositionPie from "./PositionPie";
import BenchmarkBar from "./BenchmarkBar";

const PortfolioSection = ({
  cashBalance,
  portfolioStats,
  portfolioLoading,
  portfolioError,
    tradeError,
    openPositions,
    onSelectPosition,
    formatDollars,
    formatPct,
    benchmarkPct,
    benchmarkLabel = "SPY",
    benchmarkLoading,
    benchmarkError,
  }) => (
  <section className="panel">
    <PortfolioStats
      cashBalance={cashBalance}
      marketValue={portfolioStats.marketValue}
      equity={portfolioStats.equity}
      totalPct={portfolioStats.totalPct}
      formatDollars={formatDollars}
      formatPct={formatPct}
      loading={portfolioLoading}
      portfolioError={portfolioError}
      tradeError={tradeError}
    />
    <div className="portfolio-split">
      <div className="portfolio-split__positions">
        <div className="positions-card">
          <p className="eyebrow" style={{ marginTop: 0, marginBottom: "8px" }}>
            Positions (same window)
          </p>
          <PositionPie openPositions={openPositions} cashBalance={cashBalance} onSelect={onSelectPosition} size={200} />
        </div>
      </div>
      <div className="portfolio-split__bench">
        <BenchmarkBar portfolioPct={portfolioStats.totalPct} benchmarkPct={benchmarkPct} benchmarkLabel={benchmarkLabel} />
        {benchmarkLoading && (
          <p className="status status--loading" style={{ marginTop: "0.35rem" }}>
            Loading {benchmarkLabel} benchmark…
          </p>
        )}
        {benchmarkError && (
          <p className="status status--error" style={{ marginTop: "0.35rem" }}>
            {benchmarkError}
          </p>
        )}
      </div>
    </div>
  </section>
);

export default PortfolioSection;
