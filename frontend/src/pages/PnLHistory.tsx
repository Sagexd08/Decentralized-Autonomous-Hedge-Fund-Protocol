import { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import {
  AreaChart, Area, BarChart, Bar, LineChart, Line,
  ResponsiveContainer, Tooltip, XAxis, YAxis, ReferenceLine, Cell,
} from 'recharts'
import {
  TrendingUp, TrendingDown, History, ArrowLeft,
  CheckCircle, Activity, Zap, BarChart2, ChevronDown, ChevronUp,
  Award, Shield, Target, Clock,
} from 'lucide-react'
import { useProtocolStore, TradingSession } from '../store/protocolStore'

const RISK_COLORS: Record<string, string> = {
  Conservative: '#10b981', Balanced: '#3b82f6', Aggressive: '#a855f7',
}
const TOKEN_COLORS: Record<string, string> = {
  WBTC: '#f59e0b', USDC: '#10b981', LINK: '#3b82f6', UNI: '#a855f7',
}

function fmt(ts: number) {
  return new Date(ts).toLocaleString('en-US', {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

function duration(s: TradingSession) {
  const ms = (s.endTime ?? Date.now()) - s.startTime
  const h = Math.floor(ms / 3600000)
  const m = Math.floor((ms % 3600000) / 60000)
  const sec = Math.floor((ms % 60000) / 1000)
  if (h > 0) return `${h}h ${m}m`
  return `${m}m ${sec}s`
}

// Expanded session detail row
function SessionDetail({ s }: { s: TradingSession }) {
  const [open, setOpen] = useState(false)
  const pnl = s.finalPnlEth ?? 0
  const pct = s.finalPnlPct ?? (s.ethDeposited > 0 ? (pnl / s.ethDeposited * 100) : 0)
  const color = RISK_COLORS[s.agentRisk] ?? '#64748b'
  const winRate = s.trades > 0 ? (((s.winTrades ?? 0) / s.trades) * 100).toFixed(1) : '—'

  // Build per-trade PnL chart
  const tradeChart = (s.tradeRecords ?? []).map((t, i) => ({
    i, pnl: t.pnlDelta, cum: (s.tradeRecords ?? []).slice(0, i + 1).reduce((a, b) => a + b.pnlDelta, 0),
  }))

  // Token breakdown
  const tokenBreakdown = (s.tradeRecords ?? []).reduce<Record<string, { count: number; pnl: number }>>((acc, t) => {
    if (!acc[t.token]) acc[t.token] = { count: 0, pnl: 0 }
    acc[t.token].count++
    acc[t.token].pnl += t.pnlDelta
    return acc
  }, {})

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
      className="border border-border rounded-xl overflow-hidden">
      {/* Summary row */}
      <div className="flex items-center gap-4 p-4 hover:bg-white/2 transition-colors cursor-pointer"
        onClick={() => setOpen(o => !o)}>
        <div className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold shrink-0"
          style={{ background: `${color}20`, color }}>
          {s.agentName.slice(0, 2)}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className="text-sm font-semibold text-white">{s.agentName}</p>
            <span className="text-xs px-1.5 py-0.5 rounded-full" style={{ color, background: `${color}15` }}>
              {s.agentRisk}
            </span>
          </div>
          <p className="text-xs text-slate-500">{fmt(s.startTime)} → {s.endTime ? fmt(s.endTime) : 'Active'} · {duration(s)}</p>
        </div>
        <div className="grid grid-cols-5 gap-6 text-right text-xs shrink-0">
          <div>
            <p className="text-slate-500">Deposited</p>
            <p className="font-mono text-white">{s.ethDeposited.toFixed(4)} ETH</p>
          </div>
          <div>
            <p className="text-slate-500">Net PnL</p>
            <p className={`font-mono font-semibold ${pnl >= 0 ? 'text-green' : 'text-red-400'}`}>
              {pnl >= 0 ? '+' : ''}{pnl.toFixed(6)} ETH
            </p>
          </div>
          <div>
            <p className="text-slate-500">Return</p>
            <p className={`font-mono ${pct >= 0 ? 'text-green' : 'text-red-400'}`}>
              {pct >= 0 ? '+' : ''}{pct.toFixed(2)}%
            </p>
          </div>
          <div>
            <p className="text-slate-500">Trades</p>
            <p className="font-mono text-white">{s.trades}</p>
          </div>
          <div>
            <p className="text-slate-500">Win Rate</p>
            <p className="font-mono text-cyan">{winRate}%</p>
          </div>
        </div>
        <button className="text-slate-500 hover:text-slate-300 ml-2">
          {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </button>
      </div>

      {/* Expanded detail */}
      {open && (
        <div className="border-t border-border p-4 bg-slate-900/30 space-y-4">
          <div className="grid grid-cols-4 gap-3">
            {[
              { label: 'Sharpe Ratio', value: s.sharpeRatio?.toFixed(3) ?? '—', color: 'text-cyan', icon: TrendingUp },
              { label: 'Max Drawdown', value: s.maxDrawdownEth ? `-${s.maxDrawdownEth.toFixed(6)} ETH` : '—', color: 'text-red-400', icon: TrendingDown },
              { label: 'Peak PnL', value: s.peakPnlEth ? `+${s.peakPnlEth.toFixed(6)} ETH` : '—', color: 'text-green', icon: Award },
              { label: 'Avg Win / Loss', value: s.avgWinEth !== undefined ? `+${s.avgWinEth.toFixed(5)} / ${s.avgLossEth?.toFixed(5)}` : '—', color: 'text-white', icon: Target },
            ].map(m => (
              <div key={m.label} className="bg-slate-900 rounded-lg p-3">
                <div className="flex items-center gap-1.5 mb-1">
                  <m.icon size={11} className={m.color} />
                  <p className="text-xs text-slate-500">{m.label}</p>
                </div>
                <p className={`text-sm font-mono font-semibold ${m.color}`}>{m.value}</p>
              </div>
            ))}
          </div>

          {/* Cumulative PnL chart */}
          {tradeChart.length > 1 && (
            <div>
              <p className="text-xs text-slate-500 mb-2">Cumulative PnL per Trade</p>
              <ResponsiveContainer width="100%" height={100}>
                <AreaChart data={tradeChart}>
                  <defs>
                    <linearGradient id={`sg-${s.id}`} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={pnl >= 0 ? '#10b981' : '#ef4444'} stopOpacity={0.3} />
                      <stop offset="95%" stopColor={pnl >= 0 ? '#10b981' : '#ef4444'} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="i" hide />
                  <YAxis tickFormatter={v => `${v > 0 ? '+' : ''}${v.toFixed(4)}`} tick={{ fill: '#64748b', fontSize: 9 }} width={55} />
                  <ReferenceLine y={0} stroke="#475569" strokeDasharray="3 3" />
                  <Tooltip contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 6, fontSize: 9 }}
                    formatter={(v: number) => [`${v >= 0 ? '+' : ''}${v.toFixed(6)} ETH`]} />
                  <Area type="monotone" dataKey="cum" stroke={pnl >= 0 ? '#10b981' : '#ef4444'}
                    strokeWidth={1.5} fill={`url(#sg-${s.id})`} dot={false} isAnimationActive={false} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Token breakdown */}
          {Object.keys(tokenBreakdown).length > 0 && (
            <div>
              <p className="text-xs text-slate-500 mb-2">Token Breakdown</p>
              <div className="grid grid-cols-4 gap-2">
                {Object.entries(tokenBreakdown).map(([token, data]) => (
                  <div key={token} className="bg-slate-900 rounded-lg p-2.5">
                    <p className="text-xs font-semibold mb-1" style={{ color: TOKEN_COLORS[token] ?? '#64748b' }}>{token}</p>
                    <p className="text-xs text-slate-500">{data.count} trades</p>
                    <p className={`text-xs font-mono ${data.pnl >= 0 ? 'text-green' : 'text-red-400'}`}>
                      {data.pnl >= 0 ? '+' : ''}{data.pnl.toFixed(6)} ETH
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Tokens traded */}
          {s.tokensTraded && s.tokensTraded.length > 0 && (
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <span>Tokens traded:</span>
              {s.tokensTraded.map(t => (
                <span key={t} className="px-2 py-0.5 rounded-full text-xs font-medium"
                  style={{ color: TOKEN_COLORS[t] ?? '#64748b', background: `${TOKEN_COLORS[t] ?? '#64748b'}15` }}>
                  {t}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </motion.div>
  )
}

export default function PnLHistory() {
  const navigate = useNavigate()
  const { sessions, startSession, endSession } = useProtocolStore()

  const seedDemo = () => {
    const tokens = ['WBTC', 'USDC', 'LINK', 'UNI']
    const makeRecords = (count: number, deposited: number) =>
      Array.from({ length: count }, (_, i) => {
        const token = tokens[i % tokens.length]
        const ethAmt = deposited * (0.05 + Math.random() * 0.1)
        const delta = ethAmt * (Math.random() - 0.46) * 0.008
        return {
          id: `demo-${i}`, timestamp: Date.now() - (count - i) * 30000,
          token, type: (delta > 0 ? 'BUY' : 'SELL') as 'BUY' | 'SELL',
          ethAmount: ethAmt, tokenAmount: ethAmt * 1e15,
          price: { WBTC: 30000, USDC: 1, LINK: 15, UNI: 8 }[token] ?? 10,
          pnlDelta: delta, decision: delta > 0 ? 'BUY' : 'SELL', confidence: 0.5 + Math.random() * 0.4,
        }
      })

    const s1 = startSession('AGT-001', 'AlphaWave', 'Aggressive', 0.5)
    const r1 = makeRecords(47, 0.5)
    setTimeout(() => endSession(s1, 0.0234, 47, r1), 50)

    const s2 = startSession('AGT-003', 'QuantSigma', 'Conservative', 0.2)
    const r2 = makeRecords(23, 0.2)
    setTimeout(() => endSession(s2, -0.0041, 23, r2), 100)

    const s3 = startSession('AGT-004', 'VoltexAI', 'Aggressive', 1.0)
    const r3 = makeRecords(112, 1.0)
    setTimeout(() => endSession(s3, 0.0891, 112, r3), 150)
  }

  const completed = useMemo(() =>
    sessions.filter(s => s.status === 'completed').sort((a, b) => (b.endTime ?? 0) - (a.endTime ?? 0)),
    [sessions]
  )
  const active = sessions.filter(s => s.status === 'active')

  const totalDeposited = completed.reduce((s, x) => s + x.ethDeposited, 0)
  const totalPnL = completed.reduce((s, x) => s + (x.finalPnlEth ?? 0), 0)
  const wins = completed.filter(s => (s.finalPnlEth ?? 0) > 0).length
  const winRate = completed.length > 0 ? (wins / completed.length * 100).toFixed(1) : '0'
  const totalTrades = completed.reduce((s, x) => s + x.trades, 0)
  const avgSharpe = completed.filter(s => s.sharpeRatio).length
    ? (completed.reduce((s, x) => s + (x.sharpeRatio ?? 0), 0) / completed.filter(s => s.sharpeRatio).length).toFixed(2)
    : '—'

  const barData = completed.slice(0, 20).reverse().map(s => ({
    name: s.agentName.slice(0, 6),
    pnl: parseFloat((s.finalPnlEth ?? 0).toFixed(6)),
    color: (s.finalPnlEth ?? 0) >= 0 ? '#10b981' : '#ef4444',
  }))

  const cumData = completed.slice().reverse().reduce<{ i: number; cum: number }[]>((acc, s) => {
    const prev = acc[acc.length - 1]?.cum ?? 0
    acc.push({ i: acc.length, cum: parseFloat((prev + (s.finalPnlEth ?? 0)).toFixed(6)) })
    return acc
  }, [])

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/dashboard')}
            className="p-2 rounded-lg border border-border text-slate-400 hover:text-white hover:border-slate-500 transition-all">
            <ArrowLeft size={14} />
          </button>
          <div>
            <h1 className="text-xl font-bold text-white">PnL History</h1>
            <p className="text-slate-500 text-sm mt-0.5">All trading sessions · detailed profit & loss records</p>
          </div>
        </div>
        {active.length > 0 && (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-green/10 border border-green/20 text-green text-xs">
            <Activity size={11} className="animate-pulse" />
            {active.length} active
          </div>
        )}
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-6 gap-3">
        {[
          { label: 'Sessions', value: completed.length, color: 'text-white', icon: History },
          { label: 'Deposited', value: `${totalDeposited.toFixed(4)} ETH`, color: 'text-white', icon: Zap },
          { label: 'Total PnL', value: `${totalPnL >= 0 ? '+' : ''}${totalPnL.toFixed(6)} ETH`, color: totalPnL >= 0 ? 'text-green' : 'text-red-400', icon: totalPnL >= 0 ? TrendingUp : TrendingDown },
          { label: 'Win Rate', value: `${winRate}%`, color: 'text-cyan', icon: CheckCircle },
          { label: 'Total Trades', value: totalTrades, color: 'text-purple', icon: Activity },
          { label: 'Avg Sharpe', value: avgSharpe, color: 'text-yellow-400', icon: Award },
        ].map(s => (
          <div key={s.label} className="card py-3 px-3 flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-slate-800 flex items-center justify-center shrink-0">
              <s.icon size={12} className={s.color} />
            </div>
            <div>
              <p className={`text-sm font-bold font-mono ${s.color}`}>{s.value}</p>
              <p className="text-xs text-slate-500">{s.label}</p>
            </div>
          </div>
        ))}
      </div>

      {completed.length === 0 && active.length === 0 ? (
        <div className="card text-center py-16 text-slate-500">
          <History size={32} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">No trading sessions yet.</p>
          <p className="text-xs mt-1">Delegate ETH to an agent and start trading to see history here.</p>
          <div className="flex items-center justify-center gap-3 mt-4">
            <button onClick={() => navigate('/agents')}
              className="px-4 py-2 rounded-lg text-xs bg-cyan/10 text-cyan border border-cyan/20 hover:bg-cyan/20 transition-all">
              Go to Agent Marketplace
            </button>
            <button onClick={seedDemo}
              className="px-4 py-2 rounded-lg text-xs bg-slate-800 text-slate-400 border border-border hover:border-slate-500 transition-all">
              Load Demo Data
            </button>
          </div>
        </div>
      ) : (
        <>
          {completed.length > 1 && (
            <div className="grid grid-cols-2 gap-4">
              <div className="card">
                <h3 className="text-sm font-semibold text-white mb-1">PnL per Session</h3>
                <p className="text-xs text-slate-500 mb-3">Last 20 sessions</p>
                <ResponsiveContainer width="100%" height={140}>
                  <BarChart data={barData}>
                    <XAxis dataKey="name" tick={{ fill: '#64748b', fontSize: 9 }} />
                    <YAxis tickFormatter={v => `${v > 0 ? '+' : ''}${v.toFixed(4)}`} tick={{ fill: '#64748b', fontSize: 9 }} width={55} />
                    <ReferenceLine y={0} stroke="#475569" />
                    <Tooltip contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 6, fontSize: 10 }}
                      formatter={(v: number) => [`${v >= 0 ? '+' : ''}${v.toFixed(6)} ETH`]} />
                    <Bar dataKey="pnl" radius={[3, 3, 0, 0]}>
                      {barData.map((d, i) => <Cell key={i} fill={d.color} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="card">
                <h3 className="text-sm font-semibold text-white mb-1">Cumulative PnL</h3>
                <p className="text-xs text-slate-500 mb-3">Running total</p>
                <ResponsiveContainer width="100%" height={140}>
                  <AreaChart data={cumData}>
                    <defs>
                      <linearGradient id="cumGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={totalPnL >= 0 ? '#10b981' : '#ef4444'} stopOpacity={0.3} />
                        <stop offset="95%" stopColor={totalPnL >= 0 ? '#10b981' : '#ef4444'} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <XAxis dataKey="i" hide />
                    <YAxis tickFormatter={v => `${v > 0 ? '+' : ''}${v.toFixed(4)}`} tick={{ fill: '#64748b', fontSize: 9 }} width={55} />
                    <ReferenceLine y={0} stroke="#475569" strokeDasharray="3 3" />
                    <Tooltip contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 6, fontSize: 10 }}
                      formatter={(v: number) => [`${v >= 0 ? '+' : ''}${v.toFixed(6)} ETH`, 'Cumulative']} />
                    <Area type="monotone" dataKey="cum" stroke={totalPnL >= 0 ? '#10b981' : '#ef4444'}
                      strokeWidth={2} fill="url(#cumGrad)" dot={false} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {active.length > 0 && (
            <div className="card border-green/20">
              <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                <Activity size={13} className="text-green animate-pulse" /> Active Sessions
              </h3>
              <div className="space-y-2">
                {active.map(s => (
                  <div key={s.id} className="flex items-center justify-between p-3 rounded-xl bg-green/5 border border-green/15">
                    <div className="flex items-center gap-3">
                      <div className="w-2 h-2 rounded-full bg-green animate-pulse" />
                      <div>
                        <p className="text-sm font-semibold text-white">{s.agentName}</p>
                        <p className="text-xs text-slate-500">{s.agentRisk} · {s.trades} trades · Started {fmt(s.startTime)}</p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-xs text-slate-500">Deposited</p>
                      <p className="text-sm font-mono text-cyan">{s.ethDeposited.toFixed(4)} ETH</p>
                    </div>
                    <button onClick={() => navigate('/dashboard')}
                      className="text-xs px-3 py-1.5 rounded-lg bg-green/10 text-green border border-green/20 hover:bg-green/20 transition-all">
                      View Live
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {completed.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-white">Completed Sessions</h3>
              {completed.map(s => <SessionDetail key={s.id} s={s} />)}
            </div>
          )}
        </>
      )}
    </div>
  )
}
