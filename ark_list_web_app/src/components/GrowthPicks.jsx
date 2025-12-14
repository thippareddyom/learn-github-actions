import React from "react";

const GrowthPicks = ({
  deterministicTable,
  processedTickers,
  aiAssetClass,
  aiTickerInput,
  onAssetClassChange,
  onTickerInputChange,
  onRun,
  onTickerClick,
  onBuy,
  onTickerInputKeyDown,
  openTickers = [],
  title = "Growth portfolio picks",
  eyebrow = "Deterministic selection (simulated)",
  upsideLabel = "Upside Target %",
  upsideKey = "upside",
  hideAssetSelect = false,
  assetOptions = [
    { value: "stocks", label: "stocks" },
    { value: "etf", label: "etf" },
  ],
}) => {
  if (!deterministicTable?.length) return null;

  return (
    <section className="panel panel--chart">
      <div className="panel__header">
        <div>
          <p className="eyebrow">{eyebrow}</p>
          <h2>{title}</h2>
        </div>
      </div>
      <div className="ai-rec__container">
        <div className="chart-search" style={{ marginBottom: "0.35rem" }}>
          {!hideAssetSelect && (
            <select
              className="chart-search__control"
              value={aiAssetClass}
              onChange={(e) => onAssetClassChange(e.target.value)}
              style={{ maxWidth: "120px" }}
            >
              {assetOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          )}
          <input
            type="text"
            className="chart-search__control chart-search__input"
            style={{ minWidth: "260px" }}
            value={aiTickerInput}
            placeholder="Enter tickers (comma separated)"
            onChange={(e) => onTickerInputChange(e.target.value)}
            onKeyDown={onTickerInputKeyDown}
          />
          <button type="button" className="chart-search__button" onClick={onRun}>
            Run
          </button>
        </div>
        <p className="muted" style={{ margin: "0 0 0.6rem 0", fontSize: "0.9rem", color: "#000" }}>
          Leave blank to use default universe. Used for deterministic selection and allocations.
        </p>
        <div className="table-wrap">
          <table className="table" cellPadding={0} cellSpacing={0}>
            <thead>
              <tr>
                <th>#</th>
                <th>Ticker</th>
                <th>{upsideLabel}</th>
                <th>Allocation %</th>
                <th>Beta</th>
                <th>Sector</th>
                <th>Fwd PE</th>
                <th>Short Description</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {deterministicTable.map((row) => {
                const isHeld = openTickers.includes(row.ticker);
                const upsVal =
                  row[upsideKey] ??
                  row.upside ??
                  (upsideKey ? undefined : row.ytd_pct ?? row.ytd ?? row.target_upside_pct ?? row.targetUpsidePct);
                return (
                <tr key={row.rank}>
                  <td>{row.rank}</td>
                  <td>
                    <button type="button" className="link-btn" onClick={() => onTickerClick(row.ticker)}>
                      {row.ticker}
                    </button>
                  </td>
                  <td>
                    {Number.isFinite(upsVal) ? `${upsVal >= 0 ? "+" : ""}${Number(upsVal).toFixed(1)}%` : "-"}
                  </td>
                  <td>{Number.isFinite(row.allocation) ? `${row.allocation.toFixed(0)}%` : "-"}</td>
                  <td>{Number.isFinite(row.beta) ? row.beta.toFixed(2) : "-"}</td>
                  <td>{row.sector || "-"}</td>
                  <td>{Number.isFinite(row.forwardPE) ? row.forwardPE.toFixed(2) : "-"}</td>
                  <td>{row.reason || row.Reason || "-"}</td>
                  <td>
                    <button
                      type="button"
                      className="chip-btn chip-btn--active"
                      onClick={() => onBuy(row.ticker)}
                      disabled={isHeld}
                      title={isHeld ? "Already in Current Trades" : "Simulate add"}
                      style={{ whiteSpace: "nowrap", minWidth: "108px", justifyContent: "center" }}
                    >
                      {isHeld ? "Held" : "Simulate add"}
                    </button>
                  </td>
                </tr>
              );
              })}
            </tbody>
          </table>
        </div>
        <div className="ai-rec__tickers" style={{ marginTop: "0.75rem" }}>
          <span className="muted">Bullish setups processed from </span>
          <div className="ai-rec__tickers-list">
            {processedTickers.map((ticker, idx) => (
              <button
                key={`${ticker}-${idx}`}
                className="link-btn link-btn--inline"
                type="button"
                onClick={() => onTickerClick(ticker)}
              >
                {ticker}
                {idx < processedTickers.length - 1 ? "," : ""}
              </button>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
};

export default GrowthPicks;
