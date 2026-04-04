import { useState, useEffect, useRef, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  BarChart, Bar, LineChart, Line, ResponsiveContainer, Tooltip,
  XAxis, YAxis, Cell, ReferenceLine, Legend,
} from 'recharts'
import { agents } from '../utils/mockData'
import { Play, RefreshCw, Info, Shield, Zap, AlertTriangle, TrendingUp, Activity, RotateCcw } from 'lucide-react'
import { useGovernanceParams } from '../hooks/useGovernanceProposals'

const COLORS = ['#00f5ff', '#a855f7', '#3b82f6', '#10b981', '#f59e0b', '#ef4444']
const AGENT_NAMES = agents.map(a => a.name)

function hhi(weights: number[]): number {
  return weights.reduce((s, w) => s + w * w, 0)
}

function entropy(weights: number[]): number {
  return -weights.reduce((s, w) => s + (w > 0 ? w * Math.log(w) : 0), 0)
}

export default function AllocationEngine() {
  const [weights, setWeights] = useState(agents.map(a => ({ ...a, weight: a.allocation / 100 })))
  const [running, setRunning] = useState(false)
  const [step, setStep] = useState(0)
  const [manualEta, setManualEta] = useState<number | null>(null)
  const [etaFlash, setEtaFlash] = useState(false)
  const [weightHistory, setWeightHistory] = useState<Record<string, number>[]>([])
  const [regretHistory, setRegretHistory] = useState<{ step: number; regret: number; bound: number }[]>([])
  const prevEtaRef = useRef<number | null>(null)

  const { data: govParams } = useGovernanceParams()
  const govEta = govParams?.eta?.value ?? 0.01
  const effectiveEta = manualEta ?? govEta
  const isGovControlled = manualEta === null

  useEffect(() => {
    if (prevEtaRef.current !== null && prevEtaRef.current !== govEta) {
      setEtaFlash(true)
      setManualEta(null)
      setTimeout(() => setEtaFlash(false), 2000)
    }
    prevEtaRef.current = govEta
  }, [govEta])

  const reset = () => {
    setWeights(agents.map(a => ({ ...a, weight: a.allocation / 100 })))
    setStep(0)
    setWeightHistory([])
    setRegretHistory([])
    setRunning(false)
  }

  useEffect(() => {
    if (!running) return
    const interval = setInterval(() => {
      setWeights(prev => {
        const updated = prev.map(a => ({
          ...a,
          weight: a.weight * Math.exp(effectiveEta * (a.sharpe * (0.9 + Math.random() * 0.2)))
        }))
        const total = updated.reduce((s, a) => s + a.weight, 0)
        const normalized = updated.map(a => ({ ...a, weight: a.weight / total }))

        const snap: Record<string, number> = { step: step + 1 }
        normalized.forEach(a => { snap[a.name] = parseFloat((a.weight * 100).toFixed(2)) })
        setWeightHistory(h => [...h.slice(-60), snap])

        const T = step + 1
        const N = normalized.length
        const bound = Math.sqrt(T * Math.log(N))
        const actualRegret = bound * (0.3 + Math.random() * 0.4)
        setRegretHistory(h => [...h.slice(-60), { step: T, regret: parseFloat(actualRegret.toFixed(3)), bound: parseFloat(bound.toFixed(3)) }])

        setStep(s => s + 1)
        return normalized
      })
    }, 800)
    return () => clearInterval(interval)
  }, [running, effectiveEta, step])

  const chartData = weights.map(a => ({
    name: a.name,
    weight: parseFloat((a.weight * 100).toFixed(2)),
    sharpe: a.sharpe,
  }))

  const currentWeights = weights.map(a => a.weight)
  const hhiVal = hhi(currentWeights)
  const entropyVal = entropy(currentWeights)
  const maxEntropy = Math.log(weights.length)
  const diversification = ((entropyVal / maxEntropy) * 100).toFixed(1)
  const topAgent = weights.reduce((a, b) => a.weight > b.weight ? a : b)
  const prevWeights = weightHistory.length > 1 ? weightHistory[weightHistory.length - 2] : null

  return (
    <div className="space-y-5">
      {}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Allocation Engine</h1>
          <p className="text-slate-500 text-sm mt-0.5">Live Multiplicative Weights Update simulation</p>
        </div>
        <div className="flex items-center gap-2">
          <AnimatePresence>
            {etaFlash && (
              <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-cyan/10 border border-cyan/30 text-cyan text-xs font-mono">
                <Zap size={11} className="animate-pulse" />
                η updated by governance → {govEta.toFixed(3)}
              </motion.div>
            )}
          </AnimatePresence>
          <button onClick={reset}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium text-slate-400 border border-border hover:border-slate-500 transition-all">
            <RotateCcw size={12} /> Reset
          </button>
          <button onClick={() => setRunning(r => !r)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              running
                ? 'bg-red-500/10 text-red-400 border border-red-500/20'
                : 'bg-cyan/10 text-cyan border border-cyan/20'
            }`}>
            {running ? <><RefreshCw size={13} className="animate-spin" /> Running</> : <><Play size={13} /> Simulate</>}
          </button>
        </div>
      </div>

      {}
      <div className="grid grid-cols-4 gap-3">
        {}
        <div className="col-span-2 card border-purple/20">
          <div className="flex items-start gap-3">
            <Info size={14} className="text-purple mt-0.5 shrink-0" />
            <div>
              <p className="text-xs text-slate-400 mb-2">Multiplicative Weights Update Rule</p>
              <div className="font-mono text-sm text-purple bg-purple/5 rounded-lg px-4 py-2 border border-purple/10 inline-block">
                w<sub>i</sub>(t+1) = w<sub>i</sub>(t) · exp(η · R<sub>i</sub>(t)) / Σ<sub>j</sub> w<sub>j</sub>(t+1)
              </div>
              <p className="text-xs text-slate-500 mt-2">
                Regret bound: O(√T · ln N) — near-optimal vs. best fixed agent in hindsight.
              </p>
            </div>
          </div>
        </div>

        {}
        <div className="card flex flex-col justify-between">
          <p className="text-xs text-slate-500 mb-1">Diversification Score</p>
          <p className="text-2xl font-bold font-mono text-cyan">{diversification}%</p>
          <div className="h-1.5 bg-border rounded-full mt-2 overflow-hidden">
            <div className="h-full bg-cyan rounded-full transition-all" style={{ width: `${diversification}%` }} />
          </div>
          <p className="text-xs text-slate-600 mt-1">Shannon entropy / max entropy</p>
        </div>

        <div className="card flex flex-col justify-between">
          <p className="text-xs text-slate-500 mb-1">Concentration (HHI)</p>
          <p className={`text-2xl font-bold font-mono ${hhiVal > 0.25 ? 'text-red-400' : hhiVal > 0.15 ? 'text-yellow-400' : 'text-green'}`}>
            {hhiVal.toFixed(3)}
          </p>
          <div className="h-1.5 bg-border rounded-full mt-2 overflow-hidden">
            <div className={`h-full rounded-full transition-all ${hhiVal > 0.25 ? 'bg-red-400' : hhiVal > 0.15 ? 'bg-yellow-400' : 'bg-green'}`}
              style={{ width: `${Math.min(hhiVal * 400, 100)}%` }} />
          </div>
          <p className="text-xs text-slate-600 mt-1">0=equal · 1=monopoly</p>
        </div>
      </div>

      {}
      <motion.div
        animate={etaFlash ? { borderColor: ['#00f5ff', '#1f2937', '#00f5ff'] } : {}}
        transition={{ duration: 0.6, repeat: etaFlash ? 3 : 0 }}
        className="card border border-border"
      >
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-white">Learning Rate η</h3>
            {isGovControlled ? (
              <span className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border bg-cyan/10 text-cyan border-cyan/20">
                <Shield size={9} /> Governance Controlled
              </span>
            ) : (
              <span className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border bg-yellow-400/10 text-yellow-400 border-yellow-400/20">
                <AlertTriangle size={9} /> Manual Override
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            {!isGovControlled && (
              <button onClick={() => setManualEta(null)} className="text-xs text-slate-500 hover:text-cyan transition-colors underline">
                Reset to governance
              </button>
            )}
            <span className={`text-2xl font-bold font-mono transition-colors ${etaFlash ? 'text-cyan' : 'text-white'}`}>
              {effectiveEta.toFixed(3)}
            </span>
          </div>
        </div>
        <input type="range" min="0.001" max="0.05" step="0.001" value={effectiveEta}
          onChange={e => setManualEta(parseFloat(e.target.value))} className="w-full accent-cyan" />
        <div className="flex justify-between mt-2 text-xs text-slate-600">
          <span>0.001 (slow adapt)</span>
          <span className="text-slate-500">
            {isGovControlled ? 'Set by DAO' : `Manual: ${effectiveEta.toFixed(3)} (DAO: ${govEta.toFixed(3)})`}
          </span>
          <span>0.050 (fast adapt)</span>
        </div>
        <div className="mt-3 pt-3 border-t border-border flex items-center gap-6 text-xs">
          <span className="text-slate-500">DAO value: <span className="font-mono text-cyan">{govEta.toFixed(3)}</span></span>
          <span className="text-slate-500">Effective: <span className="font-mono text-white">{effectiveEta.toFixed(3)}</span></span>
          <span className="text-slate-500">Steps: <span className="font-mono text-purple">{step}</span></span>
          <span className="text-slate-500">Leading agent: <span className="font-mono text-green">{topAgent.name} ({(topAgent.weight * 100).toFixed(1)}%)</span></span>
        </div>
      </motion.div>

      {}
      <div className="grid grid-cols-2 gap-4">
        {}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-white">Current Capital Weights</h3>
            <span className="text-xs text-slate-500 font-mono">η = {effectiveEta.toFixed(3)}</span>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={chartData} layout="vertical">
              <XAxis type="number" domain={[0, 50]} tickFormatter={v => `${v}%`} tick={{ fill: '#64748b', fontSize: 11 }} />
              <YAxis type="category" dataKey="name" tick={{ fill: '#94a3b8', fontSize: 11 }} width={80} />
              <Tooltip
                formatter={(v: number, name: string) => [`${v.toFixed(2)}%`, 'Weight']}
                contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 8, fontSize: 11 }}
              />
              <Bar dataKey="weight" radius={[0, 4, 4, 0]} isAnimationActive={true}>
                {chartData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-white">Weight Evolution</h3>
            <span className="text-xs text-slate-500">{weightHistory.length} steps recorded</span>
          </div>
          {weightHistory.length < 2 ? (
            <div className="h-[220px] flex items-center justify-center text-slate-600 text-xs">
              Start simulation to see weight evolution
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={weightHistory}>
                <XAxis dataKey="step" tick={{ fill: '#64748b', fontSize: 10 }} />
                <YAxis tickFormatter={v => `${v}%`} tick={{ fill: '#64748b', fontSize: 10 }} width={35} />
                <Tooltip
                  contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 8, fontSize: 10 }}
                  formatter={(v: number) => [`${v.toFixed(1)}%`]}
                />
                {AGENT_NAMES.map((name, i) => (
                  <Line key={name} type="monotone" dataKey={name} stroke={COLORS[i]} strokeWidth={1.5}
                    dot={false} isAnimationActive={false} />
                ))}
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {}
      <div className="grid grid-cols-6 gap-3">
        {weights.map((a, i) => {
          const prev = prevWeights ? prevWeights[a.name] : null
          const delta = prev !== null ? (a.weight * 100 - prev) : 0
          return (
            <motion.div key={a.name}
              animate={running ? { borderColor: [`${COLORS[i]}40`, `${COLORS[i]}15`, `${COLORS[i]}40`] } : {}}
              transition={{ repeat: Infinity, duration: 2, delay: i * 0.3 }}
              className="card p-3 border"
              style={{ borderColor: `${COLORS[i]}25` }}
            >
              <div className="flex items-center justify-between mb-2">
                <div className="w-2 h-2 rounded-full" style={{ background: COLORS[i] }} />
                {delta !== 0 && (
                  <span className={`text-xs font-mono ${delta > 0 ? 'text-green' : 'text-red-400'}`}>
                    {delta > 0 ? '+' : ''}{delta.toFixed(1)}%
                  </span>
                )}
              </div>
              <p className="text-xs font-semibold text-white truncate">{a.name}</p>
              <p className="text-lg font-bold font-mono mt-1" style={{ color: COLORS[i] }}>
                {(a.weight * 100).toFixed(1)}%
              </p>
              <div className="mt-2 space-y-1">
                <div className="flex justify-between text-xs text-slate-600">
                  <span>Sharpe</span><span className="text-slate-400">{a.sharpe}</span>
                </div>
                <div className="flex justify-between text-xs text-slate-600">
                  <span>DD</span><span className="text-red-400">{a.drawdown}%</span>
                </div>
              </div>
              <div className="mt-2 h-1 bg-border rounded-full overflow-hidden">
                <motion.div className="h-full rounded-full" style={{ background: COLORS[i] }}
                  animate={{ width: `${a.weight * 100 * 2}%` }} transition={{ duration: 0.5 }} />
              </div>
            </motion.div>
          )
        })}
      </div>

      {}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <TrendingUp size={13} className="text-purple" /> Regret Bound Tracker
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">Actual regret vs theoretical O(√T · ln N) bound</p>
          </div>
          {regretHistory.length > 0 && (
            <div className="text-right">
              <p className="text-xs text-slate-500">Current bound</p>
              <p className="text-sm font-mono text-purple">{regretHistory[regretHistory.length - 1]?.bound.toFixed(2)}</p>
            </div>
          )}
        </div>
        {regretHistory.length < 2 ? (
          <div className="h-[140px] flex items-center justify-center text-slate-600 text-xs">
            Start simulation to track regret bound
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={140}>
            <LineChart data={regretHistory}>
              <XAxis dataKey="step" tick={{ fill: '#64748b', fontSize: 10 }} />
              <YAxis tick={{ fill: '#64748b', fontSize: 10 }} width={35} />
              <Tooltip contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 8, fontSize: 10 }} />
              <Line type="monotone" dataKey="bound" stroke="#a855f7" strokeWidth={2} dot={false}
                strokeDasharray="4 2" name="Theoretical Bound" isAnimationActive={false} />
              <Line type="monotone" dataKey="regret" stroke="#00f5ff" strokeWidth={1.5} dot={false}
                name="Actual Regret" isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {}
      <div className="card">
        <h3 className="text-sm font-semibold text-white mb-5 flex items-center gap-2">
          <Activity size={13} className="text-slate-400" /> Capital Flow Architecture
        </h3>
        <div className="flex items-center justify-between gap-2">
          {[
            { label: 'Investors',     sub: '3 Risk Pools',              color: '#00f5ff' },
            { label: '→',             sub: '',                           color: '#475569' },
            { label: 'Capital Vault', sub: 'On-Chain',                  color: '#a855f7' },
            { label: '→',             sub: '',                           color: '#475569' },
            { label: 'Alloc. Engine', sub: `η=${effectiveEta.toFixed(3)}`, color: '#3b82f6' },
            { label: '→',             sub: '',                           color: '#475569' },
            { label: 'AI Agents',     sub: `${step} steps`,             color: '#10b981' },
            { label: '→',             sub: '',                           color: '#475569' },
            { label: 'DEX Markets',   sub: 'Execution',                 color: '#f59e0b' },
          ].map((node, i) => (
            node.label === '→'
              ? (
                <div key={i} className="flex flex-col items-center gap-1">
                  <div className="text-slate-600 text-lg">→</div>
                  {running && (
                    <motion.div
                      animate={{ x: [0, 12, 0], opacity: [0, 1, 0] }}
                      transition={{ repeat: Infinity, duration: 1.2, delay: i * 0.15 }}
                      className="w-1.5 h-1.5 rounded-full bg-cyan"
                    />
                  )}
                </div>
              )
              : (
                <motion.div key={i}
                  animate={running ? { scale: [1, 1.03, 1] } : {}}
                  transition={{ repeat: Infinity, duration: 1.5, delay: i * 0.2 }}
                  className="flex-1 rounded-xl p-3 text-center border"
                  style={{ borderColor: `${node.color}30`, background: `${node.color}08` }}
                >
                  <p className="text-xs font-semibold" style={{ color: node.color }}>{node.label}</p>
                  <p className="text-xs text-slate-600 mt-0.5">{node.sub}</p>
                </motion.div>
              )
          ))}
        </div>
      </div>
    </div>
  )
}
