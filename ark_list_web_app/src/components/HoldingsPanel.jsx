import React from "react";

const HoldingsTable = ({ rows }) => (
  <div className="table-wrap">
    <table className="table" cellPadding={0} cellSpacing={0}>
      <thead>
        <tr>
          {Array.isArray(rows) && rows[0]
            ? Object.keys(rows[0]).map((col) => <th key={col}>{col}</th>)
            : null}
        </tr>
      </thead>
      <tbody>
        {(!rows || rows.length === 0) && (
          <tr>
            <td className="muted">No holdings</td>
          </tr>
        )}
        {rows?.map((row, idx) => (
          <tr key={idx}>
            {Object.values(row).map((val, i) => (
              <td key={`${idx}-${i}`}>{val}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);

const HoldingsPanel = ({ title = "Holdings", asOf, loading, error, rows, footnote }) => (
  <section className="panel">
    <div className="panel__header panel__header--between">
      <div>
        <p className="eyebrow">{title}</p>
        <p className="muted">{asOf ? `As of ${asOf}` : "Latest available snapshot"}</p>
      </div>
      <div className="panel__meta">
        {loading && <span className="status status--loading">Loading...</span>}
        {error && <span className="status status--error">{error}</span>}
      </div>
    </div>
    {!loading && !error && <HoldingsTable rows={rows} />}
    {loading && <p className="muted">Fetching holdings...</p>}
    {footnote && <p className="footnote">{footnote}</p>}
  </section>
);

export default HoldingsPanel;
