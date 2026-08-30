"use client"

import { useEffect, useRef, useState, useCallback } from "react"
import { WS_URL, pricesApi } from "@/lib/api"

export interface PriceState {
  price: number
  change_pct: number
  initial: number
}

export type PricesMap = Record<string, PriceState>

/**
 * Connects to /ws/prices and keeps a live map of token prices.
 * Falls back to the REST endpoint on connection failure.
 */
export function useLivePrices(): { prices: PricesMap; connected: boolean } {
  const [prices, setPrices] = useState<PricesMap>({})
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const connect = useCallback(() => {
    const wsEndpoint =
      WS_URL !== "same-origin"
        ? `${WS_URL}/ws/prices`
        : typeof window !== "undefined"
          ? `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}/ws/prices`
          : "ws://localhost:3000/ws/prices"

    const ws = new WebSocket(wsEndpoint)
    wsRef.current = ws

    ws.onopen = () => setConnected(true)

    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data as string)
        // ping keepalive
        if (data.type === "ping") return

        // single price tick: { symbol, price, change_pct, timestamp }
        if (data.symbol && data.price !== undefined) {
          setPrices((prev) => ({
            ...prev,
            [data.symbol]: {
              price: data.price,
              change_pct: data.change_pct ?? 0,
              initial: prev[data.symbol]?.initial ?? data.price,
            },
          }))
        }

        // batch format: { prices: { WBTC: { price, change_pct, initial }, ... } }
        if (data.prices) {
          setPrices((prev) => {
            const next = { ...prev }
            for (const [sym, info] of Object.entries(data.prices as Record<string, PriceState>)) {
              next[sym] = info
            }
            return next
          })
        }
      } catch {
        // ignore malformed frames
      }
    }

    ws.onclose = () => {
      setConnected(false)
      reconnectTimer.current = setTimeout(connect, 5000)
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [])

  // seed from REST on mount so the UI is populated before WS connects
  useEffect(() => {
    pricesApi.current().then((data) => {
      setPrices(data)
    }).catch(() => {})
    connect()
    return () => {
      wsRef.current?.close()
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
    }
  }, [connect])

  return { prices, connected }
}
