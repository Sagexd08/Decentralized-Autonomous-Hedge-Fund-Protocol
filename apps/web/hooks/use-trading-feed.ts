"use client"

import { useEffect, useRef, useState, useCallback } from "react"
import { WS_URL, type TradeEvent } from "@/lib/api"

const MAX_EVENTS = 100

/**
 * Connects to /ws/trading and streams live trade events.
 */
export function useTradingFeed(): { events: TradeEvent[]; connected: boolean } {
  const [events, setEvents] = useState<TradeEvent[]>([])
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const connect = useCallback(() => {
    const wsEndpoint =
      WS_URL !== "same-origin"
        ? `${WS_URL}/ws/trading`
        : typeof window !== "undefined"
          ? `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}/ws/trading`
          : "ws://localhost:3000/ws/trading"

    const ws = new WebSocket(wsEndpoint)
    wsRef.current = ws

    ws.onopen = () => setConnected(true)

    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data as string) as TradeEvent
        if (!data.token) return // ignore pings / malformed
        setEvents((prev) => [data, ...prev].slice(0, MAX_EVENTS))
      } catch {
        // ignore
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

  useEffect(() => {
    connect()
    return () => {
      wsRef.current?.close()
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
    }
  }, [connect])

  return { events, connected }
}
