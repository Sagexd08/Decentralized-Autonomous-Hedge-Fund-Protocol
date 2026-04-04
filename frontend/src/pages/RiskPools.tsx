import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  AreaChart, Area, LineChart, Line, ScatterChart, Scatter,
  RadarChart, Radar, PolarGrid, PolarAngleAxis,
  ResponsiveContainer, Tooltip, XAxis, YAxis, ZAxis,
  ReferenceLine, Cell,
} from 'recharts'
import {
  Shield, TrendingUp, Users, DollarSign, AlertTriangle,
  CheckCircle, Activity, X, ArrowUpRight, Zap, BarChart2,
  Lock, Unlock, ChevronDown, ChevronUp,
} from 'lucide-react'
import { pools, agents, generateTimeSeries } from '../utils/mockData'
import { api } from '../utils/api'

const POOL_META = {
  conservative: {
    color: '#10b981', gradient: 'from-emerald-500/10 to-transparent',
    maxCapacity: 10000000, riskLabel: 'Low Risk', icon: Lock,
    description: 'Capital-preservation focused. Targets stable yield through mean-reversion strategies with strict drawdown limits.',
    strategies: ['Mean Reversion', 'Yield Farming', 'Delta Neutral'],
    drawdownLimit: 8,
  },
  balanced: {
    color: '#3b82f6', gradient: 'from-blue-500/10 to-transparent',
    maxCapacity: 20000000, riskLabel: 'Medium Risk', icon: Shield,
    description: 'Balanced risk/return profile. Combines momentum and arbitrage strategies with moderate volatility tolerance.',
    strategies: ['Momentum', 'Cross-DEX Arb', 'Options Hedging'],
    drawdownLimit: 15,
  },
  aggressive: {
    color: '#a855f7', gradient: 'from-purple-500/10 to-transparent',
    maxCapacity: 30000000, riskLabel: 'High Risk', icon: Unlock,
    description: 'Maximum return pursuit. High-frequency breakout and liquidation hunting strategies with elevated vol tolerance.',
    strategies: ['Breakout', 'Liquidation Hunt', 'Volatility Arb'],
    drawdownLimit: 25,
  },
}

function useRollingVol() {
  const [volData, setVolData] = useState<Record<string, number>>({
    conservative: 5.2, balanced: 13.8, aggressive: 28.4,
  })
  useEffect(() => {
    const t = setInterval(() => {
      setVolData(prev => ({
        conservative: Math.max(1, Math.min(8, prev.conservative + (Math.random() - 0.5) * 0.4)),
        balanced: Math.max(5, Math.min(18, prev.balanced + (Math.random() - 0.5) * 0.8)),
        aggressive: Math.max(10, Math.min(35, prev.aggressive + (Math.random() - 0.5) * 1.5)),
      }))
    }, 2000)
    return () => clearInterval(t)
  }, [])
  return volData
}

function useTVLHistory() {
  const [history, setHistory] = useState(() => ({
    conservative: generateTimeSeries(30, 4.2, 0.1),
    balanced: generateTimeSeries(30, 8.7, 0.2),
    aggressive: generateTimeSeries(30, 12.4, 0.4),
  }))
  useEffect(() => {
    const t = setInterval(() => {
      setHistory(prev => {
        const now = new Date().toISOString().slice(0, 16).replace('T', ' ')
        return {
          conservative: [...prev.conservative.slice(-29), { time: now, value: parseFloat((prev.conservative[prev.conservative.length - 1].value + (Math.random() - 0.48) * 0.05).toFixed(3)) }],
          balanced: [...prev.balanced.slice(-29), { time: now, value: parseFloat((prev.balanced[prev.balanced.length - 1].value + (Math.random() - 0.48) * 0.1).toFixed(3)) }],
          aggressive: [...prev.aggressive.slice(-29), { time: now, value: parseFloat((prev.aggressive[prev.aggressive.length - 1].value + (Math.random() - 0.48) * 0.2).toFixed(3)) }],
        }
      })
    }, 3000)
    return () => clearInterval(t)
  }, [])
  return history
}

function mergeTVL(history: Record<string, { time: string; value: number }[]>) {
  return history.conservative.map((p, i) => ({
    time: p.time,
    Conservative: p.value,
    Balanced: history.balanced[i]?.value ?? 0,
    Aggressive: history.aggressive[i]?.value ?? 0,
  }))
}

function DepositModal({ pool, onClose }: { pool: typeof pools[0]; onClose: () => void }) {
  const meta = POOL_META[pool.id as keyof typeof POOL_META]
  const [amount, setAmount] = useState('')
  const [address, setAddress] = useState('0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266')
  const [status, setStatus] = useState<'idle' | 'pending' | 'success'>('idle')

  const handleDeposit = async () => {
    if (!amount || parseFloat(amount) <= 0) return
    setStatus('pending')
    try {
      await api.post('/api/pools/deposit', {
        pool_id: pool.id, amount: parseFloat(amount), investor_address: address,
      })
      setStatus('success')
    } catch {
      setStatus('idle')
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }}
        className="bg-slate-950 border border-border rounded-2xl w-full max-w-md">
        <div className="flex items-center justify-between p-5 border-b border-border">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: `${meta.color}20` }}>
              <Shield size={13} style={{ color: meta.color }} />
            </div>
            <h2 className="text-sm font-semibold text-white">Deposit into {pool.name}</h2>
          </div>
          <button onClick={onClose} className="text-slate-500 hover:text-white"><X size={16} /></button>
        </div>

        {status === 'success' ? (
          <div className="p-8 text-center space-y-3">
            <CheckCircle size={40} className="text-green mx-auto" />
            <p className="text-white font-semibold">Deposit Submitted</p>
            <p className="text-xs text-slate-500">Transaction is being processed on-chain</p>
            <button onClick={onClose} className="mt-2 px-6 py-2 rounded-lg text-sm bg-green/10 text-green border border-green/20">Done</button>
          </div>
        ) : (
          <div className="p-5 space-y-4">
            <div className="grid grid-cols-3 gap-2 text-center">
              {[
                { label: 'APY', value: `${pool.apy}%`, color: meta.color },
                { label: 'Vol Cap', value: `${pool.volatilityCap}%`, color: '#f59e0b' },
                { label: 'TVL', value: `$${(pool.tvl / 1e6).toFixed(1)}M`, color: '#94a3b8' },
              ].map(s => (
                <div key={s.label} className="bg-slate-900 rounded-lg p-2">
                  <p className="text-xs text-slate-500">{s.label}</p>
                  <p className="text-sm font-bold font-mono" style={{ color: s.color }}>{s.value}</p>
                </div>
              ))}
            </div>

            <div>
              <label className="text-xs text-slate-400 mb-1.5 block">Amount (USDC)</label>
              <input value={amount} onChange={e => setAmount(e.target.value)} type="number" placeholder="0.00"
                className="w-full bg-slate-900 border border-border rounded-lg px-3 py-2 text-sm text-slate-100 font-mono placeholder-slate-600 focus:outline-none focus:border-cyan/50" />
              <div className="flex gap-2 mt-2">
                {[1000, 5000, 10000].map(v => (
                  <button key={v} onClick={() => setAmount(String(v))}
                    className="text-xs px-2 py-1 rounded-md bg-slate-800 text-slate-400 hover:text-white transition-colors">
                    ${v.toLocaleString()}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="text-xs text-slate-400 mb-1.5 block">Wallet Address</label>
              <input value={address} onChange={e => setAddress(e.target.value)}
                className="w-full bg-slate-900 border border-border rounded-lg px-3 py-2 text-xs text-slate-100 font-mono focus:outline-none focus:border-cyan/50" />
            </div>

            {amount && parseFloat(amount) > 0 && (
              <div className="p-3 bg-slate-900 rounded-lg border border-border text-xs space-y-1">
                <div className="flex justify-between text-slate-500">
                  <span>Estimated annual yield</span>
                  <span className="text-green font-mono">+${(parseFloat(amount) * pool.apy / 100).toFixed(2)}</span>
                </div>
                <div className="flex justify-between text-slate-500">
                  <span>Max drawdown risk</span>
                  <span className="text-yellow-400 font-mono">-{meta.drawdownLimit}%</span>
                </div>
              </div>
            )}

            <button onClick={handleDeposit} disabled={!amount || status === 'pending'}
              className="w-full py-2.5 rounded-xl text-sm font-medium transition-all disabled:opacity-40 flex items-center justify-center gap-2"
              style={{ background: `${meta.color}15`, color: meta.color, border: `1px solid ${meta.color}30` }}>
              {status === 'pending' ? <><Activity size={13} className="animate-spin" /> Processing…</> : <><ArrowUpRight size={13} /> Confirm Deposit</>}
            </button>
          </div>
        )}
      </motion.div>
    </div>
  )
}

function VolGauge({ current, cap, color }: { current: number; cap: number; color: string }) {
  const pct = (current / cap) * 100
  const warn = pct > 80
  const critical = pct > 95
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-slate-500">Rolling Vol</span>
        <span className={`font-mono ${critical ? 'text-red-400' : warn ? 'text-yellow-400' : 'text-slate-300'}`}>
          {current.toFixed(1)}% / {cap}%
        </span>
      </div>
      <div className="h-2 bg-border rounded-full overflow-hidden relative">
        <motion.div className="h-full rounded-full transition-all"
          style={{ width: `${Math.min(pct, 100)}%`, background: critical ? '#ef4444' : warn ? '#f59e0b' : color }}
          animate={{ opacity: critical ? [1, 0.5, 1] : 1 }}
          transition={{ repeat: critical ? Infinity : 0, duration: 0.8 }}
        />
        {}
        <div className="absolute top-0 h-full w-px bg-yellow-400/40" style={{ left: '80%' }} />
      </div>
      {critical && <p className="text-xs text-red-400 mt-1 flex items-center gap-1"><AlertTriangle size={9} /> Near vol cap — agents may be restricted</p>}
    </div>
  )
}

function PoolCard({
  pool, volData, tvlHistory, onDeposit,
}: {
  pool: typeof pools[0]
  volData: Record<string, number>
  tvlHistory: Record<string, { time: string; value: number }[]>
  onDeposit: (pool: typeof pools[0]) => void
}) {
  const meta = POOL_META[pool.id as keyof typeof POOL_META]
  const Icon = meta.icon
  const history = tvlHistory[pool.id] ?? []
  const vol = volData[pool.id] ?? 0
  const utilization = (pool.tvl / meta.maxCapacity) * 100
  const [expanded, setExpanded] = useState(false)
  const poolAgents = agents.filter(a => a.risk.toLowerCase() === pool.name.toLowerCase())

  return (
    <motion.div initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }}
      className="card hover:border-opacity-40 transition-all"
      style={{ borderColor: `${meta.color}25` }}>

      {}
      <div className="flex items-start justify-between mb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h2 className="font-bold text-white text-base">{pool.name}</h2>
            <span className="text-xs px-2 py-0.5 rounded-full border font-medium"
              style={{ color: meta.color, borderColor: `${meta.color}30`, background: `${meta.color}10` }}>
              {meta.riskLabel}
            </span>
          </div>
          <p className="text-xs text-slate-500 max-w-xs">{meta.description}</p>
        </div>
        <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0" style={{ background: `${meta.color}15` }}>
          <Icon size={18} style={{ color: meta.color }} />
        </div>
      </div>

      {}
      <div className="grid grid-cols-3 gap-2 mb-4">
        {[
          { label: 'TVL', value: `$${(pool.tvl / 1e6).toFixed(1)}M`, icon: DollarSign, color: 'text-white' },
          { label: 'APY', value: `${pool.apy}%`, icon: TrendingUp, color: 'text-green' },
          { label: 'Agents', value: pool.agents, icon: Users, color: 'text-slate-300' },
        ].map(m => (
          <div key={m.label} className="bg-slate-900/60 rounded-lg p-2.5">
            <div className="flex items-center gap-1 mb-1">
              <m.icon size={10} className="text-slate-500" />
              <span className="text-xs text-slate-500">{m.label}</span>
            </div>
            <p className={`font-bold font-mono text-sm ${m.color}`}>{m.value}</p>
          </div>
        ))}
      </div>

      {}
      <div className="mb-3">
        <div className="flex justify-between text-xs mb-1">
          <span className="text-slate-500">Capacity</span>
          <span className="text-slate-400 font-mono">{utilization.toFixed(1)}% of ${(meta.maxCapacity / 1e6).toFixed(0)}M max</span>
        </div>
        <div className="h-1.5 bg-border rounded-full overflow-hidden">
          <div className="h-full rounded-full transition-all" style={{ width: `${utilization}%`, background: meta.color }} />
        </div>
      </div>

      {}
      <div className="mb-4">
        <VolGauge current={vol} cap={pool.volatilityCap} color={meta.color} />
      </div>

      {}
      <ResponsiveContainer width="100%" height={60}>
        <AreaChart data={history}>
          <defs>
            <linearGradient id={`grad-${pool.id}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={meta.color} stopOpacity={0.3} />
              <stop offset="95%" stopColor={meta.color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis dataKey="time" hide />
          <Tooltip contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 8, fontSize: 10 }}
            formatter={(v: number) => [`$${v.toFixed(2)}M`, 'TVL']} />
          <Area type="monotone" dataKey="value" stroke={meta.color} strokeWidth={1.5} fill={`url(#grad-${pool.id})`} />
        </AreaChart>
      </ResponsiveContainer>

      {}
      <div className="flex gap-1.5 mt-3 mb-4 flex-wrap">
        {meta.strategies.map(s => (
          <span key={s} className="text-xs px-2 py-0.5 rounded-md bg-slate-800 text-slate-400">{s}</span>
        ))}
      </div>

      {}
      <button onClick={() => setExpanded(e => !e)}
        className="w-full flex items-center justify-between text-xs text-slate-500 hover:text-slate-300 transition-colors mb-3">
        <span>{poolAgents.length} agents in this pool</span>
        {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
      </button>
      <AnimatePresence>
        {expanded && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden mb-3">
            <div className="space-y-1.5">
              {poolAgents.map(a => (
                <div key={a.id} className="flex items-center justify-between text-xs p-2 rounded-lg bg-slate-900/50">
                  <span className="text-slate-300 font-mono">{a.name}</span>
                  <div className="flex items-center gap-3">
                    <span className="text-slate-500">Sharpe <span className="text-green">{a.sharpe}</span></span>
                    <span className="text-slate-500">Alloc <span className="font-mono" style={{ color: meta.color }}>{a.allocation}%</span></span>
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <button onClick={() => onDeposit(pool)}
        className="w-full py-2.5 rounded-lg text-sm font-medium transition-all flex items-center justify-center gap-2"
        style={{ background: `${meta.color}12`, color: meta.color, border: `1px solid ${meta.color}25` }}>
        <ArrowUpRight size={13} /> Deposit into {pool.name}
      </button>
    </motion.div>
  )
}

export default function RiskPools() {
  const [depositPool, setDepositPool] = useState<typeof pools[0] | null>(null)
  const [tvlTab, setTvlTab] = useState<'combined' | 'conservative' | 'balanced' | 'aggressive'>('combined')
  const volData = useRollingVol()
  const tvlHistory = useTVLHistory()
  const combinedTVL = mergeTVL(tvlHistory)

  const totalTVL = pools.reduce((s, p) => s + p.tvl, 0)
  const weightedAPY = pools.reduce((s, p) => s + p.apy * p.tvl, 0) / totalTVL
  const totalAgents = pools.reduce((s, p) => s + p.agents, 0)

  const scatterData = pools.map(p => ({
    name: p.name,
    x: p.volatilityCap,
    y: p.apy,
    z: p.tvl / 1e6,
    color: POOL_META[p.id as keyof typeof POOL_META].color,
  }))

  const radarData = [
    { metric: 'APY', Conservative: 25, Balanced: 53, Aggressive: 100 },
    { metric: 'Safety', Conservative: 100, Balanced: 65, Aggressive: 30 },
    { metric: 'Liquidity', Conservative: 90, Balanced: 75, Aggressive: 60 },
    { metric: 'Agents', Conservative: 50, Balanced: 83, Aggressive: 100 },
    { metric: 'Capacity', Conservative: 42, Balanced: 44, Aggressive: 41 },
    { metric: 'Diversif.', Conservative: 70, Balanced: 85, Aggressive: 60 },
  ]

  const corrMatrix = [
    { pool: 'Conservative', Conservative: 1.00, Balanced: 0.42, Aggressive: 0.18 },
    { pool: 'Balanced',     Conservative: 0.42, Balanced: 1.00, Aggressive: 0.61 },
    { pool: 'Aggressive',   Conservative: 0.18, Balanced: 0.61, Aggressive: 1.00 },
  ]

  const corrColor = (v: number) => {
    if (v >= 0.9) return 'bg-red-500/60 text-red-200'
    if (v >= 0.6) return 'bg-yellow-500/40 text-yellow-200'
    if (v >= 0.3) return 'bg-blue-500/30 text-blue-200'
    return 'bg-green/20 text-green'
  }

  return (
    <div className="space-y-5">
      {depositPool && <DepositModal pool={depositPool} onClose={() => setDepositPool(null)} />}

      {}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Risk Pools</h1>
          <p className="text-slate-500 text-sm mt-0.5">Unified capital pools with enforced volatility budgets</p>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <div className="px-3 py-1.5 rounded-lg bg-surface border border-border">
            <span className="text-slate-500">Protocol TVL </span>
            <span className="font-mono text-white">${(totalTVL / 1e6).toFixed(1)}M</span>
          </div>
          <div className="px-3 py-1.5 rounded-lg bg-surface border border-border">
            <span className="text-slate-500">Blended APY </span>
            <span className="font-mono text-green">{weightedAPY.toFixed(1)}%</span>
          </div>
          <div className="px-3 py-1.5 rounded-lg bg-surface border border-border">
            <span className="text-slate-500">Active Agents </span>
            <span className="font-mono text-cyan">{totalAgents}</span>
          </div>
        </div>
      </div>

      {}
      <div className="grid grid-cols-3 gap-5">
        {pools.map((pool, i) => (
          <PoolCard key={pool.id} pool={pool} volData={volData} tvlHistory={tvlHistory} onDeposit={setDepositPool} />
        ))}
      </div>

      {}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <BarChart2 size={13} className="text-slate-400" /> TVL History
          </h3>
          <div className="flex gap-1">
            {(['combined', 'conservative', 'balanced', 'aggressive'] as const).map(t => (
              <button key={t} onClick={() => setTvlTab(t)}
                className={`text-xs px-2.5 py-1 rounded-lg capitalize transition-all ${
                  tvlTab === t ? 'bg-cyan/10 text-cyan border border-cyan/20' : 'text-slate-500 hover:text-slate-300'
                }`}>
                {t}
              </button>
            ))}
          </div>
        </div>
        <ResponsiveContainer width="100%" height={180}>
          {tvlTab === 'combined' ? (
            <AreaChart data={combinedTVL}>
              <defs>
                {(['Conservative', 'Balanced', 'Aggressive'] as const).map((name, i) => {
                  const colors = ['#10b981', '#3b82f6', '#a855f7']
                  return (
                    <linearGradient key={name} id={`tvl-${name}`} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={colors[i]} stopOpacity={0.3} />
                      <stop offset="95%" stopColor={colors[i]} stopOpacity={0} />
                    </linearGradient>
                  )
                })}
              </defs>
              <XAxis dataKey="time" hide />
              <YAxis tickFormatter={v => `$${v}M`} tick={{ fill: '#64748b', fontSize: 10 }} width={45} />
              <Tooltip contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 8, fontSize: 10 }}
                formatter={(v: number) => [`$${v.toFixed(2)}M`]} />
              <Area type="monotone" dataKey="Conservative" stroke="#10b981" strokeWidth={1.5} fill="url(#tvl-Conservative)" />
              <Area type="monotone" dataKey="Balanced" stroke="#3b82f6" strokeWidth={1.5} fill="url(#tvl-Balanced)" />
              <Area type="monotone" dataKey="Aggressive" stroke="#a855f7" strokeWidth={1.5} fill="url(#tvl-Aggressive)" />
            </AreaChart>
          ) : (
            <AreaChart data={tvlHistory[tvlTab]}>
              <defs>
                <linearGradient id="tvl-single" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={POOL_META[tvlTab].color} stopOpacity={0.3} />
                  <stop offset="95%" stopColor={POOL_META[tvlTab].color} stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="time" hide />
              <YAxis tickFormatter={v => `$${v}M`} tick={{ fill: '#64748b', fontSize: 10 }} width={45} />
              <Tooltip contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 8, fontSize: 10 }}
                formatter={(v: number) => [`$${v.toFixed(2)}M`, 'TVL']} />
              <Area type="monotone" dataKey="value" stroke={POOL_META[tvlTab].color} strokeWidth={2} fill="url(#tvl-single)" />
            </AreaChart>
          )}
        </ResponsiveContainer>
      </div>

      {}
      <div className="grid grid-cols-2 gap-4">
        {}
        <div className="card">
          <h3 className="text-sm font-semibold text-white mb-1">Risk / Return Profile</h3>
          <p className="text-xs text-slate-500 mb-4">Bubble size = TVL · X = volatility cap · Y = APY</p>
          <ResponsiveContainer width="100%" height={200}>
            <ScatterChart>
              <XAxis type="number" dataKey="x" name="Vol Cap" unit="%" tick={{ fill: '#64748b', fontSize: 10 }}
                label={{ value: 'Volatility Cap (%)', position: 'insideBottom', offset: -5, fill: '#64748b', fontSize: 10 }} />
              <YAxis type="number" dataKey="y" name="APY" unit="%" tick={{ fill: '#64748b', fontSize: 10 }}
                label={{ value: 'APY (%)', angle: -90, position: 'insideLeft', fill: '#64748b', fontSize: 10 }} />
              <ZAxis type="number" dataKey="z" range={[400, 1200]} />
              <Tooltip cursor={{ strokeDasharray: '3 3' }}
                contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 8, fontSize: 11 }}
                formatter={(v: number, name: string) => [name === 'z' ? `$${v.toFixed(1)}M TVL` : `${v}%`, name === 'x' ? 'Vol Cap' : name === 'y' ? 'APY' : 'TVL']} />
              <Scatter data={scatterData} shape={(props: any) => {
                const { cx, cy, payload } = props
                return (
                  <g>
                    <circle cx={cx} cy={cy} r={Math.sqrt(payload.z) * 3} fill={payload.color} fillOpacity={0.3} stroke={payload.color} strokeWidth={2} />
                    <text x={cx} y={cy - Math.sqrt(payload.z) * 3 - 5} textAnchor="middle" fill={payload.color} fontSize={10}>{payload.name}</text>
                  </g>
                )
              }} />
            </ScatterChart>
          </ResponsiveContainer>
        </div>

        {}
        <div className="card">
          <h3 className="text-sm font-semibold text-white mb-1">Pool Comparison Radar</h3>
          <p className="text-xs text-slate-500 mb-2">Normalized scores across key dimensions</p>
          <ResponsiveContainer width="100%" height={220}>
            <RadarChart data={radarData}>
              <PolarGrid stroke="#1f2937" />
              <PolarAngleAxis dataKey="metric" tick={{ fill: '#64748b', fontSize: 10 }} />
              <Radar name="Conservative" dataKey="Conservative" stroke="#10b981" fill="#10b981" fillOpacity={0.15} />
              <Radar name="Balanced" dataKey="Balanced" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.15} />
              <Radar name="Aggressive" dataKey="Aggressive" stroke="#a855f7" fill="#a855f7" fillOpacity={0.15} />
              <Tooltip contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 8, fontSize: 10 }} />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {}
      <div className="card">
        <h3 className="text-sm font-semibold text-white mb-1">Pool Correlation Matrix</h3>
        <p className="text-xs text-slate-500 mb-4">Lower correlation = better diversification benefit across pools</p>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr>
                <th className="text-left pb-2 text-slate-500 font-medium w-32">Pool</th>
                {corrMatrix.map(r => <th key={r.pool} className="pb-2 text-slate-500 font-medium text-center">{r.pool}</th>)}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {corrMatrix.map(row => (
                <tr key={row.pool}>
                  <td className="py-2.5 font-semibold text-slate-300">{row.pool}</td>
                  {(['Conservative', 'Balanced', 'Aggressive'] as const).map(col => {
                    const v = row[col]
                    return (
                      <td key={col} className="py-2.5 text-center">
                        <span className={`inline-block px-3 py-1 rounded-lg font-mono text-xs ${corrColor(v)}`}>
                          {v.toFixed(2)}
                        </span>
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex items-center gap-4 mt-3 text-xs text-slate-500">
            <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded bg-green/20 inline-block" /> Low (&lt;0.3)</span>
            <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded bg-blue-500/30 inline-block" /> Moderate (0.3–0.6)</span>
            <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded bg-yellow-500/40 inline-block" /> High (0.6–0.9)</span>
            <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded bg-red-500/60 inline-block" /> Very High (&gt;0.9)</span>
          </div>
        </div>
      </div>

      {}
      <div className="card">
        <h3 className="text-sm font-semibold text-white mb-4">Full Pool Comparison</h3>
        <table className="w-full text-xs">
          <thead>
            <tr className="text-slate-500 border-b border-border">
              {['Pool', 'TVL', 'APY', 'Vol Cap', 'Drawdown Limit', 'Agents', 'Capacity Used', 'Allocation Method'].map(h => (
                <th key={h} className="text-left pb-2 font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {pools.map(p => {
              const meta = POOL_META[p.id as keyof typeof POOL_META]
              const util = ((p.tvl / meta.maxCapacity) * 100).toFixed(1)
              return (
                <tr key={p.id} className="hover:bg-white/2 transition-colors">
                  <td className="py-3 font-semibold" style={{ color: meta.color }}>{p.name}</td>
                  <td className="py-3 font-mono text-white">${(p.tvl / 1e6).toFixed(1)}M</td>
                  <td className="py-3 font-mono text-green">{p.apy}%</td>
                  <td className="py-3 font-mono text-slate-300">{p.volatilityCap}%</td>
                  <td className="py-3 font-mono text-yellow-400">{meta.drawdownLimit}%</td>
                  <td className="py-3 text-slate-300">{p.agents}</td>
                  <td className="py-3">
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-1.5 bg-border rounded-full overflow-hidden">
                        <div className="h-full rounded-full" style={{ width: `${util}%`, background: meta.color }} />
                      </div>
                      <span className="font-mono text-slate-400">{util}%</span>
                    </div>
                  </td>
                  <td className="py-3 text-slate-400">MWU Algorithm</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
