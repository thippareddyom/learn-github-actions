import { API_BASE } from "../config";

const base = API_BASE;

export const fetchAiPortfolio = async (assetClass, symbols) => {
  const url = new URL(`${base}/ai/portfolio`);
  if (assetClass) url.searchParams.set("assetclass", assetClass);
  if (symbols?.length) {
    const joined = symbols.join(",");
    url.searchParams.set("symbols", joined);
    url.searchParams.set("tickers", joined);
  }
  const res = await fetch(url.toString(), { cache: "no-store" });
  if (!res.ok) throw new Error((await res.text()) || `API returned ${res.status}`);
  return res.json();
};

export const fetchAiRecommendation = async ({ symbol, assetclass, modules, rows }) => {
  const res = await fetch(`${base}/ai/recommendation`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbol, assetclass, modules, rows }),
  });
  if (!res.ok) throw new Error((await res.text()) || `API returned ${res.status}`);
  return res.json();
};
