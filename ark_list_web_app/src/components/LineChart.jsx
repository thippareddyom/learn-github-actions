import React, { useEffect, useMemo, useState } from "react";
import { computeRSI, computeSMA } from "../utils/chartUtils";

/**
 * Simple candlestick chart with MA21/MA50, volume bars, and an RSI sub-panel.
 * Includes daily change, YTD change, and earnings marker.
 */
const LineChart = ({
  points = [],
  ticker = "",
  recText = "",
  recLoading = false,
  recError = "",
  recFallback = "",
  onSearchTicker,
  selectedAssetClass = "stocks",
  earningsDate = "",
}) => {
  const width = 980;
  const height = 560;
  const pad = 44;
  const rsiPanelHeight = 110;

  const [range, setRange] = useState("3M");
  const [hoverIdx, setHoverIdx] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [searchAssetClass, setSearchAssetClass] = useState(selectedAssetClass);

  useEffect(() => {
    if (ticker) setSearchTerm(ticker.toUpperCase());
  }, [ticker]);

  useEffect(() => {
    setSearchAssetClass(selectedAssetClass || "stocks");
  }, [selectedAssetClass]);

  const rangeOptions = [
    { key: "1D", label: "1D" },
    { key: "5D", label: "5D" },
    { key: "1M", label: "1M" },
    { key: "3M", label: "3M" },
    { key: "6M", label: "6M" },
    { key: "YTD", label: "YTD" },
    { key: "1Y", label: "1Y" },
    { key: "ALL", label: "All" },
  ];

  const toNumber = (val) => {
    const num = Number(val);
    return Number.isFinite(num) ? num : null;
  };

  const filteredPoints = useMemo(() => {
    if (!points.length) return [];
    const lastDate = new Date(points[points.length - 1].date);
    const cutoff = new Date(lastDate);
    const setCutoff = (days) => cutoff.setDate(lastDate.getDate() - days);
    if (range === "1D") setCutoff(1);
    else if (range === "5D") setCutoff(5);
    else if (range === "1M") setCutoff(30);
    else if (range === "3M") setCutoff(90);
    else if (range === "6M") setCutoff(180);
    else if (range === "1Y") setCutoff(365);
    else if (range === "YTD") cutoff.setFullYear(lastDate.getFullYear(), 0, 1);

    const filtered = range === "ALL" ? points : points.filter((p) => new Date(p.date) >= cutoff);
    return filtered.length ? filtered : points;
  }, [points, range]);

  const xs = filteredPoints.map((_, idx) => idx);
  if (!xs.length) return null;

  const closes = filteredPoints.map((p) => toNumber(p.close) ?? 0);
  const highs = filteredPoints.map((p) => toNumber(p.high) ?? toNumber(p.close) ?? 0);
  const lows = filteredPoints.map((p) => toNumber(p.low) ?? toNumber(p.close) ?? 0);
  const volumes = filteredPoints.map((p) => toNumber(p.volume)).filter((v) => v != null);

  const minY = Math.min(...lows);
  const maxY = Math.max(...highs);
  const spanY = maxY - minY || 1;

  const ma21 = computeSMA(closes, 21);
  const ma50 = computeSMA(closes, 50);
  const rsiValues = computeRSI(closes, 14);

  const hasVolume = volumes.length > 0;
  const maxVolume = hasVolume ? Math.max(...volumes) : 0;
  const volumePanelHeight = hasVolume ? 80 : 0;
  const priceHeight = height - pad * 2 - rsiPanelHeight - volumePanelHeight;
  const priceBottom = height - pad - rsiPanelHeight - volumePanelHeight;
  const volumeBaseY = height - pad - rsiPanelHeight;
  const useLineChart = !(range === "1D" || range === "5D" || range === "1M" || range === "3M" || range === "6M");

  const toX = (i) => pad + (i / Math.max(1, xs.length - 1)) * (width - pad * 2);
  const toY = (y) => priceBottom - ((y - minY) / spanY) * priceHeight;
  const volumeScale = maxVolume ? (volumePanelHeight - 12) / maxVolume : 0;
  const candleWidth = Math.min(14, Math.max(5, ((width - pad * 2) / Math.max(filteredPoints.length, 8)) * 0.7));
  const volumeBarWidth = Math.min(18, Math.max(4, candleWidth * 0.9));

  const activeIdx = hoverIdx ?? filteredPoints.length - 1;
  const activePoint = filteredPoints[activeIdx];
  const activePrice = toNumber(activePoint?.close) ?? 0;
  const lastYear = new Date(filteredPoints[filteredPoints.length - 1].date).getFullYear();
  const startOfYear =
    filteredPoints.find((p) => new Date(p.date).getFullYear() === lastYear) || filteredPoints[0];
  const startClose = toNumber(startOfYear?.close);
  const lastClose = toNumber(filteredPoints[filteredPoints.length - 1]?.close);
  const ytdGain = startClose ? ((lastClose - startClose) / startClose) * 100 : 0;
  const prevClose = toNumber(filteredPoints[filteredPoints.length - 2]?.close);
  const dayChangePct = prevClose && lastClose ? ((lastClose - prevClose) / prevClose) * 100 : 0;
  const dayChangeColor = dayChangePct > 0 ? "#16a34a" : dayChangePct < 0 ? "#ef4444" : "#111827";

  const fmt = (val, digits = 2) => (Number.isFinite(val) ? Number(val).toFixed(digits) : "");

  const xTickCount = 8;
  const xStep = Math.max(1, Math.floor((filteredPoints.length - 1) / (xTickCount - 1)));
  const xTickIdx = Array.from({ length: xTickCount }, (_, i) =>
    Math.min(filteredPoints.length - 1, i * xStep),
  );
  const formatDate = (d) => {
    const date = new Date(d);
    return `${date.getMonth() + 1}/${date.getDate()}`;
  };

  const handleMove = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const xVal = e.clientX - rect.left;
    let best = 0;
    let bestDist = Infinity;
    filteredPoints.forEach((_, idx) => {
      const px = toX(idx);
      const dist = Math.abs(px - xVal);
      if (dist < bestDist) {
        best = idx;
        bestDist = dist;
      }
    });
    setHoverIdx(best);
  };

  const handleLeave = () => setHoverIdx(null);

  const handleSearch = (e) => {
    e.preventDefault();
    const sym = (searchTerm || "").trim().toUpperCase();
    if (!sym || !onSearchTicker) return;
    onSearchTicker(sym, searchAssetClass);
  };

  const showRec = !!recText || recLoading || recError;

  // Earnings marker index (computed inline to avoid hook-order changes)
  const earningsIdx = (() => {
    if (!earningsDate || !filteredPoints.length) return null;
    const earnTs = new Date(earningsDate).getTime();
    if (!Number.isFinite(earnTs)) return null;
    let idx = filteredPoints.findIndex((p) => new Date(p.date).getTime() >= earnTs);
    if (idx === -1) idx = filteredPoints.length - 1;
    return idx;
  })();

  // Y-axis ticks/grid
  const yTicks = (() => {
    const count = 5;
    const step = spanY / Math.max(1, count - 1);
    return Array.from({ length: count }, (_, i) => minY + step * i);
  })();

  return (
    <div className="chart">
      <div className="chart__toolbar">
        <form onSubmit={handleSearch} className="chart-search">
          <select
            className="chart-search__control"
            value={searchAssetClass}
            onChange={(e) => setSearchAssetClass(e.target.value)}
          >
            <option value="stocks">stocks</option>
            <option value="etf">etf</option>
            <option value="crypto">crypto</option>
          </select>
          <input
            className="chart-search__control chart-search__input"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search ticker"
          />
          <button type="submit" className="chip-btn">
            Search
          </button>
        </form>
        <div className="chart__range">
          {rangeOptions.map((opt) => (
            <button
              key={opt.key}
              type="button"
              className={`chip-btn ${range === opt.key ? "chip-btn--active" : ""}`}
              onClick={() => setRange(opt.key)}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div className="chart-meta">
        <div className="chart-meta__title">
          {ticker} {fmt(activePrice)}{" "}
          <span style={{ color: dayChangeColor, fontWeight: 600 }}>
            {dayChangePct > 0 ? "+" : ""}
            {fmt(dayChangePct)}%
          </span>{" "}
          — YTD: {fmt(ytdGain)}%
        </div>
        {showRec && (
          <div className="chart-meta__rec">
            {recLoading ? "Fetching recommendation..." : recError ? `AI: ${recError}` : recText || recFallback}
          </div>
        )}
      </div>

      <svg
        width="100%"
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        xmlns="http://www.w3.org/2000/svg"
        role="img"
        onMouseMove={handleMove}
        onMouseLeave={handleLeave}
      >
        <defs>
          <linearGradient id="volumeGradient" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#0ea5e9" stopOpacity="0.35" />
            <stop offset="100%" stopColor="#0ea5e9" stopOpacity="0.08" />
          </linearGradient>
        </defs>

        {/* Y-axis grid/ticks */}
        <g>
          {yTicks.map((val, idx) => (
            <g key={`yt-${idx}`}>
              <line
                x1={pad}
                x2={width - pad}
                y1={toY(val)}
                y2={toY(val)}
                stroke="#e5e7eb"
                strokeWidth={idx === 0 || idx === yTicks.length - 1 ? 1.4 : 1}
                opacity="0.8"
              />
              <text x={width - pad + 6} y={toY(val) + 4} fill="#4b5563" fontSize="11">
                {fmt(val)}
              </text>
            </g>
          ))}
        </g>

        {/* X-axis vertical grid lines */}
        <g>
          {xTickIdx.map((i) => (
            <line
              key={`xg-${i}`}
              x1={toX(i)}
              x2={toX(i)}
              y1={pad}
              y2={priceBottom}
              stroke="#e5e7eb"
              strokeWidth="1"
              opacity="0.6"
            />
          ))}
        </g>

        <g>
          {Number.isInteger(earningsIdx) && earningsIdx >= 0 && earningsIdx < filteredPoints.length && (
            <g>
              <line
                x1={toX(earningsIdx)}
                x2={toX(earningsIdx)}
                y1={pad}
                y2={priceBottom}
                stroke="#f97316"
                strokeDasharray="4 3"
                strokeWidth="2"
              />
              <text
                x={toX(earningsIdx)}
                y={pad - 6}
                textAnchor="middle"
                fill="#f97316"
                fontSize="12"
                fontWeight="600"
              >
                Earnings
              </text>
            </g>
          )}
          {/* Price series */}
          {useLineChart ? (
            <polyline
              fill="none"
              stroke="#2563eb"
              strokeWidth="2"
              points={filteredPoints.map((p, idx) => `${toX(idx)},${toY(toNumber(p.close) ?? 0)}`).join(" ")}
            />
          ) : (
            filteredPoints.map((p, idx) => {
              const open = toNumber(p.open) ?? toNumber(p.close) ?? 0;
              const close = toNumber(p.close) ?? open;
              const high = toNumber(p.high) ?? Math.max(open, close);
              const low = toNumber(p.low) ?? Math.min(open, close);
              const up = close >= open;
              const color = up ? "#2563eb" : "#ef4444";
              const bodyTop = toY(Math.max(open, close));
              const bodyBottom = toY(Math.min(open, close));
              const cx = toX(idx);
              return (
                <g key={`c-${idx}`}>
                  <line x1={cx} x2={cx} y1={toY(high)} y2={toY(low)} stroke={color} strokeWidth="2" />
                  <rect
                    x={cx - candleWidth / 2}
                    y={bodyTop}
                    width={candleWidth}
                    height={Math.max(2, bodyBottom - bodyTop)}
                    fill={color}
                    stroke={color}
                    rx="1"
                  />
                </g>
              );
            })
          )}

          {/* MAs */}
          {ma21.some((v) => v != null) && (
            <polyline
              fill="none"
              stroke="#e11d48"
              strokeWidth="2"
              points={ma21
                .map((v, i) => (v == null ? null : `${toX(i)},${toY(v)}`))
                .filter(Boolean)
                .join(" ")}
            />
          )}
          {ma50.some((v) => v != null) && (
            <polyline
              fill="none"
              stroke="#111827"
              strokeWidth="2"
              opacity="0.9"
              points={ma50
                .map((v, i) => (v == null ? null : `${toX(i)},${toY(v)}`))
                .filter(Boolean)
                .join(" ")}
            />
          )}

          {/* Volume bars */}
          {hasVolume &&
            filteredPoints.map((p, idx) => {
              const v = toNumber(p.volume);
              if (v == null) return null;
              const cx = toX(idx);
              const barHeight = v * volumeScale;
              return (
                <rect
                  key={`v-${idx}`}
                  x={cx - volumeBarWidth / 2}
                  y={volumeBaseY - barHeight}
                  width={volumeBarWidth}
                  height={barHeight}
                  fill="url(#volumeGradient)"
                />
              );
            })}

          {/* RSI panel */}
          {rsiValues.some((v) => v != null) && (
            <>
              <rect
                x={pad}
                y={height - pad - rsiPanelHeight}
                width={width - pad * 2}
                height={rsiPanelHeight}
                fill="#f8fafc"
                stroke="#e5e7eb"
              />
              <line
                x1={pad}
                x2={width - pad}
                y1={height - pad - rsiPanelHeight / 3}
                y2={height - pad - rsiPanelHeight / 3}
                stroke="#e5e7eb"
              />
              <line
                x1={pad}
                x2={width - pad}
                y1={height - pad - (rsiPanelHeight / 3) * 2}
                y2={height - pad - (rsiPanelHeight / 3) * 2}
                stroke="#e5e7eb"
              />
              <polyline
                fill="none"
                stroke="#2563eb"
                strokeWidth="2"
                points={rsiValues
                  .map((v, i) => (v == null ? null : `${toX(i)},${height - pad - (v / 100) * rsiPanelHeight}`))
                  .filter(Boolean)
                  .join(" ")}
              />
            </>
          )}
        </g>

        {/* X-axis ticks */}
        <g>
          {xTickIdx.map((i) => (
            <text key={`xt-${i}`} x={toX(i)} y={height - pad + 16} textAnchor="middle" fill="#6b7280" fontSize="12">
              {formatDate(filteredPoints[i].date)}
            </text>
          ))}
        </g>
      </svg>
    </div>
  );
};

export default LineChart;
