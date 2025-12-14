import React from "react";
import DonutLogo from "./DonutLogo";

const AppHeader = ({ openPositions, cashBalance, title, subtitle }) => (
  <header className="site-header">
    <DonutLogo openPositions={openPositions} cashBalance={cashBalance} label="SE AI" fallbackLabel="SE AI" />
    <div>
      <div className="site-header__title">{title || "SwingEdge"}</div>
      {subtitle && <div className="site-header__subtitle">{subtitle}</div>}
    </div>
  </header>
);

export default AppHeader;
