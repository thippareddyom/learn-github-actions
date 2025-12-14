export const computeSMA = (values, window = 21) => {
  const result = Array(values.length).fill(null);
  let sum = 0;
  for (let i = 0; i < values.length; i += 1) {
    sum += values[i];
    if (i >= window - 1) {
      result[i] = sum / window;
      sum -= values[i - window + 1];
    }
  }
  return result;
};

export const computeRSI = (values, period = 14) => {
  if (values.length < period + 1) return Array(values.length).fill(null);
  const gains = [];
  const losses = [];
  for (let i = 1; i < values.length; i += 1) {
    const diff = values[i] - values[i - 1];
    gains.push(diff > 0 ? diff : 0);
    losses.push(diff < 0 ? -diff : 0);
  }
  const rsi = Array(values.length).fill(null);
  let avgGain = gains.slice(0, period).reduce((a, b) => a + b, 0) / period;
  let avgLoss = losses.slice(0, period).reduce((a, b) => a + b, 0) / period;
  const rsFirst = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);
  rsi[period] = rsFirst;
  for (let i = period + 1; i < values.length; i += 1) {
    avgGain = (avgGain * (period - 1) + gains[i - 1]) / period;
    avgLoss = (avgLoss * (period - 1) + losses[i - 1]) / period;
    const rs = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);
    rsi[i] = rs;
  }
  return rsi;
};

export const computeRegression = (xs, ys) => {
  const n = Math.min(xs.length, ys.length);
  if (n === 0) return null;
  const meanX = xs.reduce((a, b) => a + b, 0) / n;
  const meanY = ys.reduce((a, b) => a + b, 0) / n;
  let num = 0;
  let den = 0;
  for (let i = 0; i < n; i += 1) {
    num += (xs[i] - meanX) * (ys[i] - meanY);
    den += (xs[i] - meanX) ** 2;
  }
  const slope = den === 0 ? 0 : num / den;
  const intercept = meanY - slope * meanX;
  const preds = xs.map((x) => slope * x + intercept);
  const residuals = ys.map((y, i) => y - preds[i]);
  const std =
    Math.sqrt(residuals.reduce((a, b) => a + b * b, 0) / Math.max(1, n - 2)) || 0;
  return { slope, intercept, std };
};

export const computeFallbackPlan = (points) => {
  if (!points?.length) return "";
  const closes = points
    .map((p) => Number.parseFloat(p.close))
    .filter((v) => Number.isFinite(v));
  if (!closes.length) return "";
  const lastClose = closes[closes.length - 1];
  const maVals = computeSMA(closes, 21);
  const ma21 = maVals[maVals.length - 1];
  const entryLow = lastClose * 0.97;
  const entryHigh = lastClose * 0.99;
  const target = lastClose * 1.05;
  const stop = lastClose * 0.94;
  const note = Number.isFinite(ma21)
    ? `MA21 ${ma21.toFixed(2)}`
    : "based on latest close";
  return `Entry zone: ${entryLow.toFixed(2)}-${entryHigh.toFixed(
    2,
  )} | Target: ${target.toFixed(2)} | Stop: ${stop.toFixed(2)} | Note: ${note}`;
};

// Helpers used across hooks/components
export const toNumber = (val) => {
  if (val === undefined || val === null) return null;
  const num = Number(val);
  return Number.isFinite(num) ? num : null;
};

export const fallbackMA = (series = [], window = 21) => {
  if (!Array.isArray(series) || !series.length) return [];
  const nums = series.map((v) => toNumber(v) ?? 0);
  return computeSMA(nums, window);
};
