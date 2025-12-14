import { useCallback, useEffect, useMemo, useState } from "react";
import { computeRSI, computeSMA, toNumber } from "../utils/chartUtils";

export default function useTickerSelection(apiBase) {
  const [selectedTicker, setSelectedTicker] = useState("");
  const [selectedAssetClass, setSelectedAssetClass] = useState("stocks");
  const [range, setRange] = useState("6M");
  const [tickerPoints, setTickerPoints] = useState([]);
  const [tickerModules, setTickerModules] = useState(null);
  const [earningsDate, setEarningsDate] = useState("");
  const [tickerLoading, setTickerLoading] = useState(false);
  const [tickerError, setTickerError] = useState("");
  const [recText, setRecText] = useState("");
  const [recError, setRecError] = useState("");
  const [recLoading, setRecLoading] = useState(false);
  const [asOf, setAsOf] = useState("");
  const [holdings, setHoldings] = useState([]);
  const [holdingsError, setHoldingsError] = useState("");
  const [holdingsLoading, setHoldingsLoading] = useState(false);
  const [footnote, setFootnote] = useState("");
  const [tickerFetchNonce, setTickerFetchNonce] = useState(0);

  const handleTickerClick = useCallback((sym, asset = "stocks") => {
    setSelectedTicker(sym);
    setSelectedAssetClass(asset);
    setTickerFetchNonce((n) => n + 1);
  }, []);

  // Load holdings for ETF
  useEffect(() => {
    const loadHoldings = async () => {
      if (!selectedTicker || selectedAssetClass !== "etf") return;
      setHoldingsLoading(true);
      setHoldingsError("");
      try {
        const res = await fetch(`${apiBase}/funds/${selectedTicker}/holdings`);
        if (!res.ok) throw new Error(await res.text() || `API returned ${res.status}`);
        const data = await res.json();
        setHoldings(data.rows || []);
        setAsOf(data.date || "");
        setFootnote(data.footnote || "");
      } catch (err) {
        setHoldingsError(err instanceof Error ? err.message : "Failed to load holdings");
      } finally {
        setHoldingsLoading(false);
      }
    };
    loadHoldings();
  }, [apiBase, selectedTicker, selectedAssetClass]);

  // Load ticker history/modules/recommendation
  useEffect(() => {
    if (!selectedTicker) return;
    let cancelled = false;
    const load = async () => {
      setTickerLoading(true);
      setTickerError("");
      setRecError("");
      setRecText("");
      try {
        const url = new URL(`${apiBase}/tickers/${selectedTicker}/history`);
        if (selectedAssetClass) url.searchParams.set("assetclass", selectedAssetClass);
        const res = await fetch(url);
        if (!res.ok) throw new Error(await res.text() || `API returned ${res.status}`);
        const data = await res.json();
        if (cancelled) return;
        setTickerPoints(data.rows || data.points || []);
        setTickerModules(data.modules || null);
        const latest = data.latest || {};
        const earn = latest.earningsDate || latest.earningsdate || "";
        setEarningsDate(earn || "");
      } catch (err) {
        if (!cancelled) setTickerError(err instanceof Error ? err.message : "Failed to load ticker history");
      } finally {
        if (!cancelled) setTickerLoading(false);
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [apiBase, selectedTicker, selectedAssetClass, tickerFetchNonce]);

  useEffect(() => {
    if (!selectedTicker) return;
    let cancelled = false;
    const loadRec = async () => {
      setRecLoading(true);
      setRecError("");
      setRecText("");
      try {
        const url = new URL(`${apiBase}/tickers/${selectedTicker}/recommendation`);
        if (selectedAssetClass) url.searchParams.set("assetclass", selectedAssetClass);
        const res = await fetch(url, { cache: "no-store" });
        if (!res.ok) throw new Error((await res.text()) || `API returned ${res.status}`);
        const data = await res.json();
        const neutralize = (text = "") => text.replace(/buy\s*:/gi, "Entry:");
        if (!cancelled) setRecText(neutralize(data?.recommendation || ""));
      } catch (err) {
        if (!cancelled) {
          setRecError(err instanceof Error ? err.message : "Failed to load recommendation");
        }
      } finally {
        if (!cancelled) setRecLoading(false);
      }
    };
    loadRec();
    return () => {
      cancelled = true;
    };
  }, [apiBase, selectedTicker, selectedAssetClass]);

  // Derive long business summary
  const longBusinessSummary = useMemo(() => {
    if (!tickerModules || !selectedTicker) return "";
    const sym = selectedTicker.toUpperCase();
    let profile = tickerModules.assetProfile;
    if (!profile) return "";
    if (profile[sym]) {
      profile = profile[sym];
    } else if (profile[sym?.toLowerCase?.()]) {
      profile = profile[sym.toLowerCase()];
    } else if (typeof profile === "object" && !Array.isArray(profile)) {
      const vals = Object.values(profile);
      if (vals.length === 1) {
        profile = vals[0];
      }
    }
    return profile?.longBusinessSummary || "";
  }, [selectedTicker, tickerModules]);

  // Range filter
  const filteredPoints = useMemo(() => {
    if (!tickerPoints.length) return [];
    if (range === "ALL") return tickerPoints;
    const cutoff = (() => {
      const lastDate = tickerPoints[tickerPoints.length - 1]?.date;
      if (!lastDate) return 0;
      const last = new Date(lastDate);
      const map = { "1D": 1, "5D": 5, "1M": 30, "3M": 90, "6M": 180, YTD: 366, "1Y": 366 };
      const days = map[range] || 180;
      return last.setDate(last.getDate() - days);
    })();
    return tickerPoints.filter((p) => {
      const d = new Date(p.date);
      return d.getTime() >= cutoff;
    });
  }, [tickerPoints, range]);

  // RSI/MA helpers for chart
  const derived = useMemo(() => {
    const closes = filteredPoints.map((p) => toNumber(p.close)).filter((v) => v != null);
    const maVals = computeSMA(filteredPoints.map((p) => toNumber(p.close) ?? 0), 21);
    let rsiValues = filteredPoints.map((_, i) => {
      const window = filteredPoints.slice(Math.max(0, i - 13), i + 1).map((p) => toNumber(p.close) ?? 0);
      return computeRSI(window, 14);
    });
    if (rsiValues.every((v) => v == null)) {
      rsiValues = computeRSI(closes, 14);
    }
    return { maVals, rsiValues };
  }, [filteredPoints]);

  return {
    selectedTicker,
    selectedAssetClass,
    range,
    tickerPoints,
    filteredPoints,
    tickerModules,
    tickerLoading,
    tickerError,
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
    setRange,
    handleTickerClick,
    setSelectedTicker,
    setSelectedAssetClass,
  };
}
