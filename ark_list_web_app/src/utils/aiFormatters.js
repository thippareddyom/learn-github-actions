export const formatFriendlyRec = (recText) => {
  if (!recText) return "";
  const m = recText.match(
    /(Buy|Entry zone):\s*([\d.-]+)\s*(?:-|to)?\s*([\d.-]+)?\s*\|?\s*Target:\s*([\d.]+)\s*\|?\s*Stop:\s*([\d.]+)\s*\|?\s*Note:\s*(.+)/i,
  );
  if (!m) return recText;
  const [, , entry1, entry2Maybe, target, stop, noteRaw] = m;
  const entryLow = Number(entry1);
  const entryHigh = entry2Maybe ? Number(entry2Maybe) : entryLow;
  const targetNum = Number(target);
  const midEntry =
    Number.isFinite(entryLow) && Number.isFinite(entryHigh)
      ? (entryLow + entryHigh) / 2
      : Number.isFinite(entryLow)
      ? entryLow
      : null;
  const pct = midEntry && targetNum ? ((targetNum - midEntry) / midEntry) * 100 : null;
  const note = noteRaw?.trim() || "";
  return (
    `Plan: entry near ${Number.isFinite(entryLow) ? entryLow.toFixed(2) : entry1}` +
    `${Number.isFinite(entryHigh) && entryHigh !== entryLow ? `-${entryHigh.toFixed(2)}` : ""}, ` +
    `target ${targetNum ? targetNum.toFixed(2) : target}` +
    `${pct != null ? ` (~${pct.toFixed(1)}% spread)` : ""}, ` +
    `stop ${Number(stop).toFixed(2)}. ${note}`
  );
};

export const formatAiSummary = (rows = [], fallbackText = "") => {
  if (rows.length) {
    const top = rows.slice(0, 3);
    const parts = top.map((r) =>
      `${r.ticker} (${Number.isFinite(r.upside) ? `${r.upside.toFixed(1)}%` : "n/a"})`,
    );
    return `Top picks: ${parts.join(", ")}.`;
  }
  if (fallbackText) return fallbackText;
  return "AI summary not available yet.";
};
