"use client"

import { useMemo, useState, useRef, useEffect } from "react"
import { useCandleData, type Candle } from "@/hooks/use-candle-data"
import type { TradeEvent } from "@/lib/api"

// ─── Symbols ─────────────────────────────────────────────────────────────────
const SYMBOLS = ["WBTC", "ETH", "SOL", "LINK", "AAVE"] as const
type Symbol = (typeof SYMBOLS)[number]

// ─── Tooltip ──────────────────────────────────────────────────────────────────
interface TooltipData { candle: Candle; x: number; y: number }

function CandleTooltip({ data }: { data: TooltipData }) {
  const { candle: c, x, y } = data
  const isGreen = c.close >= c.open
  return (
    <div
      style={{
        position: "absolute",
        left: x + 8,
        top: Math.max(4, y - 60),
        background: "#0a0a0a",
        border: "1px solid #f59e0b44",
        borderRadius: 4,
        padding: "7px 10px",
        fontFamily: "monospace",
        fontSize: 11,
        color: "#e5e5e5",
        minWidth: 120,
        pointerEvents: "none",
        zIndex: 10,
        whiteSpace: "nowrap",
      }}
    >
      <div style={{ color: "#f59e0b", marginBottom: 3, fontSize: 10 }}>{c.timeLabel}</div>
      <div>O <span style={{ color: isGreen ? "#22c55e" : "#ef4444" }}>{c.open.toFixed(2)}</span></div>
      <div>H <span style={{ color: "#22c55e" }}>{c.high.toFixed(2)}</span></div>
      <div>L <span style={{ color: "#ef4444" }}>{c.low.toFixed(2)}</span></div>
      <div>C <span style={{ color: isGreen ? "#22c55e" : "#ef4444", fontWeight: 700 }}>{c.close.toFixed(2)}</span></div>
      <div style={{ color: "#6b7280", marginTop: 2 }}>Vol {c.volume.toFixed(0)}</div>
    </div>
  )
}

// ─── Pure SVG candle renderer ─────────────────────────────────────────────────
interface SvgCandlesProps {
  candles: Candle[]
  tradeLabels: { label: string; type: string }[]
  height: number
}

function SvgCandles({ candles, tradeLabels, height }: SvgCandlesProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(800)
  const [tooltip, setTooltip] = useState<TooltipData | null>(null)

  // Measure container width
  useEffect(() => {
    if (!containerRef.current) return
    const ro = new ResizeObserver((entries) => {
      setWidth(entries[0].contentRect.width)
    })
    ro.observe(containerRef.current)
    setWidth(containerRef.current.clientWidth)
    return () => ro.disconnect()
  }, [])

  const PADDING = { top: 8, right: 56, bottom: 24, left: 6 }
  const chartW = Math.max(width - PADDING.left - PADDING.right, 100)
  const chartH = height - PADDING.top - PADDING.bottom

  const { yMin, yMax, xLabels, candleData, maxVol } = useMemo(() => {
    if (!candles.length) return { yMin: 0, yMax: 1, xLabels: [], candleData: [], maxVol: 1 }

    const allLows  = candles.map((c) => c.low)
    const allHighs = candles.map((c) => c.high)
    const lo = Math.min(...allLows)
    const hi = Math.max(...allHighs)
    const pad = (hi - lo) * 0.06 || lo * 0.02
    const yMin = lo - pad
    const yMax = hi + pad
    const maxVol = Math.max(...candles.map((c) => c.volume), 1)

    const n = candles.length
    const candleW = Math.max(Math.floor(chartW / n) - 1, 2)
    const halfW = Math.max(Math.floor(candleW / 2), 1)

    const toY = (price: number) =>
      PADDING.top + ((yMax - price) / (yMax - yMin)) * chartH

    const candleData = candles.map((c, i) => {
      const cx = PADDING.left + (i + 0.5) * (chartW / n)
      const isGreen = c.close >= c.open
      const color = isGreen ? "#22c55e" : "#ef4444"

      const openY  = toY(c.open)
      const closeY = toY(c.close)
      const highY  = toY(c.high)
      const lowY   = toY(c.low)

      const bodyTop    = Math.min(openY, closeY)
      const bodyBottom = Math.max(openY, closeY)
      const bodyH      = Math.max(bodyBottom - bodyTop, 1)

      // Volume bar: bottom 18% of chart
      const volH = (c.volume / maxVol) * chartH * 0.18
      const volY = PADDING.top + chartH - volH

      return { c, cx, isGreen, color, highY, lowY, bodyTop, bodyH, halfW, candleW, volH, volY, i }
    })

    // X-axis labels — show ~6 evenly spaced
    const step = Math.max(Math.floor(n / 6), 1)
    const xLabels = candles
      .map((c, i) => ({ label: c.timeLabel, i }))
      .filter((_, i) => i % step === 0)
      .map(({ label, i }) => ({
        label,
        x: PADDING.left + (i + 0.5) * (chartW / n),
      }))

    // Y-axis ticks
    const tickCount = 5
    const yRange = yMax - yMin
    const yTicks = Array.from({ length: tickCount }, (_, i) => {
      const price = yMin + (yRange * i) / (tickCount - 1)
      return { price, y: toY(price) }
    })

    return { yMin, yMax, xLabels, candleData, maxVol, yTicks }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [candles, chartW, chartH])

  const { yTicks } = useMemo(() => {
    if (!candles.length) return { yTicks: [] }
    const allLows  = candles.map((c) => c.low)
    const allHighs = candles.map((c) => c.high)
    const lo = Math.min(...allLows)
    const hi = Math.max(...allHighs)
    const pad = (hi - lo) * 0.06 || lo * 0.02
    const yMinV = lo - pad
    const yMaxV = hi + pad
    const toY = (price: number) => PADDING.top + ((yMaxV - price) / (yMaxV - yMinV)) * chartH
    const tickCount = 5
    const yRange = yMaxV - yMinV
    return {
      yTicks: Array.from({ length: tickCount }, (_, i) => {
        const price = yMinV + (yRange * i) / (tickCount - 1)
        return { price, y: toY(price) }
      }),
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [candles, chartW, chartH])

  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!candleData.length) return
    const rect = e.currentTarget.getBoundingClientRect()
    const mouseX = e.clientX - rect.left - PADDING.left
    const n = candleData.length
    const idx = Math.max(0, Math.min(n - 1, Math.floor((mouseX / chartW) * n)))
    const d = candleData[idx]
    if (!d) return
    setTooltip({ candle: d.c, x: d.cx, y: d.bodyTop })
  }

  return (
    <div ref={containerRef} style={{ position: "relative", width: "100%" }}>
      <svg
        width={width}
        height={height}
        style={{ display: "block", overflow: "visible" }}
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setTooltip(null)}
      >
        {/* Grid lines */}
        {yTicks?.map((t, i) => (
          <line
            key={i}
            x1={PADDING.left}
            y1={t.y}
            x2={PADDING.left + chartW}
            y2={t.y}
            stroke="#ffffff08"
            strokeDasharray="3 3"
          />
        ))}

        {/* Volume bars */}
        {candleData.map((d) => (
          <rect
            key={`vol-${d.i}`}
            x={d.cx - d.halfW}
            y={d.volY}
            width={d.candleW}
            height={d.volH}
            fill="#ffffff06"
          />
        ))}

        {/* Candles */}
        {candleData.map((d) => (
          <g key={`c-${d.i}`}>
            {/* Full wick */}
            <line
              x1={d.cx}
              y1={d.highY}
              x2={d.cx}
              y2={d.lowY}
              stroke={d.color}
              strokeWidth={1}
              opacity={0.7}
            />
            {/* Body */}
            <rect
              x={d.cx - d.halfW}
              y={d.bodyTop}
              width={d.candleW}
              height={d.bodyH}
              fill={d.isGreen ? d.color : d.color}
              fillOpacity={d.isGreen ? 0.85 : 0.75}
              stroke={d.color}
              strokeWidth={0.5}
            />
          </g>
        ))}

        {/* Trade reference lines */}
        {tradeLabels.map((r, i) => {
          const match = candleData.find((d) => d.c.timeLabel === r.label)
          if (!match) return null
          return (
            <line
              key={`trade-${i}`}
              x1={match.cx}
              y1={PADDING.top}
              x2={match.cx}
              y2={PADDING.top + chartH}
              stroke={r.type === "swap" ? "#22c55e88" : "#ef444488"}
              strokeWidth={1}
              strokeDasharray="3 3"
            />
          )
        })}

        {/* X axis */}
        <line
          x1={PADDING.left}
          y1={PADDING.top + chartH}
          x2={PADDING.left + chartW}
          y2={PADDING.top + chartH}
          stroke="#ffffff10"
        />
        {xLabels.map((l, i) => (
          <text
            key={i}
            x={l.x}
            y={height - 6}
            textAnchor="middle"
            fontSize={9}
            fill="#374151"
            fontFamily="monospace"
          >
            {l.label}
          </text>
        ))}

        {/* Y axis ticks */}
        {yTicks?.map((t, i) => (
          <text
            key={i}
            x={PADDING.left + chartW + 4}
            y={t.y + 3}
            fontSize={10}
            fill="#4b5563"
            fontFamily="monospace"
          >
            {t.price >= 1000 ? `${(t.price / 1000).toFixed(1)}k` : t.price.toFixed(2)}
          </text>
        ))}

        {/* Crosshair on hover */}
        {tooltip && (
          <line
            x1={tooltip.x}
            y1={PADDING.top}
            x2={tooltip.x}
            y2={PADDING.top + chartH}
            stroke="#f59e0b33"
            strokeWidth={1}
            strokeDasharray="2 2"
          />
        )}
      </svg>

      {tooltip && <CandleTooltip data={tooltip} />}
    </div>
  )
}

// ─── Main exported component ──────────────────────────────────────────────────
interface CandleChartProps {
  tradeEvents?: TradeEvent[]
  defaultSymbol?: Symbol
  height?: number
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

  const displayCandles = useMemo(() => candles.slice(-60), [candles])

  const change = useMemo(() => {
    if (displayCandles.length < 2) return 0
    const first = displayCandles[0].open
    const last  = displayCandles[displayCandles.length - 1].close
    return ((last - first) / first) * 100
  }, [displayCandles])

  const tradeLabels = useMemo(() =>
    tradeEvents.slice(0, 10).map((evt) => {
      const d = new Date(evt.timestamp * 1000)
      const label = `${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}`
      return { label, type: evt.type }
    }),
  [tradeEvents])

  const isUp = change >= 0

  return (
    <div style={{ background: "transparent" }}>
      {/* Header */}
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

        <div style={{ display: "flex", alignItems: "center", gap: 10, fontFamily: "monospace" }}>
          {currentPrice != null && (
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

      <SvgCandles candles={displayCandles} tradeLabels={tradeLabels} height={height} />
    </div>
  )
}
