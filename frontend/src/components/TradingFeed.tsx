import { useEffect, useState } from 'react'
import { TradeExecutedMessage } from '../hooks/useWebSocket'

interface Props {
  messages: TradeExecutedMessage[]
}

const MAX_TRADES = 50

const ACTION_COLORS: Record<string, string> = {
  swap:     'bg-cyan/10 text-cyan',
  supply:   'bg-green/10 text-green',
  borrow:   'bg-purple/10 text-purple',
  withdraw: 'bg-gold/10 text-gold',
}

function truncateAddress(addr: string): string {
  if (!addr || addr.length < 10) return addr
  return `${addr.slice(0, 6)}…${addr.slice(-4)}`
}

function relativeTime(timestamp: number): string {
  const now = Math.floor(Date.now() / 1000)
  const diff = now - timestamp
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  return `${Math.floor(diff / 3600)}h ago`
}

function formatEth(wei: string): string {
  const n = Number(wei) / 1e18
  return n.toFixed(4)
}

function formatTokenAmount(amount: string): string {
  const n = Number(amount)
  if (n === 0) return '0'
  if (n >= 1e6) return `${(n / 1e6).toFixed(2)}M`
  if (n >= 1e3) return `${(n / 1e3).toFixed(2)}K`
  return n.toFixed(4)
}

interface TradeRow extends TradeExecutedMessage {
  _key: number
  _highlight: boolean
}

export default function TradingFeed({ messages }: Props) {
  const [trades, setTrades] = useState<TradeRow[]>([])
  const [keyCounter, setKeyCounter] = useState(0)

  useEffect(() => {
    if (messages.length === 0) return
    const latest = messages[messages.length - 1]

    setKeyCounter(prev => {
      const newKey = prev + 1
      setTrades(prevTrades => {
        const newRow: TradeRow = { ...latest, _key: newKey, _highlight: true }
        const updated = [newRow, ...prevTrades].slice(0, MAX_TRADES)
        return updated
      })
      return newKey
    })

    // Remove highlight after animation
    const timer = setTimeout(() => {
      setTrades(prev => prev.map(t => ({ ...t, _highlight: false })))
    }, 600)
    return () => clearTimeout(timer)
  }, [messages])

  if (trades.length === 0) {
    return (
      <div className="card">
        <h3 className="text-sm font-semibold text-white mb-4">Trading Feed</h3>
        <div className="flex items-center justify-center h-24 text-slate-500 text-sm">
          Waiting for agent trades...
        </div>
      </div>
    )
  }

  return (
    <div className="card">
      <h3 className="text-sm font-semibold text-white mb-4">Trading Feed</h3>
      <div className="space-y-1 max-h-64 overflow-y-auto">
        {trades.map(trade => (
          <div
            key={trade._key}
            className={`flex items-center gap-3 px-3 py-2 rounded-lg text-xs transition-colors ${
              trade._highlight ? 'bg-cyan/5' : 'hover:bg-white/2'
            }`}
          >
            {/* Agent address */}
            <span className="font-mono text-slate-400 w-20 shrink-0">
              {truncateAddress(trade.agent)}
            </span>

            {/* Action badge */}
            <span
              className={`px-2 py-0.5 rounded-full font-medium capitalize shrink-0 ${
                ACTION_COLORS[trade.type] ?? 'bg-slate-700 text-slate-300'
              }`}
            >
              {trade.type}
            </span>

            {/* Token */}
            <span className="text-white font-medium w-10 shrink-0">{trade.token}</span>

            {/* Amount in ETH */}
            <span className="font-mono text-slate-400 shrink-0">
              {formatEth(trade.amountIn)} ETH
            </span>

            {/* Arrow */}
            <span className="text-slate-600">→</span>

            {/* Amount out */}
            <span className="font-mono text-slate-300 shrink-0">
              {formatTokenAmount(trade.amountOut)}
            </span>

            {/* Relative time */}
            <span className="text-slate-600 ml-auto shrink-0">
              {relativeTime(trade.timestamp)}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
