export const formatDollars = (val) =>
  Number.isFinite(val)
    ? `$${Number(val).toLocaleString("en-US", { maximumFractionDigits: 2 })}`
    : "-";

export const formatPct = (val) =>
  Number.isFinite(val)
    ? `${val >= 0 ? "+" : ""}${val.toFixed(2)}%`
    : "-";

export const formatDateET = (val) => {
  if (!val) return "-";
  const toDate = () => {
    const d1 = new Date(val);
    if (!Number.isNaN(d1.getTime())) return d1;
    const cleaned = String(val).replace(/ [A-Za-z]+ Standard Time$/i, "");
    const d2 = new Date(cleaned);
    if (!Number.isNaN(d2.getTime())) return d2;
    return null;
  };
  const d = toDate();
  if (!d || Number.isNaN(d.getTime())) return val;
  return d.toLocaleDateString("en-US", {
    timeZone: "America/New_York",
    month: "2-digit",
    day: "2-digit",
    year: "2-digit",
  });
};

export const formatDateShort = (val) => {
  if (!val) return "-";
  const d = new Date(val);
  if (Number.isNaN(d.getTime())) return "-";
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "2-digit" });
};
