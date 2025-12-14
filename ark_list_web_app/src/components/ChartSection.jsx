import React from "react";
import LineChart from "./LineChart";

const ChartSection = ({
  anchorRef,
  sectionRef,
  selectedTicker,
  selectedAssetClass,
  tickerPoints,
  recText,
  recLoading,
  recError,
  recFallback,
  setSelectedTicker,
  setSelectedAssetClass,
  tickerLoading,
  tickerError,
  friendlyRec,
  longBusinessSummary,
  earningsDate,
}) => (
  <section className="panel" ref={sectionRef}>
    <div ref={anchorRef} className="chart-anchor" />
    <LineChart
      ticker={selectedTicker}
      selectedAssetClass={selectedAssetClass}
      points={tickerPoints}
      recText={recText}
      recLoading={recLoading}
      recError={recError || tickerError}
      recFallback={recFallback}
      earningsDate={earningsDate}
      onSearchTicker={(sym, asset) => {
        setSelectedTicker(sym);
        if (asset) setSelectedAssetClass(asset);
      }}
    />
    {tickerLoading && <p className="status status--loading">Loading chartƒ?İ</p>}
    {tickerError && <p className="status status--error">{tickerError}</p>}
    {longBusinessSummary && (
      <div className="ai-box" style={{ marginTop: "0.75rem" }}>
        <p className="eyebrow">{selectedTicker} profile</p>
        <p>{longBusinessSummary}</p>
      </div>
    )}
  </section>
);

export default ChartSection;
