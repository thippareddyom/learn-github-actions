import React from "react";

const ScoreCard = ({ title = "Score Card", items = [] }) => {
  const visible = items.filter((item) => item.value !== null && item.value !== undefined);
  if (!visible.length) return null;
  return (
    <div className="score-card">
      <p className="eyebrow" style={{ marginBottom: "6px" }}>
        {title}
      </p>
      <div className="score-card__grid">
        {visible.map((item) => (
          <div key={item.label} className="score-card__item">
            <div className="score-card__label">{item.label}</div>
            <div className="score-card__value">{item.value}</div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default ScoreCard;
