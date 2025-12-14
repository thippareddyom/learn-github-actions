import React, { useCallback, useEffect, useMemo, useRef } from "react";
import { formatDollars, formatPct, formatDateET } from "./utils/formatters";
import { formatFriendlyRec, formatAiSummary } from "./utils/aiFormatters";
import { computeFallbackPlan } from "./utils/chartUtils";
import { API_BASE, SITE_TITLE, SITE_DESCRIPTION } from "./config";

import usePortfolioState from "./hooks/usePortfolioState";
import useAiPortfolio from "./hooks/useAiPortfolio";
import useTickerSelection from "./hooks/useTickerSelection";
import useSpyBenchmark from "./hooks/useSpyBenchmark";

import CurrentTrades from "./components/CurrentTrades";
import PastTrades from "./components/PastTrades";
import HoldingsPanel from "./components/HoldingsPanel";
import AppHeader from "./components/AppHeader";
import DisclaimerBanner from "./components/DisclaimerBanner";
import PortfolioSection from "./components/PortfolioSection";
import GrowthSection from "./components/GrowthSection";
import ChartSection from "./components/ChartSection";
import TradeErrorAlert from "./components/TradeErrorAlert";
import ScoreCard from "./components/ScoreCard";

export default function App() {
  useEffect(() => {
    if (SITE_TITLE) document.title = SITE_TITLE;
    if (SITE_DESCRIPTION) {
      let meta = document.querySelector('meta[name="description"]');
      if (!meta) {
        meta = document.createElement("meta");
        meta.name = "description";
        document.head.appendChild(meta);
      }
      meta.content = SITE_DESCRIPTION;
    }
  }, []);

  // Portfolio state
  const {
    portfolioLoading,
    portfolioError,
    tradeError,
    cashBalance,
    openPositions,
    closedTrades,
    tradeForm,
    portfolioStats,
    loadPortfolio,
    handleTradeFieldChange,
    handleBuy,
    handleSell,
    handleQuickBuy,
    handleQuickSell,
    setTradeError,
  } = usePortfolioState(API_BASE);

  // AI picks
  const {
    aiRecText,
    aiRecLoading,
    aiRecError,
    aiRecTickers,
    aiRecRows,
    aiTickerInput,
    aiAssetClass,
    setAiAssetClass,
    setAiTickerInput,
    handleAiRun,
    handleAiInputKeyDown,
  } = useAiPortfolio(API_BASE, "stocks");

  const {
    aiRecText: etfRecText,
    aiRecLoading: etfRecLoading,
    aiRecError: etfRecError,
    aiRecTickers: etfRecTickers,
    aiRecRows: etfRecRows,
    aiTickerInput: etfTickerInput,
    aiAssetClass: etfAssetClass,
    setAiAssetClass: setEtfAssetClass,
    setAiTickerInput: setEtfTickerInput,
    handleAiRun: handleEtfRun,
    handleAiInputKeyDown: handleEtfInputKeyDown,
  } = useAiPortfolio(API_BASE, "etf");

  // Ticker selection (chart, rec, holdings)
  const {
    selectedTicker,
    selectedAssetClass,
    filteredPoints,
    tickerPoints,
    tickerLoading,
    tickerError,
    tickerModules,
    recText,
    recError,
    recLoading,
    holdings,
    holdingsError,
    holdingsLoading,
    asOf,
    footnote,
    longBusinessSummary,
    derived,
    earningsDate,
    handleTickerClick,
    setSelectedTicker,
    setSelectedAssetClass,
  } = useTickerSelection(API_BASE);

  // Initial load
  useEffect(() => {
    loadPortfolio();
    handleAiRun();
    handleEtfRun();
    if (!selectedTicker) setSelectedTicker("AAPL");
  }, [handleAiRun, handleEtfRun, loadPortfolio, selectedTicker, setSelectedTicker]);

  const chartRef = useRef(null);
  const chartAnchorRef = useRef(null);

  const handleTickerClickWithScroll = useCallback(
    (sym, asset = "stocks") => {
      handleTickerClick(sym, asset);
      const target = chartAnchorRef.current || chartRef.current;
      if (target) {
        const rect = target.getBoundingClientRect();
        const desiredTop = window.scrollY + rect.top - 220; // offset so chart stays in view
        const maxTop = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
        const top = Math.min(Math.max(0, desiredTop), maxTop);
        window.scrollTo({ top, behavior: "smooth" });
      }
    },
    [handleTickerClick],
  );

  const openSymbols = useMemo(() => openPositions.map((p) => p.symbol), [openPositions]);

  const recFallback = useMemo(
    () => computeFallbackPlan(filteredPoints.length ? filteredPoints : tickerPoints),
    [filteredPoints, tickerPoints],
  );

  const stockRowsMapped = useMemo(() => {
    if (!Array.isArray(aiRecRows)) return [];
    return aiRecRows.map((row) => {
      const next = { ...row };
      if (row.Reason && !row.reason) next.reason = row.Reason;
      return next;
    });
  }, [aiRecRows]);

  const friendlyRec = useMemo(() => formatFriendlyRec(recText), [recText]);
  const aiSummary = useMemo(() => formatAiSummary(aiRecRows, aiRecText), [aiRecRows, aiRecText]);
  const etfSummary = useMemo(() => formatAiSummary(etfRecRows, etfRecText), [etfRecRows, etfRecText]);

  const etfRowsMapped = useMemo(() => {
    if (!Array.isArray(etfRecRows)) return [];
    return etfRecRows.map((row) => {
      const next = { ...row };
      if (row.upside !== undefined) {
        next.upside = row.upside;
        next.UpsidePct = row.upside;
      }
      if (row.UpsidePct !== undefined) {
        next.upside = row.UpsidePct;
        next.UpsidePct = row.UpsidePct;
      }
      if (row.category) next.sector = row.category;
      if (row.beta3Year !== undefined) next.beta = row.beta3Year;
      if (row.trailingPE !== undefined) next.forwardPE = row.trailingPE;
      if (row.Reason && !row.reason) next.reason = row.Reason;
      return next;
    });
  }, [etfRecRows]);

  const scoreItems = useMemo(() => {
    const m = tickerModules || {};
    const summary = (m.summaryDetail || m.summary_detail || {}) || {};
    const stats = (m.defaultKeyStatistics || m.defaultKey_statistics || {}) || {};
    const fin = (m.financialData || m.financial_data || {}) || {};
    const techRsi = Array.isArray(derived?.rsiValues) ? derived.rsiValues.at(-1) : null;
    const ma21 = Array.isArray(derived?.maVals) ? derived.maVals.at(-1) : null;

    const fmt = (val, digits = 2, suffix = "") => {
      if (val === null || val === undefined) return null;
      const num = Number(val);
      if (!Number.isFinite(num)) return null;
      return `${num.toFixed(digits)}${suffix}`;
    };

    return [
      { label: "P/E", value: fmt(summary.trailingPE ?? stats.trailingPE) },
      { label: "Forward P/E", value: fmt(stats.forwardPE ?? summary.forwardPE ?? fin.forwardPE) },
      { label: "EPS (ttm)", value: fmt(stats.trailingEps ?? stats.trailingEPS) },
      { label: "EPS next Q", value: fmt(stats.epsEstimateNextQuarter ?? stats.epsQuarterlyGrowth) },
      { label: "Target Price", value: fmt(fin.targetMeanPrice, 2) },
      { label: "Recom", value: fmt(fin.recommendationMean, 2) },
      { label: "RSI (14)", value: fmt(techRsi, 2) },
      { label: "SMA21", value: fmt(ma21, 2) },
      { label: "Beta", value: fmt(summary.beta ?? stats.beta, 2) },
      { label: "Short Float %", value: fmt(stats.shortPercentOfFloat, 2, "%") },
      { label: "Short Ratio", value: fmt(stats.shortRatio, 2) },
    ].filter((item) => item.value !== null);
  }, [derived?.maVals, derived?.rsiValues, tickerModules]);

  const earliestDate = useMemo(() => {
    const dates = [
      ...openPositions.map((p) => p.addedAt).filter(Boolean),
      ...closedTrades.map((t) => t.entry).filter(Boolean),
    ];
    const ts = dates
      .map((d) => {
        try {
          return new Date(d).getTime();
        } catch {
          return null;
        }
      })
      .filter((n) => Number.isFinite(n))
      .sort((a, b) => a - b);
    if (!ts.length) return null;
    return new Date(ts[0]).toISOString();
  }, [closedTrades, openPositions]);

  const { spyPct, spyLoading, spyError } = useSpyBenchmark(API_BASE, earliestDate);

  return (
    <main className="page">
      <AppHeader
        openPositions={openPositions}
        cashBalance={cashBalance}
        title={SITE_TITLE || "SwingEdge"}
        subtitle={SITE_DESCRIPTION}
      />
      <DisclaimerBanner />

      <PortfolioSection
        cashBalance={cashBalance}
        portfolioStats={portfolioStats}
        portfolioLoading={portfolioLoading}
        portfolioError={portfolioError}
        tradeError={tradeError}
        openPositions={openPositions}
        onSelectPosition={handleTickerClickWithScroll}
        formatDollars={formatDollars}
        formatPct={formatPct}
        benchmarkPct={spyPct}
        benchmarkLabel="SPY"
        benchmarkLoading={spyLoading}
        benchmarkError={spyError}
      />

      <GrowthSection
        aiRecTickers={aiRecTickers}
        aiAssetClass={aiAssetClass}
        aiTickerInput={aiTickerInput}
        onAssetClassChange={setAiAssetClass}
        onTickerInputChange={setAiTickerInput}
        onRun={handleAiRun}
        onTickerClick={handleTickerClickWithScroll}
        onQuickBuy={(sym) => handleQuickBuy(sym)}
        onTickerInputKeyDown={handleAiInputKeyDown}
        openSymbols={openSymbols}
        aiSummary={aiSummary}
        aiRecError={aiRecError}
        aiRecLoading={aiRecLoading}
        aiRecRows={stockRowsMapped}
        title="Growth portfolio picks"
        eyebrow="Deterministic selection (simulated)"
      />

      <GrowthSection
        aiRecTickers={etfRecTickers}
        aiAssetClass={etfAssetClass}
        aiTickerInput={etfTickerInput}
        onAssetClassChange={setEtfAssetClass}
        onTickerInputChange={setEtfTickerInput}
        onRun={handleEtfRun}
        onTickerClick={handleTickerClickWithScroll}
        onQuickBuy={(sym) => handleQuickBuy(sym)}
        onTickerInputKeyDown={handleEtfInputKeyDown}
        openSymbols={openSymbols}
        aiSummary={etfSummary}
        aiRecError={etfRecError}
        aiRecLoading={etfRecLoading}
        title="ETF portfolio picks"
        eyebrow="Deterministic selection (simulated) - ETF"
        upsideLabel="Upside Target %"
        upsideKey="UpsidePct"
        hideAssetSelect
        assetOptions={[{ value: "etf", label: "etf" }]}
        aiRecRows={etfRowsMapped}
      />

      <section className="panel">
        <CurrentTrades
          openPositions={openPositions}
          onSelectTicker={handleTickerClickWithScroll}
          formatDollars={formatDollars}
          formatPct={formatPct}
          formatDate={formatDateET}
          tradeForm={tradeForm}
          onFieldChange={handleTradeFieldChange}
          onBuy={handleBuy}
          onSell={handleSell}
          onQuickSell={handleQuickSell}
        />
      </section>

      <section className="panel">
        <PastTrades
          closedTrades={closedTrades}
          onSelectTicker={handleTickerClickWithScroll}
          formatDollars={formatDollars}
          formatPct={formatPct}
          formatDate={formatDateET}
        />
      </section>

      <ChartSection
        anchorRef={chartAnchorRef}
        sectionRef={chartRef}
        selectedTicker={selectedTicker}
        selectedAssetClass={selectedAssetClass}
        tickerPoints={tickerPoints}
        recText={recText}
        recLoading={recLoading}
        recError={recError}
        recFallback={recFallback}
        setSelectedTicker={setSelectedTicker}
        setSelectedAssetClass={setSelectedAssetClass}
        tickerLoading={tickerLoading}
        tickerError={tickerError}
        friendlyRec={friendlyRec}
        earningsDate={earningsDate}
      />
      {(scoreItems.length > 0 || longBusinessSummary) && (
        <section className="panel">
          <ScoreCard title={`${selectedTicker} metrics`} items={scoreItems} />
          {longBusinessSummary && (
            <div className="ai-box" style={{ marginTop: "0.75rem" }}>
              <p className="eyebrow">{selectedTicker} profile</p>
              <p>{longBusinessSummary}</p>
            </div>
          )}
        </section>
      )}
     

      {selectedAssetClass === "etf" && (
        <HoldingsPanel
          title={`${selectedTicker} holdings`}
          asOf={asOf}
          loading={holdingsLoading}
          error={holdingsError}
          rows={holdings}
          footnote={footnote}
        />
      )}

      <TradeErrorAlert message={tradeError} onDismiss={() => setTradeError("")} />
      <DisclaimerBanner />
    </main>
  );
}
