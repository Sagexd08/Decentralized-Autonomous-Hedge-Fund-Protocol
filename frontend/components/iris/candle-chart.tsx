"use client"

import { useMemo, useState } from "react"
import {
  ComposedChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts"
import { useCandleData, type Candle } from "@/hooks/use-candle-data"
import type { TradeEvent } from "@/lib/api"

// ─── Symbols available in the price engine ───────────────────────────────────
const SYMBOLS = ["WBTC", "ETH", "SOL", "LINK", "AAVE"] as const
type Symbol = (typeof SYMBOLS)[number]

// ─── Custom candle shape (wick + body in one) ─────────────────────────────────
// Props from Recharts Bar when stacked:
//   y      = screen Y of the top of this bar segment (= high price)
//   height = screen pixel span (= high - low in price space)
//   payload = full data row → has .open, .close, .high, .low
interface CandleProps {
  x?: number
  y?: number
  width?: number
  height?: number
  payload?: Candle
}

function CandleShape({ x = 0, y = 0, width = 0, height = 0, payload }: CandleProps) {
  if (!payload || height <= 0 || width <= 0) return null
  const { open, close, high, low } = payload
  const range = high - low
  if (range === 0) return null

  const isGreen  = close >= open
  const color    = isGreen ? "#22c55e" : "#ef4444"
  const cx       = x + width / 2

  // Body bounds in screen coordinates
  const bodyTopPx    = y + ((high - Math.max(open, close)) / range) * height
  const bodyBottomPx = y + ((high - Math.min(open, close)) / range) * height
  const bodyH        = Math.max(bodyBottomPx - bodyTopPx, 1)
  const bodyW        = Math.max(width - 2, 2)

  return (
    <g>
      {/* Upper wick */}
      <line x1={cx} y1={y} x2={cx} y2={bodyTopPx} stroke={color} strokeWidth={1} opacity={0.85} />
      {/* Candle body */}
      <rect
        x={x + 1}
        y={bodyTopPx}
        width={bodyW}
        height={bodyH}
        fill={isGreen ? color : color}
        fillOpacity={isGreen ? 0.85 : 0.75}
        stroke={color}
        strokeWidth={0.5}
      />
      {/* Lower wick */}
      <line x1={cx} y1={bodyBottomPx} x2={cx} y2={y + height} stroke={color} strokeWidth={1} opacity={0.85} />
    </g>
  )
}

// ─── Invisible baseline bar shape ────────────────────────────────────────────
function NullShape() {
  return null
}

// ─── Custom tooltip ───────────────────────────────────────────────────────────
function CandleTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: Candle }> }) {
  if (!active || !payload?.length) return null
  const c = payload[0]?.payload
  if (!c) return null
  const isGreen = c.close >= c.open
  return (
    <div
      style={{
        background: "#0d0d0d",
        border: "1px solid #f59e0b44",
        borderRadius: 4,
        padding: "8px 12px",
        fontFamily: "monospace",
        fontSize: 11,
        color: "#e5e5e5",
        minWidth: 130,
      }}
    >
      <div style={{ color: "#f59e0b", marginBottom: 4, fontSize: 10 }}>{c.timeLabel}</div>
      <div>O <span style={{ color: isGreen ? "#22c55e" : "#ef4444" }}>{c.open.toFixed(2)}</span></div>
      <div>H <span style={{ color: "#22c55e" }}>{c.high.toFixed(2)}</span></div>
      <div>L <span style={{ color: "#ef4444" }}>{c.low.toFixed(2)}</span></div>
      <div>C <span style={{ color: isGreen ? "#22c55e" : "#ef4444", fontWeight: 600 }}>{c.close.toFixed(2)}</span></div>
      <div style={{ color: "#6b7280", marginTop: 2 }}>Vol {c.volume.toFixed(0)}</div>
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────
interface CandleChartProps {
  /** Pre-filter trade events to show as vertical markers */
  tradeEvents?: TradeEvent[]
  /** Override which symbol to chart */
  defaultSymbol?: Symbol
  /** Height in px */
  height?: number
  /** Show symbol selector tabs */
  showSymbolTabs?: boolean
}

export function CandleChart({
  tradeEvents = [],
  defaultSymbol = "WBTC",
  height = 320,
  showSymbolTabs = true,
}: CandleChartProps) {
  const [symbol, setSymbol] = useState<Symbol>(defaultSymbol)
  const { candles, currentPrice } = useCandleData(symbol)

  // Slice last N candles for display
  const displayCandles = useMemo(() => candles.slice(-60), [candles])

  // Y domain: pad 0.5% above/below
  const { yMin, yMax } = useMemo(() => {
    if (!displayCandles.length) return { yMin: 0, yMax: 1 }
    const allLows  = displayCandles.map((c) => c.low)
    const allHighs = displayCandles.map((c) => c.high)
    const lo = Math.min(...allLows)
    const hi = Math.max(...allHighs)
    const pad = (hi - lo) * 0.05
    return { yMin: lo - pad, yMax: hi + pad }
  }, [displayCandles])

  // Max volume for secondary axis scaling
  const maxVol = useMemo(
    () => Math.max(...displayCandles.map((c) => c.volume), 1),
    [displayCandles]
  )

  // Trade event X-positions: match timeLabel to candle index
  const tradeRefLines = useMemo(() => {
    return tradeEvents
      .map((evt) => {
        const evtLabel = (() => {
          const d = new Date(evt.timestamp * 1000)
          return `${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}`
        })()
        return { label: evtLabel, type: evt.type }
      })
      .slice(0, 10)
  }, [tradeEvents])

  const change = useMemo(() => {
    if (displayCandles.length < 2) return 0
    const first = displayCandles[0].open
    const last  = displayCandles[displayCandles.length - 1].close
    return ((last - first) / first) * 100
  }, [displayCandles])

  const isUp = change >= 0

  return (
    <div style={{ background: "transparent" }}>
      {/* Header bar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "8px 12px",
          borderBottom: "1px solid #f59e0b22",
          marginBottom: 4,
        }}
      >
        {/* Symbol tabs */}
        {showSymbolTabs && (
          <div style={{ display: "flex", gap: 2 }}>
            {SYMBOLS.map((s) => (
              <button
                key={s}
                onClick={() => setSymbol(s)}
                style={{
                  background: s === symbol ? "#f59e0b18" : "transparent",
                  border: s === symbol ? "1px solid #f59e0b55" : "1px solid transparent",
                  color: s === symbol ? "#f59e0b" : "#6b7280",
                  borderRadius: 3,
                  padding: "2px 8px",
                  fontSize: 11,
                  fontFamily: "monospace",
                  cursor: "pointer",
                  transition: "all 0.15s",
                }}
              >
                {s}
              </button>
            ))}
          </div>
        )}

        {/* Live price badge */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, fontFamily: "monospace" }}>
          {currentPrice && (
            <>
              <span style={{ fontSize: 15, fontWeight: 700, color: isUp ? "#22c55e" : "#ef4444" }}>
                {currentPrice.toFixed(symbol === "WBTC" ? 0 : 2)}
              </span>
              <span
                style={{
                  fontSize: 11,
                  color: isUp ? "#22c55e" : "#ef4444",
                  background: isUp ? "#22c55e18" : "#ef444418",
                  padding: "1px 5px",
                  borderRadius: 3,
                }}
              >
                {isUp ? "+" : ""}{change.toFixed(2)}%
              </span>
            </>
          )}
          <span style={{ fontSize: 10, color: "#4b5563" }}>30s candles</span>
        </div>
      </div>

      {/* Chart */}
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart
          data={displayCandles}
          margin={{ top: 4, right: 8, bottom: 0, left: 0 }}
          barCategoryGap="10%"
        >
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="#ffffff08"
            vertical={false}
          />

          {/* Primary Y axis — price */}
          <YAxis
            domain={[yMin, yMax]}
            orientation="right"
            tick={{ fontSize: 10, fill: "#4b5563", fontFamily: "monospace" }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v: number) =>
              v >= 1000 ? `${(v / 1000).toFixed(1)}k` : v.toFixed(2)
            }
            width={52}
          />

          {/* Secondary Y axis — volume (hidden, scaled so vol ≈ bottom 20%) */}
          <YAxis
            yAxisId="vol"
            domain={[0, maxVol * 6]}
            hide
          />

          {/* X axis — time labels */}
          <XAxis
            dataKey="timeLabel"
            tick={{ fontSize: 9, fill: "#374151", fontFamily: "monospace" }}
            tickLine={false}
            axisLine={{ stroke: "#ffffff10" }}
            interval={Math.floor(displayCandles.length / 6)}
          />

          <Tooltip content={<CandleTooltip />} cursor={{ stroke: "#f59e0b33", strokeWidth: 1 }} />

          {/* Trade event reference lines */}
          {tradeRefLines.map((r, i) => (
            <ReferenceLine
              key={i}
              x={r.label}
              stroke={r.type === "swap" ? "#22c55e88" : "#ef444488"}
              strokeDasharray="3 3"
              strokeWidth={1}
            />
          ))}

          {/* Volume bars (background, secondary axis) */}
          <Bar
            yAxisId="vol"
            dataKey="volume"
            fill="#ffffff07"
            stroke="none"
            isAnimationActive={false}
            barSize={8}
          />

          {/* ── Stacked candle bars ── */}
          {/* Bar 1: invisible baseline from 0 to low */}
          <Bar
            dataKey="candleBase"
            stackId="candle"
            fill="transparent"
            stroke="none"
            isAnimationActive={false}
            shape={<NullShape />}
          />

          {/* Bar 2: visible span from low to high, custom candle shape */}
          <Bar
            dataKey="wickSize"
            stackId="candle"
            isAnimationActive={false}
            shape={<CandleShape />}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
