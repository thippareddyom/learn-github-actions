import React, { useMemo } from "react";

const palette = [
  "#0ea5e9",
  "#6366f1",
  "#f97316",
  "#10b981",
  "#e11d48",
  "#a855f7",
  "#14b8a6",
  "#f59e0b",
];

const DonutLogo = ({
  openPositions = [],
  cashBalance = 0,
  size = 64,
  label = "SE AI",
  fallbackLabel,
}) => {
  const values = useMemo(() => {
    const computed = openPositions.map((pos, idx) => {
      const price =
        Number.isFinite(pos.markPrice) && pos.markPrice > 0
          ? pos.markPrice
          : Number.isFinite(pos.entryPrice)
          ? pos.entryPrice
          : 0;
      return { symbol: pos.symbol, value: (pos.shares || 0) * price, idx };
    });
    if (cashBalance > 0) {
      computed.push({ symbol: "CASH", value: cashBalance, idx: computed.length });
    }
    return computed.filter((v) => v.value > 0);
  }, [cashBalance, openPositions]);

  const total = values.reduce((sum, v) => sum + v.value, 0);
  const hasData = total > 0;

  const stops = useMemo(() => {
    if (!hasData) {
      return "conic-gradient(#0ea5e9 0deg 120deg, #6366f1 120deg 240deg, #a855f7 240deg 360deg)";
    }
    let acc = 0;
    return `conic-gradient(${values
      .map((v, i) => {
        const start = acc;
        const angle = (v.value / total) * 360;
        acc += angle;
        const color = v.symbol === "CASH" ? "#94a3b8" : palette[i % palette.length];
        return `${color} ${start.toFixed(2)}deg ${acc.toFixed(2)}deg`;
      })
      .join(", ")})`;
  }, [hasData, total, values]);

  const innerLabel = hasData ? label : fallbackLabel || label;

  return (
    <div
      className="site-header__logo"
      style={{ width: `${size}px`, height: `${size}px` }}
      role="img"
      aria-label="Portfolio positions donut"
    >
      <div className="site-header__logo-ring" style={{ background: stops }} />
      <div className="site-header__logo-inner">{innerLabel}</div>
    </div>
  );
};

export default DonutLogo;
