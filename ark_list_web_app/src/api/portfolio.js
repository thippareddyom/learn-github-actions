import { API_BASE } from "../config";

const base = API_BASE;

export const getPortfolio = async () => {
  const res = await fetch(`${base}/portfolio`, { cache: "no-store" });
  if (!res.ok) throw new Error((await res.text()) || `API returned ${res.status}`);
  return res.json();
};

export const buyPosition = async (payload) => {
  const res = await fetch(`${base}/portfolio/buy`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error((await res.text()) || `API returned ${res.status}`);
  return res.json();
};

export const sellPosition = async (payload) => {
  const res = await fetch(`${base}/portfolio/sell`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error((await res.text()) || `API returned ${res.status}`);
  return res.json();
};
