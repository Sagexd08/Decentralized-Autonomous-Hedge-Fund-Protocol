import { useEffect, useRef, useState, useCallback } from 'react'

export interface PriceTick {
  type: 'price' | 'ping'
  symbol?: string
  price?: number
  change_pct?: number
  timestamp?: number
}

export interface TokenPrices {
  [symbol: string]: {
    current: number
    history: number[]
    change_pct: number
  }
}

const INITIAL: TokenPrices = {
  WBTC: { current: 30000, history: [], change_pct: 0 },
  USDC: { current: 1,     history: [], change_pct: 0 },
  LINK: { current: 15,    history: [], change_pct: 0 },
  UNI:  { current: 8,     history: [], change_pct: 0 },
}

const MAX_HISTORY = 100
const RECONNECT_MS = 3000

export function usePriceWebSocket(url: string) {
  const [prices, setPrices] = useState<TokenPrices>(INITIAL)
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const unmounted = useRef(false)

  const connect = useCallback(() => {
    if (unmounted.current) return
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => { if (!unmounted.current) setConnected(true) }

    ws.onmessage = (e) => {
      if (unmounted.current) return
      try {
        const tick: PriceTick = JSON.parse(e.data)
        if (tick.type !== 'price' || !tick.symbol || tick.price == null) return
        setPrices(prev => {
          const sym = tick.symbol!
          const entry = prev[sym] ?? { current: tick.price!, history: [], change_pct: 0 }
          const history = [...entry.history, tick.price!].slice(-MAX_HISTORY)
          return {
            ...prev,
            [sym]: {
              current: tick.price!,
              history,
              change_pct: tick.change_pct ?? 0,
            }
          }
        })
      } catch {  }
    }

    ws.onclose = () => {
      if (unmounted.current) return
      setConnected(false)
      timerRef.current = setTimeout(() => { if (!unmounted.current) connect() }, RECONNECT_MS)
    }
  }, [url])

  useEffect(() => {
    unmounted.current = false
    connect()
    return () => {
      unmounted.current = true
      if (timerRef.current) clearTimeout(timerRef.current)
      if (wsRef.current) { wsRef.current.onclose = null; wsRef.current.close() }
    }
  }, [connect])

  return { prices, connected }
}
