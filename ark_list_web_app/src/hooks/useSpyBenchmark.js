import { useEffect, useMemo, useState } from "react";
import { toNumber } from "../utils/chartUtils";

const SPY_SYMBOL = "SPY";

const parseDate = (d) => {
  try {
    return new Date(d).getTime();
  } catch (err) {
    return null;
  }
};

export default function useSpyBenchmark(apiBase, anchorDate) {
  const [spyPct, setSpyPct] = useState(null);
  const [spyLoading, setSpyLoading] = useState(false);
  const [spyError, setSpyError] = useState("");

  const anchorTs = useMemo(() => (anchorDate ? parseDate(anchorDate) : null), [anchorDate]);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setSpyLoading(true);
      setSpyError("");
      try {
        const url = new URL(`${apiBase}/tickers/${SPY_SYMBOL}/history`);
        url.searchParams.set("assetclass", "stocks");
        const res = await fetch(url);
        if (!res.ok) throw new Error((await res.text()) || `API returned ${res.status}`);
        const data = await res.json();
        const rows = data.rows || data.points || [];
        const sorted = rows
          .map((p) => ({ ...p, ts: parseDate(p.date) }))
          .filter((p) => Number.isFinite(p.ts))
          .sort((a, b) => a.ts - b.ts);
        if (!sorted.length) throw new Error("No SPY history available");
        const filtered = anchorTs ? sorted.filter((p) => p.ts >= anchorTs) : sorted;
        const series = filtered.length ? filtered : sorted;
        const start = toNumber(series[0]?.close);
        const end = toNumber(series[series.length - 1]?.close);
        if (!start || !end) throw new Error("Missing price data for SPY");
        const pct = ((end - start) / start) * 100;
        if (!cancelled) setSpyPct(pct);
      } catch (err) {
        if (!cancelled) setSpyError(err instanceof Error ? err.message : "Failed to load SPY benchmark");
      } finally {
        if (!cancelled) setSpyLoading(false);
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [anchorTs, apiBase]);

  return { spyPct, spyLoading, spyError };
}
