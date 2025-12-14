import { useEffect, useState } from "react";

const useTickerHistory = (apiBase, ticker, assetClass, refreshToken = 0) => {
  const [points, setPoints] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [latest, setLatest] = useState(null);
  const [modules, setModules] = useState(null);

  useEffect(() => {
    let cancelled = false;
    if (!ticker) {
      setPoints([]);
      setError("");
      setLatest(null);
      setModules(null);
      return undefined;
    }

    async function load() {
      setLoading(true);
      setError("");
      setModules(null);
      const url = new URL(`${apiBase}/tickers/${ticker}/history`);
      if (assetClass) {
        url.searchParams.set("assetclass", assetClass);
      }

      let attempt = 0;
      const maxAttempts = 6;
      let fetched = false;
      while (attempt < maxAttempts && !fetched && !cancelled) {
        try {
          const response = await fetch(url, { cache: "no-store" });
          if (response.status === 404) {
            attempt += 1;
            if (attempt < maxAttempts) {
              await new Promise((resolve) => setTimeout(resolve, 1200));
              continue;
            }
            throw new Error("Data not available yet");
          }
          if (!response.ok) {
            throw new Error(`API returned ${response.status}`);
          }
          const data = await response.json();
          const fetchedPoints = Array.isArray(data?.points) ? data.points : [];
          if (fetchedPoints.length === 0 && attempt < maxAttempts - 1) {
            attempt += 1;
            await new Promise((resolve) => setTimeout(resolve, 1200));
            continue;
          }
          if (!cancelled) {
            setPoints(fetchedPoints);
            setLatest(data?.latest || null);
            setModules(data?.modules || null);
            setError("");
          }
          fetched = true;
        } catch (err) {
          if (attempt >= maxAttempts - 1 || cancelled) {
            if (!cancelled) {
              setPoints([]);
              setLatest(null);
              setModules(null);
              setError(err instanceof Error ? err.message : "Failed to load price history");
            }
            break;
          }
          attempt += 1;
          await new Promise((resolve) => setTimeout(resolve, 1200));
        }
      }
      if (!cancelled) {
        setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [apiBase, ticker, assetClass, refreshToken]);

  return { points, loading, error, latest, modules };
};

export default useTickerHistory;
