import { useEffect, useRef, useState, useCallback } from 'react'

export interface TradeExecutedMessage {
  agent:     string
  token:     string
  amountIn:  string
  amountOut: string
  timestamp: number
  type:      'swap' | 'supply' | 'borrow' | 'withdraw'
}

export type WebSocketStatus = 'connecting' | 'connected' | 'reconnecting' | 'disconnected'

export interface UseWebSocketReturn {
  messages:    TradeExecutedMessage[]
  status:      WebSocketStatus
  lastMessage: TradeExecutedMessage | null
}

const MAX_MESSAGES = 100
const RECONNECT_DELAY_MS = 5000

export function useWebSocket(url: string): UseWebSocketReturn {
  const [messages, setMessages] = useState<TradeExecutedMessage[]>([])
  const [status, setStatus] = useState<WebSocketStatus>('connecting')
  const [lastMessage, setLastMessage] = useState<TradeExecutedMessage | null>(null)

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const unmountedRef = useRef(false)

  const connect = useCallback(() => {
    if (unmountedRef.current) return

    setStatus('connecting')
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      if (unmountedRef.current) return
      setStatus('connected')
    }

    ws.onmessage = (event: MessageEvent) => {
      if (unmountedRef.current) return
      try {
        const msg = JSON.parse(event.data) as TradeExecutedMessage
        setLastMessage(msg)
        setMessages(prev => {
          const next = [...prev, msg]
          return next.length > MAX_MESSAGES ? next.slice(next.length - MAX_MESSAGES) : next
        })
      } catch {
        // ignore malformed messages
      }
    }

    ws.onclose = () => {
      if (unmountedRef.current) return
      setStatus('reconnecting')
      reconnectTimerRef.current = setTimeout(() => {
        if (!unmountedRef.current) connect()
      }, RECONNECT_DELAY_MS)
    }

    ws.onerror = () => {
      // onclose will fire after onerror, so reconnect logic is handled there
    }
  }, [url])

  useEffect(() => {
    unmountedRef.current = false
    connect()

    return () => {
      unmountedRef.current = true
      if (reconnectTimerRef.current !== null) {
        clearTimeout(reconnectTimerRef.current)
      }
      if (wsRef.current) {
        wsRef.current.onclose = null  // prevent reconnect on intentional close
        wsRef.current.close()
      }
      setStatus('disconnected')
    }
  }, [connect])

  return { messages, status, lastMessage }
}
