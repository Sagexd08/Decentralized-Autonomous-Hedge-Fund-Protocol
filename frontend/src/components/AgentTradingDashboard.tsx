import { useEffect, useState, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  AreaChart, Area, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import {
  TrendingUp, TrendingDown, Minus, Brain, Zap, ArrowRightLeft,
  Activity, Clock,
} from 'lucide-react'
import { TradeExecutedMessage } from '../hooks/useWebSocket'
import { useProtocolStore, TradeRecord } from '../store/protocolStore'
import { API_BASE_URL } from '../utils/api'

interface Prediction {
  agent_id: string
  symbol: string
  current_price: number
  predicted_change_pct: number
  momentum: number
  decision: 'BUY' | 'SELL' | 'HOLD'
  confidence: number
  reasoning: string
}

interface PriceHistory {
  [sym: string]: number[]
}

const TOKEN_COLORS: Record<string, string> = {
  WBTC: '#f59e0b', USDC: '#10b981', LINK: '#3b82f6', UNI: '#a855f7',
}
const TOKEN_BASE: Record<string, number> = {
  WBTC: 30000, USDC: 1.0, LINK: 15.0, UNI: 8.0,
}
const DECISION_META = {
  BUY:  { color: '#10b981', bg: 'bg-green/10 border-green/20',   icon: TrendingUp,   label: 'BUY' },
  SELL: { color: '#ef4444', bg: 'bg-red-500/10 border-red-500/20', icon: TrendingDown, label: 'SELL' },
  HOLD: { color: '#64748b', bg: 'bg-slate-700/30 border-border',   icon: Minus,        label: 'HOLD' },
}

function usePredictions(agentId: string) {
  const [predictions, setPredictions] = useState<Prediction[]>([])
  const [priceHistory, setPriceHistory] = useState<PriceHistory>({
    WBTC: [], USDC: [], LINK: [], UNI: [],
  })

  useEffect(() => {
    const fetch_ = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/prices/predictions/${agentId}`)
        if (res.ok) {
          const data = await res.json()
          const preds: Prediction[] = data.predictions ?? []
          setPredictions(preds)

          setPriceHistory(prev => {
            const next = { ...prev }
            preds.forEach(p => {
              next[p.symbol] = [...(prev[p.symbol] ?? []), p.current_price].slice(-60)
            })
            return next
          })
        }
      } catch {}
    }
    fetch_()
    const t = setInterval(fetch_, 5000)
    return () => clearInterval(t)
  }, [agentId])

  return { predictions, priceHistory }
}

function TokenPredictionCard({ pred, history }: { pred: Prediction; history: number[] }) {
  const meta = DECISION_META[pred.decision] ?? DECISION_META.HOLD
  const Icon = meta.icon
  const color = TOKEN_COLORS[pred.symbol] ?? '#64748b'
  const chartData = history.map((v, i) => ({ i, v }))
  const isUp = pred.predicted_change_pct >= 0

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      className={`card p-3 border ${meta.bg}`}
    >
      {}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-lg flex items-center justify-center text-xs font-bold"
            style={{ background: `${color}20`, color }}>
            {pred.symbol.slice(0, 1)}
          </div>
          <div>
            <p className="text-xs font-bold text-white">{pred.symbol}</p>
            <p className="text-xs font-mono text-slate-400">
              ${pred.current_price.toLocaleString('en-US', { maximumFractionDigits: 4 })}
            </p>
          </div>
        </div>
        <div className={`flex items-center gap-1 text-xs font-bold px-2 py-0.5 rounded-full border ${meta.bg}`}
          style={{ color: meta.color }}>
          <Icon size={10} />
          {meta.label}
        </div>
      </div>

      {}
      {chartData.length > 2 && (
        <div className="mb-2 -mx-1">
          <ResponsiveContainer width="100%" height={40}>
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id={`tg-${pred.symbol}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={color} stopOpacity={0.3} />
                  <stop offset="95%" stopColor={color} stopOpacity={0} />
                </linearGradient>
              </defs>
              <Area type="monotone" dataKey="v" stroke={color} strokeWidth={1.5}
                fill={`url(#tg-${pred.symbol})`} dot={false} isAnimationActive={false} />
              <Tooltip contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 6, fontSize: 9 }}
                formatter={(v: number) => [`$${v.toFixed(4)}`]} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {}
      <div className="flex items-center justify-between text-xs mb-2">
        <span className="text-slate-500">Predicted Δ</span>
        <span className={`font-mono font-semibold ${isUp ? 'text-green' : 'text-red-400'}`}>
          {isUp ? '+' : ''}{pred.predicted_change_pct.toFixed(3)}%
        </span>
      </div>

      {}
      <div className="flex items-center justify-between text-xs mb-2">
        <span className="text-slate-500">Momentum</span>
        <span className={`font-mono ${pred.momentum >= 0 ? 'text-green' : 'text-red-400'}`}>
          {pred.momentum >= 0 ? '+' : ''}{pred.momentum.toFixed(3)}%
        </span>
      </div>

      {}
      <div>
        <div className="flex justify-between text-xs mb-1">
          <span className="text-slate-500">Confidence</span>
          <span className="font-mono text-slate-300">{(pred.confidence * 100).toFixed(0)}%</span>
        </div>
        <div className="h-1.5 bg-border rounded-full overflow-hidden">
          <motion.div className="h-full rounded-full"
            style={{ background: meta.color }}
            animate={{ width: `${pred.confidence * 100}%` }}
            transition={{ duration: 0.5 }}
          />
        </div>
      </div>

      {}
      <p className="text-xs text-slate-600 mt-2 leading-relaxed line-clamp-2">{pred.reasoning}</p>
    </motion.div>
  )
}

function SwapRow({ msg, idx }: { msg: TradeExecutedMessage; idx: number }) {
  const color = TOKEN_COLORS[msg.token] ?? '#64748b'
  const ethIn = Number(msg.amountIn) / 1e18
  const tokenOut = Number(msg.amountOut)
  const ts = new Date(msg.timestamp * 1000)
  const timeStr = `${ts.getHours().toString().padStart(2, '0')}:${ts.getMinutes().toString().padStart(2, '0')}:${ts.getSeconds().toString().padStart(2, '0')}`

  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: idx * 0.03 }}
      className="flex items-center gap-3 py-2 border-b border-border/50 last:border-0"
    >
      <div className="w-6 h-6 rounded-lg flex items-center justify-center text-xs font-bold shrink-0"
        style={{ background: `${color}20`, color }}>
        {msg.token.slice(0, 1)}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 text-xs">
          <span className="font-mono text-slate-400">{ethIn.toFixed(4)} ETH</span>
          <ArrowRightLeft size={9} className="text-slate-600" />
          <span className="font-mono" style={{ color }}>{tokenOut.toFixed(4)} {msg.token}</span>
        </div>
        <p className="text-xs text-slate-600 truncate font-mono">{msg.agent?.slice(0, 10)}…</p>
      </div>
      <div className="text-right shrink-0">
        <span className="text-xs px-1.5 py-0.5 rounded font-medium capitalize"
          style={{ background: `${color}15`, color }}>
          {msg.type}
        </span>
        <p className="text-xs text-slate-600 mt-0.5">{timeStr}</p>
      </div>
    </motion.div>
  )
}

interface Props {
  agentId: string
  agentName: string
  messages: TradeExecutedMessage[]
  sessionId?: string
}

export default function AgentTradingDashboard({ agentId, agentName, messages, sessionId }: Props) {
  const { predictions, priceHistory } = usePredictions(agentId)
  const { sessions } = useProtocolStore()

  const session = sessions.find(s => s.id === sessionId)
  const storeRecords: TradeRecord[] = session?.tradeRecords ?? []

  const storeSwaps: TradeExecutedMessage[] = storeRecords.slice(-15).reverse().map(r => ({
    agent: agentId,
    token: r.token,
    amountIn: String(Math.floor(r.ethAmount * 1e18)),
    amountOut: String(Math.floor(r.tokenAmount)),
    timestamp: Math.floor(r.timestamp / 1000),
    type: 'swap' as const,
  }))

  const recentSwaps = storeSwaps.length > 0 ? storeSwaps : messages.slice(-15).reverse()

  const buyCount = predictions.filter(p => p.decision === 'BUY').length
  const sellCount = predictions.filter(p => p.decision === 'SELL').length
  const avgConf = predictions.length
    ? (predictions.reduce((s, p) => s + p.confidence, 0) / predictions.length * 100).toFixed(0)
    : '—'

  return (
    <div className="space-y-4">
      {}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Brain size={14} className="text-cyan" />
          <p className="text-sm font-semibold text-white">ML Predictions — {agentName}</p>
          <span className="text-xs text-slate-500">· updates every 5s</span>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <span className="text-green">{buyCount} BUY</span>
          <span className="text-red-400">{sellCount} SELL</span>
          <span className="text-slate-500">Avg conf: <span className="text-white">{avgConf}%</span></span>
        </div>
      </div>

      {}
      {predictions.length === 0 ? (
        <div className="grid grid-cols-4 gap-3">
          {['WBTC', 'USDC', 'LINK', 'UNI'].map(sym => (
            <div key={sym} className="card p-3 animate-pulse">
              <div className="h-4 bg-slate-800 rounded mb-2 w-16" />
              <div className="h-10 bg-slate-800 rounded mb-2" />
              <div className="h-3 bg-slate-800 rounded w-full" />
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-4 gap-3">
          {predictions.map(pred => (
            <TokenPredictionCard
              key={pred.symbol}
              pred={pred}
              history={priceHistory[pred.symbol] ?? []}
            />
          ))}
        </div>
      )}

      {}
      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <Activity size={13} className="text-slate-400" /> Agent Swap Feed
          </h3>
          <span className="text-xs text-slate-500">{storeRecords.length} total swaps</span>
        </div>
        {recentSwaps.length === 0 ? (
          <div className="text-center py-6 text-slate-500 text-xs">
            <Zap size={20} className="mx-auto mb-2 opacity-30" />
            Starting trades… (first swap in ~3s)
          </div>
        ) : (
          <div>
            {recentSwaps.map((msg, i) => (
              <SwapRow key={`${msg.timestamp}-${i}`} msg={msg} idx={i} />
            ))}
          </div>
        )}
      </div>

      {}
      {storeRecords.length > 0 && (
        <div className="card">
          <h3 className="text-sm font-semibold text-white mb-3">Trade-by-Trade PnL</h3>
          <div className="space-y-1 max-h-48 overflow-y-auto pr-1">
            {storeRecords.slice(-20).reverse().map((r, i) => (
              <div key={r.id} className="flex items-center justify-between text-xs py-1.5 border-b border-border/40 last:border-0">
                <div className="flex items-center gap-2">
                  <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${r.type === 'BUY' ? 'bg-green/10 text-green' : 'bg-red-500/10 text-red-400'}`}>
                    {r.type}
                  </span>
                  <span style={{ color: TOKEN_COLORS[r.token] ?? '#64748b' }}>{r.token}</span>
                  <span className="text-slate-500">{r.ethAmount.toFixed(4)} ETH</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-slate-500 font-mono">${r.price.toFixed(2)}</span>
                  <span className={`font-mono font-semibold ${r.pnlDelta >= 0 ? 'text-green' : 'text-red-400'}`}>
                    {r.pnlDelta >= 0 ? '+' : ''}{r.pnlDelta.toFixed(6)} ETH
                  </span>
                  <span className="text-slate-600">{(r.confidence * 100).toFixed(0)}%</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
