import React from "react";

const Bar = ({ label, value, color }) => {
  const clamped = Number.isFinite(value) ? Math.max(-200, Math.min(200, value)) : 0;
  const pct = Math.min(100, Math.abs(clamped));
  const isPositive = clamped >= 0;
  return (
    <div className="benchmark-bar">
      <div className="benchmark-bar__label">{label}</div>
      <div className="benchmark-bar__track" aria-label={`${label} performance ${value?.toFixed?.(2) ?? "n/a"}%`}>
        <div
          className="benchmark-bar__fill"
          style={{
            width: `${pct}%`,
            background: color,
            justifySelf: isPositive ? "flex-start" : "flex-end",
            marginLeft: isPositive ? 0 : "auto",
            marginRight: isPositive ? "auto" : 0,
          }}
        />
      </div>
      <div className="benchmark-bar__value">{Number.isFinite(value) ? `${value >= 0 ? "+" : ""}${value.toFixed(2)}%` : "n/a"}</div>
    </div>
  );
};

const BenchmarkBar = ({ portfolioPct, benchmarkPct, benchmarkLabel = "SPY" }) => (
  <div className="benchmark-card">
    <p className="eyebrow benchmark-card__title">Performance (same window)</p>
    <div className="benchmark-card__grid">
      <Bar label="Portfolio" value={portfolioPct} color="#0ea5e9" />
      <Bar label={benchmarkLabel} value={benchmarkPct} color="#6366f1" />
    </div>
  </div>
);

export default BenchmarkBar;
