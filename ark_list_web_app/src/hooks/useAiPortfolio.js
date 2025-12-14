import { useCallback, useMemo, useState } from "react";
import { fetchAiPortfolio } from "../api/ai";

export default function useAiPortfolio(apiBase, initialAssetClass = "stocks") {
  const [aiRecText, setAiRecText] = useState("");
  const [aiRecLoading, setAiRecLoading] = useState(false);
  const [aiRecError, setAiRecError] = useState("");
  const [aiRecTickers, setAiRecTickers] = useState([]);
  const [aiRecRows, setAiRecRows] = useState([]);
  const [aiTickerInput, setAiTickerInput] = useState("");
  const [aiAssetClass, setAiAssetClass] = useState(initialAssetClass);
  const aiInputSymbols = useMemo(
    () =>
      aiTickerInput
        .split(",")
        .map((t) => t.trim().toUpperCase())
        .filter(Boolean),
    [aiTickerInput],
  );

  const handleAiInputKeyDown = useCallback(
    (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
      }
    },
    [],
  );

  const handleAiRun = useCallback(async () => {
    setAiRecLoading(true);
    setAiRecError("");
    setAiRecText("");
    setAiRecTickers([]);
    setAiRecRows([]);
    try {
      const data = await fetchAiPortfolio(aiAssetClass, aiInputSymbols);
      if (Array.isArray(data?.rows)) {
        setAiRecRows(data.rows);
      }
      if (data?.recommendation) {
        setAiRecText(data.recommendation);
      }
      const tickersSource = Array.isArray(data?.tickers_all)
        ? data.tickers_all
        : Array.isArray(data?.tickers)
          ? data.tickers
          : [];
      const uniqTickers = Array.from(
        new Set(
          tickersSource.map((t) => (t == null ? "" : String(t).toUpperCase().trim())).filter(Boolean),
        ),
      );
      setAiRecTickers(uniqTickers);
    } catch (err) {
      setAiRecError(err instanceof Error ? err.message : "Failed to fetch");
    } finally {
      setAiRecLoading(false);
    }
  }, [aiAssetClass, aiInputSymbols]);

  return {
    aiRecText,
    aiRecLoading,
    aiRecError,
    aiRecTickers,
    aiRecRows,
    aiTickerInput,
    aiAssetClass,
    aiInputSymbols,
    setAiAssetClass,
    setAiTickerInput,
    handleAiRun,
    handleAiInputKeyDown,
  };
}
