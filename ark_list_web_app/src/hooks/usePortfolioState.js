import { useCallback, useMemo, useState } from "react";
import { formatDateET } from "../utils/formatters";
import { buyPosition, getPortfolio, sellPosition } from "../api/portfolio";

const sizeMap = { "1": 0.1, "1/2": 0.05, "1/4": 0.025, auto: 0.1 };

const mapPosition = (p) => ({
  id: p.id || `${p.symbol || ""}-${p.added_at || Date.now()}`,
  symbol: p.symbol || p.ticker || "",
  assetclass: p.assetclass || p.assetClass || "stocks",
  sizeLabel: p.size_label || p.sizeLabel || "",
  shares: Number(p.shares) || 0,
  entryPrice: Number(p.entry_price ?? p.entryPrice) || 0,
  markPrice:
    Number(
      p.price ??
        p.mark_price ??
        p.markPrice ??
        p.current_price ??
        p.entry_price ??
        p.entryPrice,
    ) || 0,
  addedAt: p.added_at || p.addedAt || "",
});

const mapClosed = (t) => ({
  symbol: t.symbol || "",
  entry: t.entry || "",
  exit: t.exit || "",
  entryPrice: Number(t.entry_price ?? t.entryPrice) || 0,
  exitPrice: Number(t.exit_price ?? t.exitPrice) || 0,
  shares: Number(t.shares) || 0,
  tradeBalance: Number(t.trade_balance ?? t.tradeBalance) || 0,
  gainPct: Number(t.gain_pct ?? t.gainPct) || 0,
});

export default function usePortfolioState(apiBase) {
  const [portfolioLoading, setPortfolioLoading] = useState(false);
  const [portfolioError, setPortfolioError] = useState("");
  const [tradeError, setTradeError] = useState("");
  const [cashBalance, setCashBalance] = useState(0);
  const [initialEquity, setInitialEquity] = useState(100000);
  const [openPositions, setOpenPositions] = useState([]);
  const [closedTrades, setClosedTrades] = useState([]);
  const [tradeForm, setTradeForm] = useState({
    symbol: "",
    positionSize: "1/2",
    entryPrice: "",
    markPrice: "",
    exitPrice: "",
  });

  const updateMarksFromApi = useCallback(
    async (positions) => {
      const updated = await Promise.all(
        positions.map(async (p) => {
          if (!p.symbol) return p;
          try {
            const asset = p.assetclass || "stocks";
            const url = new URL(`${apiBase}/tickers/${p.symbol}/history`);
            if (asset) url.searchParams.set("assetclass", asset);
            const res = await fetch(url);
            if (!res.ok) return p;
            const payload = await res.json();
            const latestClose =
              payload?.latest?.close ??
              (Array.isArray(payload?.points) ? payload.points.at(-1)?.close : null) ??
              (Array.isArray(payload?.rows) ? payload.rows.at(-1)?.close : null);
            if (!Number.isFinite(Number(latestClose))) return p;
            return { ...p, markPrice: Number(latestClose) };
          } catch (err) {
            return p;
          }
        }),
      );
      setOpenPositions(updated);
    },
    [apiBase],
  );

  const applyPortfolio = useCallback(
    (data) => {
      if (!data) return;
      setInitialEquity(Number(data.initial_equity ?? data.initialEquity ?? 100000) || 100000);
      setCashBalance(Number(data.cash_balance ?? data.cashBalance) || 0);
      const mappedPositions = Array.isArray(data.open_positions) ? data.open_positions.map(mapPosition) : [];
      setOpenPositions(mappedPositions);
      // Refresh mark prices with the latest closes so P/L and pie % reflect current values
      updateMarksFromApi(mappedPositions);
      setClosedTrades(Array.isArray(data.closed_trades) ? data.closed_trades.map(mapClosed) : []);
    },
    [updateMarksFromApi],
  );

  const loadPortfolio = useCallback(async () => {
    setPortfolioLoading(true);
    setPortfolioError("");
    try {
      const data = await getPortfolio();
      applyPortfolio(data);
    } catch (err) {
      setPortfolioError(err instanceof Error ? err.message : "Failed to load portfolio");
    } finally {
      setPortfolioLoading(false);
    }
  }, [apiBase, applyPortfolio]);

  const handleTradeFieldChange = useCallback((key, value) => {
    setTradeForm((prev) => ({ ...prev, [key]: value }));
  }, []);

  const handleBuy = useCallback(async () => {
    setTradeError("");
    const sym = tradeForm.symbol.trim().toUpperCase();
    const entry = Number(tradeForm.entryPrice);
    const mark = tradeForm.markPrice ? Number(tradeForm.markPrice) : entry;
    const fraction = sizeMap[tradeForm.positionSize] ?? 0.1;
    if (!sym) return setTradeError("Enter a symbol to trade.");
    if (!Number.isFinite(entry) || entry <= 0) return setTradeError("Entry price must be greater than zero.");

    // equity = cash + marked open positions
    const marketValue = openPositions.reduce(
      (acc, p) => acc + p.shares * (Number.isFinite(p.markPrice) ? p.markPrice : p.entryPrice),
      0,
    );
    const equity = cashBalance + marketValue;
    const allocation = equity * fraction;
    if (allocation <= 0 || allocation > cashBalance) {
      return setTradeError("Not enough cash to fund this position size based on equity.");
    }
    try {
      const data = await buyPosition({
        symbol: sym,
        position_size: tradeForm.positionSize,
        entry_price: entry,
        mark_price: Number.isFinite(mark) && mark > 0 ? mark : entry,
      });
      applyPortfolio(data);
      setTradeForm((prev) => ({ ...prev, entryPrice: "", markPrice: "" }));
    } catch (err) {
      setTradeError(err instanceof Error ? err.message : "Buy failed");
    }
  }, [apiBase, applyPortfolio, cashBalance, openPositions, tradeForm]);

  const handleSell = useCallback(async () => {
    setTradeError("");
    const sym = tradeForm.symbol.trim().toUpperCase();
    const exit = Number(tradeForm.exitPrice);
    if (!sym) return setTradeError("Enter a symbol to sell.");
    if (!Number.isFinite(exit) || exit <= 0) return setTradeError("Exit price must be greater than zero.");
    const existing = openPositions.find((p) => p.symbol === sym);
    if (!existing) return setTradeError("No open position found for that symbol.");
    try {
      const data = await sellPosition({ symbol: sym, exit_price: exit });
      applyPortfolio(data);
      setTradeForm((prev) => ({ ...prev, exitPrice: "" }));
    } catch (err) {
      setTradeError(err instanceof Error ? err.message : "Sell failed");
    }
  }, [apiBase, applyPortfolio, openPositions, tradeForm]);

  const handleQuickBuy = useCallback(async (symbol) => {
    if (!symbol) return;
    setTradeError("");
    try {
      const data = await buyPosition({ symbol: symbol.toUpperCase(), position_size: "auto" });
      applyPortfolio(data);
    } catch (err) {
      setTradeError(err instanceof Error ? err.message : "Buy failed");
    }
  }, [apiBase, applyPortfolio]);

  const handleQuickSell = useCallback(async (symbol) => {
    if (!symbol) return;
    setTradeError("");
    try {
      const data = await sellPosition({ symbol: symbol.toUpperCase() });
      applyPortfolio(data);
    } catch (err) {
      setTradeError(err instanceof Error ? err.message : "Sell failed");
    }
  }, [apiBase, applyPortfolio]);

  const portfolioStats = useMemo(() => {
    const marketValue = openPositions.reduce(
      (acc, p) => acc + p.shares * (Number.isFinite(p.markPrice) ? p.markPrice : p.entryPrice),
      0,
    );
    const invested = openPositions.reduce((acc, p) => acc + p.shares * p.entryPrice, 0);
    const equity = cashBalance + marketValue;
    const totalPct = initialEquity ? ((equity - initialEquity) / initialEquity) * 100 : 0;
    return { marketValue, invested, equity, totalPct };
  }, [openPositions, cashBalance, initialEquity]);

  return {
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
    formatDateET,
  };
}
