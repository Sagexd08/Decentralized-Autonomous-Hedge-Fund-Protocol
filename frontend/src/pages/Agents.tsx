import { useState, useEffect, useCallback, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import {
  Search, AlertTriangle, CheckCircle, Star, StarOff, BarChart2,
  List, SlidersHorizontal, TrendingUp, TrendingDown, Zap, Shield,
  Award, Target, Activity, X, ChevronUp, ChevronDown, Plus,
  ArrowUpRight, Clock, Users, DollarSign,
} from 'lucide-react'
import {
  LineChart, Line, AreaChart, Area, RadarChart, Radar,
  PolarGrid, PolarAngleAxis, ResponsiveContainer, Tooltip,
} from 'recharts'
import { useAgents } from '../hooks/useAgents'
import { generateTimeSeries } from '../utils/mockData'
import DelegationModal from '../components/agents/DelegationModal'
import { useProtocolStore } from '../store/protocolStore'
import { API_BASE_URL } from '../utils/api'

const RISK_COLORS: Record<string, string> = {
  Conservative: '#10b981', Balanced: '#3b82f6', Aggressive: '#a855f7',
}
const RISK_POOL: Record<string, 0 | 1 | 2> = {
  Conservative: 0, Balanced: 1, Aggressive: 2,
  conservative: 0, balanced: 1, aggressive: 2,
}
const TOKEN_PRICE_USD: Record<string, number> = {
  WBTC: 30000, USDC: 1, LINK: 15, UNI: 8, WETH: 2000,
}

type SortKey = 'score' | 'sharpe' | 'pnl' | 'drawdown' | 'allocation' | 'stake' | 'volatility'
type ViewMode = 'grid' | 'leaderboard'

interface AgentPortfolio {
  token_balances: Record<string, string>
  pnl_wei: string
  trading_active: boolean
}

type Agent = {
  id: string; address?: string; name: string; strategy: string; risk: string
  sharpe: number; drawdown: number; allocation: number; pnl: number
  volatility: number; stake: number; status: string; score: number
  description?: string
}

function getBadges(a: Agent, allAgents: Agent[]) {
  const badges: { label: string; color: string; icon: React.ReactNode }[] = []
  const sorted = [...allAgents]
  if (sorted.sort((x, y) => y.sharpe - x.sharpe)[0]?.id === a.id)
    badges.push({ label: 'Top Sharpe', color: 'text-cyan border-cyan/30 bg-cyan/10', icon: <TrendingUp size={9} /> })
  if (sorted.sort((x, y) => y.pnl - x.pnl)[0]?.id === a.id)
    badges.push({ label: 'Top PnL', color: 'text-green border-green/30 bg-green/10', icon: <Award size={9} /> })
  if (sorted.sort((x, y) => Math.abs(x.drawdown) - Math.abs(y.drawdown))[0]?.id === a.id)
    badges.push({ label: 'Lowest DD', color: 'text-purple border-purple/30 bg-purple/10', icon: <Shield size={9} /> })
  if (sorted.sort((x, y) => y.score - x.score)[0]?.id === a.id)
    badges.push({ label: '#1 Ranked', color: 'text-yellow-400 border-yellow-400/30 bg-yellow-400/10', icon: <Star size={9} /> })
  return badges
}

function scoreBreakdown(a: Agent) {
  return {
    sharpe: Math.min(a.sharpe / 3.5 * 40, 40),
    drawdown: Math.max(40 - Math.abs(a.drawdown) * 2, 0),
    consistency: a.score - Math.min(a.sharpe / 3.5 * 40, 40) - Math.max(40 - Math.abs(a.drawdown) * 2, 0),
  }
}

function computePortfolioUSD(balances: Record<string, string>): number {
  return Object.entries(balances).reduce((sum, [sym, rawAmt]) => {
    const price = TOKEN_PRICE_USD[sym] ?? 0
    const decimals = sym === 'WBTC' ? 8 : sym === 'USDC' ? 6 : 18
    return sum + (Number(rawAmt) / Math.pow(10, decimals)) * price
  }, 0)
}

function genSparkline(pnl: number) {
  return generateTimeSeries(30, 100, Math.abs(pnl) * 0.3).map((p, i) => ({
    t: i, v: p.value + (pnl > 0 ? i * 0.1 : -i * 0.05),
  }))
}

function DeployAgentModal({ onClose }: { onClose: () => void }) {
  const [name, setName] = useState('')
  const [strategy, setStrategy] = useState('')
  const [risk, setRisk] = useState('Balanced')
  const [stake, setStake] = useState('')
  const [submitted, setSubmitted] = useState(false)

  const handleSubmit = () => {
    if (!name || !strategy || !stake) return
    setSubmitted(true)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }}
        className="bg-slate-950 border border-border rounded-2xl w-full max-w-md">
        <div className="flex items-center justify-between p-5 border-b border-border">
          <h2 className="text-sm font-semibold text-white flex items-center gap-2"><Zap size={13} className="text-cyan" /> Deploy New Agent</h2>
          <button onClick={onClose} className="text-slate-500 hover:text-white"><X size={16} /></button>
        </div>
        {submitted ? (
          <div className="p-8 text-center space-y-3">
            <CheckCircle size={40} className="text-green mx-auto" />
            <p className="text-white font-semibold">Agent Submitted</p>
            <p className="text-xs text-slate-500">Your agent enters a 7-day simulation probation period before going live.</p>
            <button onClick={onClose} className="mt-2 px-6 py-2 rounded-lg text-sm bg-green/10 text-green border border-green/20">Done</button>
          </div>
        ) : (
          <div className="p-5 space-y-4">
            <div>
              <label className="text-xs text-slate-400 mb-1.5 block">Agent Name</label>
              <input value={name} onChange={e => setName(e.target.value)} placeholder="e.g. AlphaBot v2"
                className="w-full bg-slate-900 border border-border rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-cyan/50" />
            </div>
            <div>
              <label className="text-xs text-slate-400 mb-1.5 block">Strategy Description</label>
              <textarea value={strategy} onChange={e => setStrategy(e.target.value)} rows={3}
                placeholder="Describe your strategy — this gets hashed on-chain as strategyHash"
                className="w-full bg-slate-900 border border-border rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-cyan/50 resize-none" />
            </div>
            <div>
              <label className="text-xs text-slate-400 mb-1.5 block">Risk Pool</label>
              <div className="flex gap-2">
                {['Conservative', 'Balanced', 'Aggressive'].map(r => (
                  <button key={r} onClick={() => setRisk(r)}
                    className={`flex-1 py-1.5 rounded-lg text-xs font-medium border transition-all ${risk === r ? 'text-white' : 'text-slate-500 border-border'}`}
                    style={risk === r ? { background: `${RISK_COLORS[r]}15`, borderColor: `${RISK_COLORS[r]}40`, color: RISK_COLORS[r] } : {}}>
                    {r}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="text-xs text-slate-400 mb-1.5 block">Initial Stake (DAC tokens)</label>
              <input value={stake} onChange={e => setStake(e.target.value)} type="number" placeholder="Min 10,000"
                className="w-full bg-slate-900 border border-border rounded-lg px-3 py-2 text-sm text-slate-100 font-mono placeholder-slate-600 focus:outline-none focus:border-cyan/50" />
              <p className="text-xs text-slate-600 mt-1">Minimum stake: 10,000 DAC · Locked for 7-day probation</p>
            </div>
            {strategy && (
              <div className="p-2 bg-slate-900 rounded-lg border border-border text-xs">
                <span className="text-slate-500">Strategy hash: </span>
                <span className="font-mono text-cyan">0x{Array.from(strategy).reduce((h, c) => (h * 31 + c.charCodeAt(0)) & 0xffffffff, 0).toString(16).padStart(8, '0')}…</span>
              </div>
            )}
            <button onClick={handleSubmit} disabled={!name || !strategy || !stake}
              className="w-full py-2.5 rounded-xl text-sm font-medium bg-cyan/10 text-cyan border border-cyan/20 hover:bg-cyan/20 transition-all disabled:opacity-40 flex items-center justify-center gap-2">
              <Plus size={13} /> Register Agent
            </button>
          </div>
        )}
      </motion.div>
    </div>
  )
}

function AgentDrawer({ agent, allAgents, portfolio, onClose, onDelegate }: {
  agent: Agent; allAgents: Agent[]; portfolio?: AgentPortfolio
  onClose: () => void; onDelegate: () => void
}) {
  const sparkline = useMemo(() => genSparkline(agent.pnl), [agent.pnl])
  const breakdown = scoreBreakdown(agent)
  const badges = getBadges(agent, allAgents)
  const color = RISK_COLORS[agent.risk] ?? '#64748b'
  const portfolioUSD = portfolio ? computePortfolioUSD(portfolio.token_balances) : null

  const radarData = [
    { m: 'Sharpe', v: Math.min(agent.sharpe / 3.5 * 100, 100) },
    { m: 'PnL', v: Math.min(agent.pnl / 60 * 100, 100) },
    { m: 'Safety', v: Math.max(100 - Math.abs(agent.drawdown) * 4, 0) },
    { m: 'Alloc', v: agent.allocation * 2 },
    { m: 'Score', v: agent.score },
    { m: 'Stake', v: Math.min(agent.stake / 60000 * 100, 100) },
  ]

  return (
    <motion.div initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }}
      transition={{ type: 'spring', damping: 25, stiffness: 200 }}
      className="fixed right-0 top-0 h-full w-[420px] bg-slate-950 border-l border-border z-40 overflow-y-auto shadow-2xl">
      <div className="flex items-center justify-between p-5 border-b border-border sticky top-0 bg-slate-950 z-10">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center font-bold text-sm"
            style={{ background: `${color}20`, color }}>
            {agent.name.slice(0, 2).toUpperCase()}
          </div>
          <div>
            <p className="text-sm font-bold text-white">{agent.name}</p>
            <p className="text-xs text-slate-500">{agent.strategy}</p>
          </div>
        </div>
        <button onClick={onClose} className="text-slate-500 hover:text-white"><X size={16} /></button>
      </div>

      <div className="p-5 space-y-5">
        {}
        {badges.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {badges.map(b => (
              <span key={b.label} className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border ${b.color}`}>
                {b.icon} {b.label}
              </span>
            ))}
          </div>
        )}

        {}
        <div className="flex items-center justify-between">
          <span className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border font-medium`}
            style={{ color, borderColor: `${color}30`, background: `${color}10` }}>
            <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: color }} />
            {agent.risk} · {agent.status}
          </span>
          {portfolio?.trading_active && (
            <span className="flex items-center gap-1 text-xs text-green bg-green/10 border border-green/20 px-2 py-0.5 rounded-full">
              <Activity size={9} className="animate-pulse" /> Live Trading
            </span>
          )}
        </div>

        {}
        {agent.description && (
          <div className="p-3 bg-slate-900/60 rounded-xl border border-border">
            <p className="text-xs text-slate-400 font-medium mb-1.5">Algorithm & Mathematical Model</p>
            <p className="text-xs text-slate-400 leading-relaxed">{agent.description}</p>
          </div>
        )}

        {}
        <div className="card p-3">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs text-slate-500">30-Day PnL Trend</p>
            <span className={`text-sm font-bold font-mono ${agent.pnl >= 0 ? 'text-green' : 'text-red-400'}`}>
              {agent.pnl >= 0 ? '+' : ''}{agent.pnl}%
            </span>
          </div>
          <ResponsiveContainer width="100%" height={80}>
            <AreaChart data={sparkline}>
              <defs>
                <linearGradient id={`spark-${agent.id}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={color} stopOpacity={0.3} />
                  <stop offset="95%" stopColor={color} stopOpacity={0} />
                </linearGradient>
              </defs>
              <Area type="monotone" dataKey="v" stroke={color} strokeWidth={2} fill={`url(#spark-${agent.id})`} dot={false} />
              <Tooltip contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 6, fontSize: 9 }}
                formatter={(v: number) => [v.toFixed(1)]} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {}
        <div className="grid grid-cols-3 gap-2">
          {[
            { label: 'Sharpe', value: agent.sharpe, color: 'text-cyan' },
            { label: 'Sortino', value: (agent.sharpe * 1.3).toFixed(2), color: 'text-cyan' },
            { label: 'Drawdown', value: `${agent.drawdown}%`, color: 'text-red-400' },
            { label: 'Volatility', value: `${agent.volatility}%`, color: 'text-yellow-400' },
            { label: 'Allocation', value: `${agent.allocation}%`, color: 'text-purple' },
            { label: 'Stake', value: `$${(agent.stake / 1000).toFixed(0)}K`, color: 'text-white' },
          ].map(m => (
            <div key={m.label} className="bg-slate-900 rounded-lg p-2.5 text-center">
              <p className={`text-sm font-bold font-mono ${m.color}`}>{m.value}</p>
              <p className="text-xs text-slate-600">{m.label}</p>
            </div>
          ))}
        </div>

        {}
        <div className="card p-3">
          <p className="text-xs text-slate-500 mb-3">Score Breakdown ({agent.score}/100)</p>
          {[
            { label: 'Sharpe (40%)', value: breakdown.sharpe, max: 40, color: '#00f5ff' },
            { label: 'Drawdown (30%)', value: breakdown.drawdown, max: 40, color: '#10b981' },
            { label: 'Consistency (30%)', value: Math.max(breakdown.consistency, 0), max: 30, color: '#a855f7' },
          ].map(s => (
            <div key={s.label} className="mb-2">
              <div className="flex justify-between text-xs mb-1">
                <span className="text-slate-500">{s.label}</span>
                <span className="font-mono" style={{ color: s.color }}>{s.value.toFixed(1)}</span>
              </div>
              <div className="h-1.5 bg-border rounded-full overflow-hidden">
                <div className="h-full rounded-full" style={{ width: `${(s.value / s.max) * 100}%`, background: s.color }} />
              </div>
            </div>
          ))}
        </div>

        {}
        <div className="card p-3">
          <p className="text-xs text-slate-500 mb-2">Performance Radar</p>
          <ResponsiveContainer width="100%" height={180}>
            <RadarChart data={radarData}>
              <PolarGrid stroke="#1f2937" />
              <PolarAngleAxis dataKey="m" tick={{ fill: '#64748b', fontSize: 9 }} />
              <Radar dataKey="v" stroke={color} fill={color} fillOpacity={0.2} />
              <Tooltip contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 6, fontSize: 9 }} />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        {}
        {portfolioUSD !== null && (
          <div className="card p-3">
            <p className="text-xs text-slate-500 mb-2">Live Portfolio</p>
            <div className="flex justify-between text-sm">
              <span className="text-slate-400">Total Value</span>
              <span className="font-mono text-white">${portfolioUSD.toLocaleString('en-US', { maximumFractionDigits: 2 })}</span>
            </div>
            {Object.entries(portfolio?.token_balances ?? {}).map(([sym, raw]) => {
              const decimals = sym === 'WBTC' ? 8 : sym === 'USDC' ? 6 : 18
              const amt = Number(raw) / Math.pow(10, decimals)
              if (amt < 0.0001) return null
              return (
                <div key={sym} className="flex justify-between text-xs text-slate-500 mt-1">
                  <span>{sym}</span>
                  <span className="font-mono">{amt.toFixed(4)}</span>
                </div>
              )
            })}
          </div>
        )}

        {}
        <div className="space-y-2">
          <button onClick={onDelegate}
            className="w-full py-2.5 rounded-xl text-sm font-medium bg-cyan/10 text-cyan border border-cyan/20 hover:bg-cyan/20 transition-all flex items-center justify-center gap-2">
            <ArrowUpRight size={13} /> Delegate Capital
          </button>
          <div className="flex gap-2 text-xs text-slate-500">
            <span className="font-mono">{agent.id}</span>
            <span>·</span>
            <span>Registered 14d ago</span>
          </div>
        </div>
      </div>
    </motion.div>
  )
}

function ComparisonPanel({ agents, onRemove }: { agents: Agent[]; onRemove: (id: string) => void }) {
  if (agents.length < 2) return null
  const metrics: { key: keyof Agent; label: string; better: 'higher' | 'lower' }[] = [
    { key: 'score', label: 'Score', better: 'higher' },
    { key: 'sharpe', label: 'Sharpe', better: 'higher' },
    { key: 'pnl', label: 'PnL %', better: 'higher' },
    { key: 'drawdown', label: 'Drawdown', better: 'higher' },
    { key: 'volatility', label: 'Volatility', better: 'lower' },
    { key: 'allocation', label: 'Allocation %', better: 'higher' },
    { key: 'stake', label: 'Stake', better: 'higher' },
  ]

  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
      className="card border-cyan/20">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-white">Agent Comparison</h3>
        <span className="text-xs text-slate-500">{agents.length} agents selected</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-border">
              <th className="text-left pb-2 text-slate-500 font-medium">Metric</th>
              {agents.map(a => (
                <th key={a.id} className="pb-2 text-center">
                  <div className="flex items-center justify-center gap-1">
                    <span style={{ color: RISK_COLORS[a.risk] }}>{a.name}</span>
                    <button onClick={() => onRemove(a.id)} className="text-slate-600 hover:text-slate-400"><X size={10} /></button>
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {metrics.map(m => {
              const vals = agents.map(a => Number(a[m.key]))
              const best = m.better === 'higher' ? Math.max(...vals) : Math.min(...vals)
              return (
                <tr key={m.key}>
                  <td className="py-2 text-slate-500">{m.label}</td>
                  {agents.map((a, i) => {
                    const v = Number(a[m.key])
                    const isBest = v === best
                    return (
                      <td key={a.id} className="py-2 text-center">
                        <span className={`font-mono ${isBest ? 'text-green font-bold' : 'text-slate-400'}`}>
                          {m.key === 'stake' ? `$${(v / 1000).toFixed(0)}K` : v}
                          {isBest && <span className="ml-1 text-green">↑</span>}
                        </span>
                      </td>
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </motion.div>
  )
}

function AgentCard({ agent, allAgents, rank, isWatched, isCompared, onWatch, onCompare, onSelect, onDelegate, portfolio, isTrading, isLoading, onStartTrading, onStopTrading, delegatedEth }: {
  agent: Agent; allAgents: Agent[]; rank: number
  isWatched: boolean; isCompared: boolean
  onWatch: () => void; onCompare: () => void; onSelect: () => void; onDelegate: () => void
  portfolio?: AgentPortfolio; isTrading: boolean; isLoading: boolean
  onStartTrading: () => void; onStopTrading: () => void
  delegatedEth?: number
}) {
  const color = RISK_COLORS[agent.risk] ?? '#64748b'
  const badges = getBadges(agent, allAgents)
  const sparkline = useMemo(() => genSparkline(agent.pnl), [agent.pnl])

  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
      className={`card cursor-pointer hover:border-opacity-60 transition-all group relative ${isCompared ? 'ring-1 ring-cyan/40' : ''}`}
      style={{ borderColor: `${color}20` }}
      onClick={onSelect}>

      {}
      <div className="absolute -top-2 -left-2 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold"
        style={{ background: rank <= 3 ? color : '#1f2937', color: rank <= 3 ? '#000' : '#64748b' }}>
        {rank}
      </div>

      {}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold"
            style={{ background: `${color}20`, color }}>
            {agent.name.slice(0, 2)}
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="text-sm font-bold text-white group-hover:text-cyan transition-colors">{agent.name}</span>
              {agent.status === 'active'
                ? <CheckCircle size={11} className="text-green" />
                : <AlertTriangle size={11} className="text-yellow-400" />}
              {isTrading && <span className="w-1.5 h-1.5 rounded-full bg-green animate-pulse" />}
            </div>
            <p className="text-xs text-slate-500">{agent.strategy}</p>
          </div>
        </div>
        <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
          <button onClick={onWatch} className={`p-1 rounded transition-colors ${isWatched ? 'text-yellow-400' : 'text-slate-600 hover:text-slate-400'}`}>
            {isWatched ? <Star size={12} fill="currentColor" /> : <Star size={12} />}
          </button>
          <button onClick={onCompare}
            className={`p-1 rounded text-xs transition-colors ${isCompared ? 'text-cyan' : 'text-slate-600 hover:text-slate-400'}`}>
            <BarChart2 size={12} />
          </button>
        </div>
      </div>

      {}
      {badges.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-3">
          {badges.map(b => (
            <span key={b.label} className={`flex items-center gap-0.5 text-xs px-1.5 py-0.5 rounded-full border ${b.color}`}>
              {b.icon} {b.label}
            </span>
          ))}
        </div>
      )}

      {}
      <div className="mb-3">
        <div className="flex justify-between text-xs mb-1">
          <span className="text-slate-500">Protocol Score</span>
          <span className="font-mono text-cyan">{agent.score}/100</span>
        </div>
        <div className="h-1.5 bg-border rounded-full overflow-hidden">
          <motion.div initial={{ width: 0 }} animate={{ width: `${agent.score}%` }} transition={{ duration: 0.8 }}
            className="h-full rounded-full" style={{ background: `linear-gradient(90deg,${color},#a855f7)` }} />
        </div>
      </div>

      {}
      <div className="grid grid-cols-4 gap-1.5 mb-3">
        {[
          { label: 'Sharpe', value: agent.sharpe, color: 'text-cyan' },
          { label: 'DD', value: `${agent.drawdown}%`, color: 'text-red-400' },
          { label: 'Alloc', value: `${agent.allocation}%`, color: 'text-purple' },
          { label: 'PnL', value: `+${agent.pnl}%`, color: 'text-green' },
        ].map(m => (
          <div key={m.label} className="bg-slate-900/60 rounded-lg p-1.5 text-center">
            <div className={`text-xs font-bold font-mono ${m.color}`}>{m.value}</div>
            <div className="text-xs text-slate-600">{m.label}</div>
          </div>
        ))}
      </div>

      {}
      <div className="mb-3 -mx-1">
        <ResponsiveContainer width="100%" height={40}>
          <AreaChart data={sparkline}>
            <defs>
              <linearGradient id={`sg-${agent.id}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={color} stopOpacity={0.3} />
                <stop offset="95%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <Area type="monotone" dataKey="v" stroke={color} strokeWidth={1.5} fill={`url(#sg-${agent.id})`} dot={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {}
      <div className="flex items-center justify-between text-xs text-slate-600 mb-3">
        <span className="font-mono">{agent.id}</span>
        <span>Stake: ${(agent.stake / 1000).toFixed(0)}K</span>
      </div>

      {}
      {delegatedEth !== undefined && delegatedEth > 0 && (
        <div className="flex items-center justify-between text-xs mb-3 px-2 py-1.5 rounded-lg bg-cyan/5 border border-cyan/15">
          <span className="text-slate-400 flex items-center gap-1"><DollarSign size={10} /> Delegated</span>
          <span className="font-mono text-cyan">{delegatedEth.toFixed(4)} ETH</span>
        </div>
      )}

      {}
      <div className="flex gap-2" onClick={e => e.stopPropagation()}>
        <button onClick={onDelegate}
          className="flex-1 py-1.5 rounded-lg text-xs font-medium bg-cyan/10 text-cyan border border-cyan/20 hover:bg-cyan/20 transition-all">
          {delegatedEth ? 'Add More' : 'Delegate'}
        </button>
        {!isTrading ? (
          <button onClick={onStartTrading}
            disabled={isLoading || !delegatedEth}
            title={!delegatedEth ? 'Delegate ETH first to enable trading' : ''}
            className="flex-1 py-1.5 rounded-lg text-xs font-medium bg-green/10 text-green border border-green/20 hover:bg-green/20 transition-all disabled:opacity-40 disabled:cursor-not-allowed">
            {isLoading ? '…' : !delegatedEth ? 'Delegate First' : 'Start AI'}
          </button>
        ) : (
          <button onClick={onStopTrading} disabled={isLoading}
            className="flex-1 py-1.5 rounded-lg text-xs font-medium bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20 transition-all disabled:opacity-50">
            {isLoading ? '…' : 'Stop AI'}
          </button>
        )}
      </div>
    </motion.div>
  )
}

export default function Agents() {
  const navigate = useNavigate()
  const { data: agentsData = [] } = useAgents()
  const agents = agentsData as Agent[]
  const { delegations, startSession } = useProtocolStore()

  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('all')
  const [sortKey, setSortKey] = useState<SortKey>('score')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const [viewMode, setViewMode] = useState<ViewMode>('grid')
  const [watchlist, setWatchlist] = useState<Set<string>>(new Set())
  const [compareList, setCompareList] = useState<string[]>([])
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null)
  const [delegateAgent, setDelegateAgent] = useState<{ id: string; name: string; risk: string; score: number; riskPool: 0 | 1 | 2 } | null>(null)
  const [showDeploy, setShowDeploy] = useState(false)
  const [portfolios, setPortfolios] = useState<Record<string, AgentPortfolio>>({})
  const [tradingErrors, setTradingErrors] = useState<Record<string, string>>({})
  const [tradingLoading, setTradingLoading] = useState<Record<string, boolean>>({})

  const fetchPortfolio = useCallback(async (agentId: string) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/agents/${agentId}/portfolio`)
      if (res.ok) {
        const data = await res.json()
        setPortfolios(prev => ({ ...prev, [agentId]: data }))
      }
    } catch {}
  }, [])

  useEffect(() => { agents.forEach(a => fetchPortfolio(a.id)) }, [agents, fetchPortfolio])

  const handleStartTrading = async (agentId: string) => {
    setTradingLoading(prev => ({ ...prev, [agentId]: true }))
    try {
      await fetch(`${API_BASE_URL}/api/agents/${agentId}/start-trading`, { method: 'POST' })
      await fetchPortfolio(agentId)

      const agent = agents.find(a => a.id === agentId)
      const delegation = delegations[agentId]
      if (agent && delegation) {
        startSession(agentId, agent.name, agent.risk, delegation.ethAmount)
      }
      navigate('/dashboard')
    } catch { setTradingErrors(prev => ({ ...prev, [agentId]: 'Network error' })) }
    finally { setTradingLoading(prev => ({ ...prev, [agentId]: false })) }
  }

  const handleStopTrading = async (agentId: string) => {
    setTradingLoading(prev => ({ ...prev, [agentId]: true }))
    try {
      await fetch(`${API_BASE_URL}/api/agents/${agentId}/stop-trading`, { method: 'POST' })
      await fetchPortfolio(agentId)

      const store = useProtocolStore.getState()
      const activeSession = store.sessions.find(s => s.agentId === agentId && s.status === 'active')
      if (activeSession) {
        store.endSession(activeSession.id, 0, activeSession.trades, activeSession.tradeRecords)
        navigate('/pnl-history')
      }
    } catch { setTradingErrors(prev => ({ ...prev, [agentId]: 'Network error' })) }
    finally { setTradingLoading(prev => ({ ...prev, [agentId]: false })) }
  }

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('desc') }
  }

  const sorted = useMemo(() => {
    let list = agents.filter(a =>
      (filter === 'all' || a.risk.toLowerCase() === filter) &&
      a.name.toLowerCase().includes(search.toLowerCase())
    )

    list = [...list.filter(a => watchlist.has(a.id)), ...list.filter(a => !watchlist.has(a.id))]
    list.sort((a, b) => {
      const av = sortKey === 'drawdown' ? Math.abs(a[sortKey]) : Number(a[sortKey])
      const bv = sortKey === 'drawdown' ? Math.abs(b[sortKey]) : Number(b[sortKey])
      return sortDir === 'desc' ? bv - av : av - bv
    })
    return list
  }, [agents, filter, search, sortKey, sortDir, watchlist])

  const compareAgents = useMemo(() => agents.filter(a => compareList.includes(a.id)), [agents, compareList])

  const totalAlloc = agents.reduce((s, a) => s + a.allocation, 0)
  const avgSharpe = agents.length ? (agents.reduce((s, a) => s + a.sharpe, 0) / agents.length).toFixed(2) : '0'
  const activeCount = agents.filter(a => portfolios[a.id]?.trading_active).length

  const SortBtn = ({ k, label }: { k: SortKey; label: string }) => (
    <button onClick={() => toggleSort(k)}
      className={`flex items-center gap-1 text-xs px-2 py-1 rounded-lg transition-all ${sortKey === k ? 'bg-cyan/10 text-cyan border border-cyan/20' : 'text-slate-500 hover:text-slate-300 border border-border'}`}>
      {label}
      {sortKey === k && (sortDir === 'desc' ? <ChevronDown size={10} /> : <ChevronUp size={10} />)}
    </button>
  )

  return (
    <div className="space-y-5">
      {showDeploy && <DeployAgentModal onClose={() => setShowDeploy(false)} />}

      <AnimatePresence>
        {selectedAgent && (
          <AgentDrawer
            agent={selectedAgent}
            allAgents={agents}
            portfolio={portfolios[selectedAgent.id]}
            onClose={() => setSelectedAgent(null)}
            onDelegate={() => {
              setDelegateAgent({ id: selectedAgent.id, name: selectedAgent.name, risk: selectedAgent.risk, score: selectedAgent.score, riskPool: RISK_POOL[selectedAgent.risk] ?? 1 })
              setSelectedAgent(null)
            }}
          />
        )}
      </AnimatePresence>

      {}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Agent Marketplace</h1>
          <p className="text-slate-500 text-sm mt-0.5">Competing autonomous strategy agents · {agents.length} registered</p>
        </div>
        <button onClick={() => setShowDeploy(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium bg-cyan/10 text-cyan border border-cyan/20 hover:bg-cyan/20 transition-all">
          <Plus size={13} /> Deploy Agent
        </button>
      </div>

      {}
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: 'Total Agents', value: agents.length, icon: Users, color: 'text-white' },
          { label: 'Live Trading', value: activeCount, icon: Activity, color: 'text-green' },
          { label: 'Avg Sharpe', value: avgSharpe, icon: TrendingUp, color: 'text-cyan' },
          { label: 'Total Allocation', value: `${totalAlloc}%`, icon: Target, color: 'text-purple' },
        ].map(s => (
          <div key={s.label} className="card py-3 px-4 flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-slate-800 flex items-center justify-center">
              <s.icon size={14} className={s.color} />
            </div>
            <div>
              <p className={`text-lg font-bold font-mono ${s.color}`}>{s.value}</p>
              <p className="text-xs text-slate-500">{s.label}</p>
            </div>
          </div>
        ))}
      </div>

      {}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 max-w-xs">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search agents…"
            className="w-full bg-surface border border-border rounded-lg pl-8 pr-3 py-2 text-sm text-slate-300 placeholder-slate-600 focus:outline-none focus:border-cyan/40" />
        </div>
        {['all', 'conservative', 'balanced', 'aggressive'].map(f => (
          <button key={f} onClick={() => setFilter(f)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize transition-all border ${filter === f ? 'bg-cyan/10 text-cyan border-cyan/20' : 'text-slate-500 border-border hover:text-slate-300'}`}>
            {f}
          </button>
        ))}
        <div className="flex gap-1 ml-auto">
          <button onClick={() => setViewMode('grid')}
            className={`p-2 rounded-lg border transition-all ${viewMode === 'grid' ? 'bg-cyan/10 text-cyan border-cyan/20' : 'text-slate-500 border-border'}`}>
            <BarChart2 size={13} />
          </button>
          <button onClick={() => setViewMode('leaderboard')}
            className={`p-2 rounded-lg border transition-all ${viewMode === 'leaderboard' ? 'bg-cyan/10 text-cyan border-cyan/20' : 'text-slate-500 border-border'}`}>
            <List size={13} />
          </button>
        </div>
      </div>

      {}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs text-slate-500 flex items-center gap-1"><SlidersHorizontal size={11} /> Sort:</span>
        {(['score', 'sharpe', 'pnl', 'drawdown', 'allocation', 'stake', 'volatility'] as SortKey[]).map(k => (
          <SortBtn key={k} k={k} label={k.charAt(0).toUpperCase() + k.slice(1)} />
        ))}
        {compareList.length > 0 && (
          <button onClick={() => setCompareList([])} className="ml-auto text-xs text-slate-500 hover:text-slate-300 flex items-center gap-1">
            <X size={10} /> Clear comparison
          </button>
        )}
      </div>

      {}
      {compareAgents.length >= 2 && (
        <ComparisonPanel agents={compareAgents} onRemove={id => setCompareList(prev => prev.filter(x => x !== id))} />
      )}

      {}
      {viewMode === 'grid' && (
        <div className="grid grid-cols-2 gap-4">
          {sorted.map((a, i) => (
            <AgentCard key={a.id} agent={a} allAgents={agents} rank={i + 1}
              isWatched={watchlist.has(a.id)}
              isCompared={compareList.includes(a.id)}
              onWatch={() => setWatchlist(prev => { const s = new Set(prev); s.has(a.id) ? s.delete(a.id) : s.add(a.id); return s })}
              onCompare={() => setCompareList(prev => prev.includes(a.id) ? prev.filter(x => x !== a.id) : prev.length < 3 ? [...prev, a.id] : prev)}
              onSelect={() => setSelectedAgent(a)}
              onDelegate={() => setDelegateAgent({ id: a.id, name: a.name, risk: a.risk, score: a.score, riskPool: RISK_POOL[a.risk] ?? 1 })}
              portfolio={portfolios[a.id]}
              isTrading={portfolios[a.id]?.trading_active ?? false}
              isLoading={tradingLoading[a.id] ?? false}
              onStartTrading={() => handleStartTrading(a.id)}
              onStopTrading={() => handleStopTrading(a.id)}
              delegatedEth={delegations[a.id]?.ethAmount}
            />
          ))}
        </div>
      )}

      {}
      {viewMode === 'leaderboard' && (
        <div className="card">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border text-slate-500">
                <th className="text-left pb-2 font-medium w-8">#</th>
                <th className="text-left pb-2 font-medium">Agent</th>
                <th className="text-left pb-2 font-medium">Risk</th>
                <th className="text-right pb-2 font-medium">Score</th>
                <th className="text-right pb-2 font-medium">Sharpe</th>
                <th className="text-right pb-2 font-medium">PnL</th>
                <th className="text-right pb-2 font-medium">DD</th>
                <th className="text-right pb-2 font-medium">Alloc</th>
                <th className="text-right pb-2 font-medium">Stake</th>
                <th className="text-right pb-2 font-medium">Status</th>
                <th className="pb-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {sorted.map((a, i) => {
                const color = RISK_COLORS[a.risk] ?? '#64748b'
                const isTrading = portfolios[a.id]?.trading_active ?? false
                return (
                  <tr key={a.id} className="hover:bg-white/2 transition-colors cursor-pointer" onClick={() => setSelectedAgent(a)}>
                    <td className="py-3">
                      <span className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold ${i < 3 ? 'text-black' : 'text-slate-500'}`}
                        style={i < 3 ? { background: color } : {}}>
                        {i + 1}
                      </span>
                    </td>
                    <td className="py-3">
                      <div className="flex items-center gap-2">
                        {watchlist.has(a.id) && <Star size={10} className="text-yellow-400" fill="currentColor" />}
                        <span className="font-semibold" style={{ color }}>{a.name}</span>
                        {isTrading && <span className="w-1.5 h-1.5 rounded-full bg-green animate-pulse" />}
                      </div>
                      <p className="text-slate-600 text-xs">{a.strategy}</p>
                    </td>
                    <td className="py-3"><span className="text-xs px-1.5 py-0.5 rounded-full" style={{ color, background: `${color}15` }}>{a.risk}</span></td>
                    <td className="py-3 text-right font-mono text-cyan">{a.score}</td>
                    <td className="py-3 text-right font-mono text-green">{a.sharpe}</td>
                    <td className="py-3 text-right font-mono text-green">+{a.pnl}%</td>
                    <td className="py-3 text-right font-mono text-red-400">{a.drawdown}%</td>
                    <td className="py-3 text-right font-mono text-purple">{a.allocation}%</td>
                    <td className="py-3 text-right font-mono text-slate-300">${(a.stake / 1000).toFixed(0)}K</td>
                    <td className="py-3 text-right">
                      <span className={`text-xs px-1.5 py-0.5 rounded-full ${a.status === 'active' ? 'bg-green/10 text-green' : 'bg-yellow-400/10 text-yellow-400'}`}>
                        {a.status}
                      </span>
                    </td>
                    <td className="py-3 text-right" onClick={e => e.stopPropagation()}>
                      <button onClick={() => setDelegateAgent({ id: a.id, name: a.name, risk: a.risk, score: a.score, riskPool: RISK_POOL[a.risk] ?? 1 })}
                        className="text-xs px-2 py-1 rounded-lg bg-cyan/10 text-cyan border border-cyan/20 hover:bg-cyan/20 transition-all">
                        Delegate
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      <DelegationModal isOpen={!!delegateAgent} onClose={() => setDelegateAgent(null)} agent={delegateAgent} />
    </div>
  )
}
