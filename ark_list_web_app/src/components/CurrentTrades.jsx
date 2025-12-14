import React from "react";

const CurrentTrades = ({
  openPositions,
  onSelectTicker,
  formatDollars,
  formatPct,
  formatDate,
  tradeForm,
  onFieldChange,
  onBuy,
  onSell,
  onQuickSell,
}) => (
  <div className="table-wrap" style={{ marginTop: "0.75rem" }}>
    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
      <h3 style={{ margin: 0 }}>Current Trades</h3>
      <span className="eyebrow muted">Simulation only</span>
    </div>
    <table className="table" cellPadding={0} cellSpacing={0}>
      <thead>
        <tr>
          <th>Symbol</th>
          <th>Balance</th>
          <th>Shares</th>
          <th>Time Added (E.T.)</th>
          <th>Price</th>
          <th>Entry</th>
          <th>Gain/Loss%</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>
        {openPositions.length === 0 && (
          <tr>
            <td colSpan={8} className="muted">
              No open positions.
            </td>
          </tr>
        )}
        {openPositions.map((pos) => {
          const markVal = pos.shares * (Number.isFinite(pos.markPrice) ? pos.markPrice : pos.entryPrice);
          const gainPct =
            pos.entryPrice && Number.isFinite(pos.markPrice)
              ? ((pos.markPrice - pos.entryPrice) / pos.entryPrice) * 100
              : 0;
          return (
            <tr key={pos.id}>
              <td>
                <button className="link-btn" type="button" onClick={() => onSelectTicker(pos.symbol)}>
                  {pos.symbol}
                </button>
              </td>
              <td>{formatDollars(markVal)}</td>
              <td>{pos.shares.toFixed(2)}</td>
              <td>{formatDate(pos.addedAt)}</td>
              <td>{formatDollars(pos.markPrice)}</td>
              <td>{formatDollars(pos.entryPrice)}</td>
              <td className={gainPct >= 0 ? "chip--pos" : "chip--neg"}>{formatPct(gainPct)}</td>
              <td>
                <button className="chip-btn" type="button" onClick={() => onQuickSell(pos.symbol)}>
                  Close
                </button>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
    <div className="ai-box" style={{ marginTop: "0.75rem" }}>
      <div className="ai-box__grid">
        <label>
          Symbol
          <input
            className="chart-search__control"
            value={tradeForm.symbol}
            onChange={(e) => onFieldChange("symbol", e.target.value)}
            placeholder="e.g. TSLA"
          />
        </label>
        <label>
          Position size
          <select
            className="chart-search__control"
            value={tradeForm.positionSize}
            onChange={(e) => onFieldChange("positionSize", e.target.value)}
          >
            <option value="1">1</option>
            <option value="1/2">1/2</option>
            <option value="1/4">1/4</option>
          </select>
        </label>
        <label>
          Entry price
          <input
            className="chart-search__control"
            value={tradeForm.entryPrice}
            onChange={(e) => onFieldChange("entryPrice", e.target.value)}
              placeholder="Entry price"
          />
        </label>
        <label>
          Mark price (for P/L)
          <input
            className="chart-search__control"
            value={tradeForm.markPrice}
            onChange={(e) => onFieldChange("markPrice", e.target.value)}
            placeholder="Optional current price"
          />
        </label>
        <label>
          Exit price
          <input
            className="chart-search__control"
            value={tradeForm.exitPrice}
            onChange={(e) => onFieldChange("exitPrice", e.target.value)}
            placeholder="Planned exit price"
          />
        </label>
      </div>
      <div className="ai-box__footer">
        <button type="button" className="chip-btn chip-btn--active" onClick={onBuy}>
          Simulate Open
        </button>
        <button type="button" className="chip-btn" onClick={onSell}>
          Simulate Close
        </button>
      </div>
    </div>
  </div>
);

export default CurrentTrades;
