import React, { useMemo, useState } from "react";

const PAGE_SIZE = 10;

const PastTrades = ({ closedTrades, onSelectTicker, formatDollars, formatPct, formatDate }) => {
  const [page, setPage] = useState(0);
  const totalPages = Math.max(1, Math.ceil((closedTrades?.length || 0) / PAGE_SIZE));
  const safePage = Math.min(page, totalPages - 1);

  const visible = useMemo(() => {
    const start = safePage * PAGE_SIZE;
    return (closedTrades || []).slice(start, start + PAGE_SIZE);
  }, [closedTrades, safePage]);

  return (
    <div className="table-wrap" style={{ marginTop: "0.75rem" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
        <h3 style={{ margin: 0 }}>Past Trades</h3>
        <span className="eyebrow muted">Simulation only</span>
      </div>
      <table className="table" cellPadding={0} cellSpacing={0}>
        <thead>
          <tr>
            <th>Trade-Balance</th>
            <th>Symbol</th>
            <th>Entry</th>
            <th>Exit</th>
            <th>Entry-Price</th>
            <th>Exit-Price</th>
            <th>Gain/Loss%</th>
          </tr>
        </thead>
        <tbody>
          {closedTrades.length === 0 && (
            <tr>
              <td colSpan={7} className="muted">
                No closed trades yet.
              </td>
            </tr>
          )}
          {visible.map((t, idx) => (
            <tr key={`${t.symbol}-${safePage * PAGE_SIZE + idx}`}>
              <td>{formatDollars(t.tradeBalance)}</td>
              <td>
                <button className="link-btn" type="button" onClick={() => onSelectTicker(t.symbol)}>
                  {t.symbol}
                </button>
              </td>
              <td>{formatDate(t.entry)}</td>
              <td>{formatDate(t.exit)}</td>
              <td>{formatDollars(t.entryPrice)}</td>
              <td>{formatDollars(t.exitPrice)}</td>
              <td className={t.gainPct >= 0 ? "chip--pos" : "chip--neg"}>{formatPct(t.gainPct)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {closedTrades.length > PAGE_SIZE && (
        <div className="pager">
          <button className="chip-btn" type="button" onClick={() => setPage(Math.max(0, safePage - 1))} disabled={safePage === 0}>
            Prev
          </button>
          <span className="muted">
            Page {safePage + 1} of {totalPages}
          </span>
          <button
            className="chip-btn"
            type="button"
            onClick={() => setPage(Math.min(totalPages - 1, safePage + 1))}
            disabled={safePage >= totalPages - 1}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
};

export default PastTrades;
