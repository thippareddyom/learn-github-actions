import React from "react";
import GrowthPicks from "./GrowthPicks";

const GrowthSection = ({
  aiRecRows,
  aiRecTickers,
  aiAssetClass,
  aiTickerInput,
  onAssetClassChange,
  onTickerInputChange,
  onRun,
  onTickerClick,
  onQuickBuy,
  onTickerInputKeyDown,
  openSymbols,
  aiSummary,
  aiRecError,
  aiRecLoading,
  title,
  eyebrow,
  upsideLabel = "Upside Target %",
  upsideKey = "upside",
  hideAssetSelect = false,
  assetOptions,
}) => (
  <section className="panel">
    <GrowthPicks
      deterministicTable={aiRecRows}
      processedTickers={aiRecTickers}
      aiAssetClass={aiAssetClass}
      aiTickerInput={aiTickerInput}
      onAssetClassChange={onAssetClassChange}
      onTickerInputChange={onTickerInputChange}
      onRun={onRun}
      onTickerClick={onTickerClick}
      onBuy={onQuickBuy}
      onTickerInputKeyDown={onTickerInputKeyDown}
      openTickers={openSymbols}
      title={title}
      eyebrow={eyebrow}
      upsideLabel={upsideLabel}
      upsideKey={upsideKey}
      hideAssetSelect={hideAssetSelect}
      assetOptions={assetOptions}
    />
    {aiSummary && (
      <div className="ai-box" style={{ marginTop: "0.5rem" }}>
        <p className="muted">AI summary (hypothetical, not advice):</p>
        <p>{aiSummary}</p>
      </div>
    )}
    {aiRecError && <p className="status status--error">{aiRecError}</p>}
    {aiRecLoading && <p className="status status--loading">Loading AI picksƒ?İ</p>}
  </section>
);

export default GrowthSection;
