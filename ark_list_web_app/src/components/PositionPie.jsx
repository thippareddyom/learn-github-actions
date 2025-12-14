import React from "react";

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

const PositionPie = ({ openPositions, cashBalance = 0, onSelect, size = 240 }) => {
  if (!openPositions?.length) return null;

  const values = openPositions.map((pos, idx) => {
    const price =
      Number.isFinite(pos.markPrice) && pos.markPrice > 0
        ? pos.markPrice
        : Number.isFinite(pos.entryPrice)
        ? pos.entryPrice
        : 0;
    const markVal = pos.shares * price;
    return { id: pos.id, symbol: pos.symbol, value: markVal, idx };
  });

  if (cashBalance > 0) {
    values.push({ id: "CASH", symbol: "CASH", value: cashBalance, idx: values.length });
  }

  const total = values.reduce((sum, v) => sum + v.value, 0) || 1;

  let acc = 0;
  const stops = values
    .map((v, i) => {
      const start = acc;
      const angle = (v.value / total) * 360;
      acc += angle;
      const color = v.symbol === "CASH" ? "#94a3b8" : palette[i % palette.length];
      return `${color} ${start.toFixed(2)}deg ${acc.toFixed(2)}deg`;
    })
    .join(", ");

  return (
    <div style={{ display: "flex", alignItems: "center", gap: "1.2rem", margin: "0.5rem 0 0.75rem", flexWrap: "nowrap" }}>
      <div style={{ position: "relative", width: `${size || 240}px`, height: `${size || 240}px` }}>
        <div
          style={{
            width: `${(size || 240) * 0.67}px`,
            height: `${(size || 240) * 0.67}px`,
            borderRadius: "9999px",
            background: `conic-gradient(${stops})`,
            border: "1px solid #e2e8f0",
            position: "absolute",
            left: `${(size || 240) * 0.167}px`,
            top: `${(size || 240) * 0.167}px`,
            boxShadow: "0 6px 18px rgba(15, 23, 42, 0.1)",
            cursor: "pointer",
          }}
          onClick={() => onSelect(values[0]?.symbol)}
          title="Click any legend to focus a position"
        />
        <div
          style={{
            position: "absolute",
            left: `${(size || 240) * 0.25}px`,
            top: `${(size || 240) * 0.25}px`,
            right: `${(size || 240) * 0.25}px`,
            bottom: `${(size || 240) * 0.25}px`,
            borderRadius: "9999px",
            background: "#f8fafc",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontWeight: 700,
            color: "#0f172a",
            fontSize: "13px",
            textAlign: "center",
            padding: "0 6px",
            boxShadow: "inset 0 0 0 1px #e2e8f0",
          }}
        >
          Positions
        </div>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.6rem", maxWidth: "380px" }}>
        {values.map((v, i) => {
          const pct = (v.value / total) * 100;
          const color = v.symbol === "CASH" ? "#94a3b8" : palette[i % palette.length];
          return (
            <div
              key={`legend-${v.id}`}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                padding: "4px 8px",
                borderRadius: "8px",
                border: "1px solid #e2e8f0",
                background: "#fff",
                boxShadow: "0 2px 6px rgba(15, 23, 42, 0.08)",
                minWidth: "120px",
                justifyContent: "flex-start",
              }}
            >
              <span
                style={{
                  width: "10px",
                  height: "10px",
                  borderRadius: "9999px",
                  background: color,
                }}
              />
              <span style={{ fontWeight: 700, fontSize: "11px" }}>
                {v.symbol} {pct.toFixed(1)}%
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default PositionPie;
