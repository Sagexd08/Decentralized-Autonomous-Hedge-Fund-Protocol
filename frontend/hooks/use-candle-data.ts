"use client"

import { useEffect, useRef, useState, useCallback } from "react"
import { WS_URL } from "@/lib/api"

export interface Candle {
  time: number        // unix ms (candle open time)
  timeLabel: string   // "HH:MM"
  open: number
  high: number
  low: number
  close: number
  volume: number
  // Recharts stacked-bar fields
  candleBase: number  // = low  (invisible bottom bar)
  wickSize: number    // = high - low (visible bar with custom shape)
  isGreen: boolean
}

const CANDLE_INTERVAL_MS = 30_000 // 30-second candles
const HISTORY_COUNT = 80          // seed this many historical candles

/** Generate realistic seeded historical candles via random walk. */
function seedHistory(basePrice: number, symbol: string): Candle[] {
  const candles: Candle[] = []
  const volatility = symbol.includes("BTC") || symbol.includes("WBTC")
    ? 0.0025 : symbol.includes("SOL") ? 0.004 : 0.003

  let price = basePrice
  const now = Date.now()

  for (let i = HISTORY_COUNT; i >= 0; i--) {
    const t = now - i * CANDLE_INTERVAL_MS
    const dt = new Date(t)
    const timeLabel = `${dt.getHours().toString().padStart(2, "0")}:${dt.getMinutes().toString().padStart(2, "0")}`

    // Random walk with slight mean reversion
    const drift = (Math.random() - 0.498) * volatility
    const open = price
    const close = open * (1 + drift)
    const wicks = Math.random() * volatility * 0.6
    const high = Math.max(open, close) * (1 + wicks)
    const low  = Math.min(open, close) * (1 - wicks)
    const volume = Math.random() * 200 + 50

    candles.push({
      time: t,
      timeLabel,
      open,
      high,
      low,
      close,
      volume,
      candleBase: low,
      wickSize: high - low,
      isGreen: close >= open,
    })

    price = close
  }

  return candles
}

function formatTimeLabel(ts: number): string {
  const d = new Date(ts)
  return `${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}`
}

function alignToInterval(ts: number): number {
  return Math.floor(ts / CANDLE_INTERVAL_MS) * CANDLE_INTERVAL_MS
}

/**
 * Builds OHLC candle data from live WS price ticks.
 * Seeds with generated historical candles so the chart is never empty.
 */
export function useCandleData(symbol: string = "WBTC"): {
  candles: Candle[]
  currentPrice: number | null
  seeded: boolean
} {
  const [candles, setCandles] = useState<Candle[]>([])
  const [seeded, setSeeded] = useState(false)
  const [currentPrice, setCurrentPrice] = useState<number | null>(null)

  // Current in-progress candle
  const activeCandle = useRef<Candle | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const seedRef = useRef(false)
  const flushTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const flushActive = useCallback(() => {
    if (!activeCandle.current) return
    const c = { ...activeCandle.current }
    setCandles((prev) => {
      const next = [...prev]
      // Replace last if same time bucket, otherwise append
      if (next.length > 0 && next[next.length - 1].time === c.time) {
        next[next.length - 1] = c
      } else {
        next.push(c)
        if (next.length > HISTORY_COUNT + 40) next.shift()
      }
      return next
    })
  }, [])

  const handlePrice = useCallback((price: number) => {
    setCurrentPrice(price)
    const bucketTime = alignToInterval(Date.now())
    const timeLabel = formatTimeLabel(bucketTime)

    if (!seedRef.current) return

    if (!activeCandle.current || activeCandle.current.time !== bucketTime) {
      // Close old candle
      if (activeCandle.current) flushActive()

      // Open new candle
      const prev = activeCandle.current
      activeCandle.current = {
        time: bucketTime,
        timeLabel,
        open: prev?.close ?? price,
        high: price,
        low: price,
        close: price,
        volume: 1,
        candleBase: price,
        wickSize: 0,
        isGreen: true,
      }
    } else {
      // Update active candle
      const c = activeCandle.current
      c.high = Math.max(c.high, price)
      c.low  = Math.min(c.low, price)
      c.close = price
      c.volume += 1
      c.candleBase = c.low
      c.wickSize = c.high - c.low
      c.isGreen = c.close >= c.open
    }
    // Throttle: flush at most once per 500ms to avoid spamming re-renders
    if (!flushTimer.current) {
      flushTimer.current = setTimeout(() => {
        flushActive()
        flushTimer.current = null
      }, 500)
    }
  }, [flushActive])

  const connect = useCallback(() => {
    const ws = new WebSocket(`${WS_URL}/ws/prices`)
    wsRef.current = ws

    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data as string)
        if (data.type === "ping") return

        // Single tick
        if (data.symbol === symbol && data.price !== undefined) {
          handlePrice(data.price)
        }

        // Batch prices
        if (data.prices?.[symbol]?.price !== undefined) {
          handlePrice(data.prices[symbol].price)
          // Seed history once we know the real price
          if (!seedRef.current) {
            const history = seedHistory(data.prices[symbol].price, symbol)
            setCandles(history)
            seedRef.current = true
            setSeeded(true)
          }
        }
      } catch { /* ignore */ }
    }

    ws.onclose = () => {
      reconnectTimer.current = setTimeout(connect, 5000)
    }
    ws.onerror = () => ws.close()
  }, [symbol, handlePrice])

  useEffect(() => {
    // Seed with a reasonable default price while WS connects
    if (!seedRef.current) {
      const defaultPrices: Record<string, number> = {
        WBTC: 67000, ETH: 3200, SOL: 185, LINK: 18, AAVE: 95
      }
      const base = defaultPrices[symbol] ?? 100
      const history = seedHistory(base, symbol)
      setCandles(history)
      seedRef.current = true
      setSeeded(true)
    }

    connect()
    return () => {
      wsRef.current?.close()
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      if (flushTimer.current) clearTimeout(flushTimer.current)
    }
  }, [connect, symbol])

  return { candles, currentPrice, seeded }
}
