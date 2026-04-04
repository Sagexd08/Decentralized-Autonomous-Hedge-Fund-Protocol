import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { AreaChart, Area, LineChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid } from 'recharts'
import { agents, generateTimeSeries } from '../utils/mockData'

export default function AgentDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const agent = agents.find(a => a.id === id) || agents[0]
  const pnlData = generateTimeSeries(60, 0, 1500)
  const allocData = generateTimeSeries(30, agent.allocation, 3)

  return (
    <div className="space-y-5">
      <button onClick={() => navigate('/agents')} className="flex items-center gap-2 text-slate-400 hover:text-white text-sm transition-colors">
        <ArrowLeft size={14} /> Back to Agents
      </button>

      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">{agent.name}</h1>
          <p className="text-slate-500 text-sm">{agent.strategy} · {agent.id}</p>
        </div>
        <span className={`px-3 py-1 rounded-full text-sm font-medium ${agent.status === 'active' ? 'bg-green/10 text-green border border-green/20' : 'bg-gold/10 text-gold border border-gold/20'}`}>
          {agent.status}
        </span>
      </div>

      {/* Key metrics */}
      <div className="grid grid-cols-5 gap-3">
        {[
          { label: 'Sharpe Ratio', value: agent.sharpe, color: 'text-green' },
          { label: 'Max Drawdown', value: `${agent.drawdown}%`, color: 'text-red-400' },
          { label: 'Allocation', value: `${agent.allocation}%`, color: 'text-cyan' },
          { label: 'Total PnL', value: `+${agent.pnl}%`, color: 'text-green' },
          { label: 'Volatility', value: `${agent.volatility}%`, color: 'text-purple' },
        ].map(m => (
          <div key={m.label} className="card text-center">
            <div className={`text-xl font-bold font-mono ${m.color}`}>{m.value}</div>
            <div className="text-xs text-slate-500 mt-1">{m.label}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-4">
        {/* PnL curve */}
        <div className="card">
          <h3 className="text-sm font-semibold text-white mb-4">Cumulative PnL</h3>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={pnlData}>
              <defs>
                <linearGradient id="pnlGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="time" hide />
              <YAxis hide />
              <Tooltip contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 8, fontSize: 11 }} />
              <Area type="monotone" dataKey="value" stroke="#10b981" strokeWidth={2} fill="url(#pnlGrad)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Allocation over time */}
        <div className="card">
          <h3 className="text-sm font-semibold text-white mb-4">Allocation Weight Over Time</h3>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={allocData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="time" hide />
              <YAxis hide />
              <Tooltip contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 8, fontSize: 11 }} />
              <Line type="monotone" dataKey="value" stroke="#a855f7" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Staking info */}
      <div className="card">
        <h3 className="text-sm font-semibold text-white mb-4">Staking & Risk Profile</h3>
        <div className="grid grid-cols-3 gap-4 text-sm">
          <div>
            <p className="text-slate-500 text-xs mb-1">Staked Collateral</p>
            <p className="font-mono text-white">${agent.stake.toLocaleString()}</p>
          </div>
          <div>
            <p className="text-slate-500 text-xs mb-1">Risk Class</p>
            <p className="font-mono text-purple">{agent.risk}</p>
          </div>
          <div>
            <p className="text-slate-500 text-xs mb-1">Protocol Score</p>
            <div className="flex items-center gap-2">
              <div className="flex-1 h-2 bg-border rounded-full overflow-hidden">
                <div className="h-full rounded-full" style={{ width: `${agent.score}%`, background: 'linear-gradient(90deg,#00f5ff,#a855f7)' }} />
              </div>
              <span className="font-mono text-cyan text-xs">{agent.score}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
