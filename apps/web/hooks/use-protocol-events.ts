"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { wsUrl, type ProtocolEvent } from "@/lib/protocol"

/**
 * Live protocol events — Phase 9's stream, consumed.
 *
 * Every frame corresponds to a row in `protocol_events`, written by a trigger
 * on one of the tables phases 3-8 populate, and carries the `source_table` and
 * `source_id` needed to go and read it. Distinct from `use-trading-feed`, which
 * consumes the pre-v2 socket and receives ticks generated in-process.
 *
 * Reconnection is lossless. The hook remembers the highest `seq` it has seen
 * and reconnects with `?since=`, so a dropped connection is a delay rather than
 * a hole — which matters because these events are the audit trail, not a
 * ticker.
 */

const MAX_KEPT = 250
const RECONNECT_MS = 2000

export interface UseProtocolEvents {
  events: ProtocolEvent[]
  connected: boolean
  /** Highest sequence number seen. Also what a reconnect resumes from. */
  watermark: number
  error: string | null
}

export function useProtocolEvents(options: {
  agent?: string
  kinds?: string[]
  replay?: number
  enabled?: boolean
} = {}): UseProtocolEvents {
  const { agent, kinds, replay = 40, enabled = true } = options

  const [events, setEvents] = useState<ProtocolEvent[]>([])
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Refs rather than state: the watermark must survive a reconnect without
  // re-running the effect that owns the socket, or every reconnect would tear
  // down the connection it just made.
  const watermark = useRef(0)
  const socketRef = useRef<WebSocket | null>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const closedByUs = useRef(false)

  const kindKey = kinds?.join(",") ?? ""

  const connect = useCallback(() => {
    if (!enabled || typeof window === "undefined") return

    const params = new URLSearchParams()
    if (agent) params.set("agent", agent)
    if (kindKey) params.set("kinds", kindKey)
    if (watermark.current > 0) {
      params.set("since", String(watermark.current))
    } else {
      params.set("replay", String(replay))
    }

    let socket: WebSocket
    try {
      socket = new WebSocket(wsUrl(`/ws/events?${params}`))
    } catch (err) {
      setError(String(err))
      return
    }
    socketRef.current = socket

    socket.onopen = () => {
      setConnected(true)
      setError(null)
    }

    socket.onmessage = (message) => {
      let frame: ProtocolEvent & { kind: string }
      try {
        frame = JSON.parse(message.data)
      } catch {
        return
      }
      // Control frames carry no row behind them and must not enter the feed.
      if (frame.kind === "KEEPALIVE" || frame.kind === "STREAM_OPEN") return

      watermark.current = Math.max(watermark.current, frame.seq)
      setEvents((current) => {
        // De-duplicate on seq: a reconnect with `since` can legitimately
        // re-deliver the boundary event.
        if (current.some((e) => e.seq === frame.seq)) return current
        return [frame, ...current].slice(0, MAX_KEPT)
      })
    }

    socket.onerror = () => setError("event stream error")

    socket.onclose = () => {
      setConnected(false)
      socketRef.current = null
      if (closedByUs.current) return
      timerRef.current = setTimeout(connect, RECONNECT_MS)
    }
  }, [agent, kindKey, replay, enabled])

  useEffect(() => {
    closedByUs.current = false
    connect()
    return () => {
      closedByUs.current = true
      if (timerRef.current) clearTimeout(timerRef.current)
      socketRef.current?.close()
      socketRef.current = null
    }
  }, [connect])

  return { events, connected, watermark: watermark.current, error }
}
