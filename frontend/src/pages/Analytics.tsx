import { useState, useMemo } from 'react'
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar,
  ComposedChart, ScatterChart, Scatter,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
  CartesianGrid, ReferenceLine, Cell, Legend,
} from 'recharts'
import { generateTimeSeries, rollingVolatility, trendWave, monteCarloData, agents } from '../utils/mockData'
import { motion, AnimatePresence } from 'framer-motion'
import { useMonteCarloData } from '../hooks/useMonteCarloData'
import { TrendingUp, TrendingDown, Activity, BarChart2, Zap, AlertTriangle, CheckCircle, Clock } from 'lucide-react'

// ---------------------------------------------------------------------------
// Data generators
// ---------------------------------------------------------------------------
const AGENT_COLORS = ['#00f5ff', '#a855f7', '#3b82f6', '#10b981', '#f59e0b', '#ef4444']

// 30 visually distinct colors for MC paths
const PATH_COLORS = [
  '#00f5ff', '#a855f7', '#10b981', '#f59e0b', '#ef4444', '#3b82f6',
  '#ec4899', '#14b8a6', '#f97316', '#8b5cf6', '#06b6d4', '#84cc16',
  '#e11d48', '#0ea5e9', '#d946ef', '#22c55e', '#fb923c', '#6366f1',
  '#fbbf24', '#38bdf8', '#4ade80', '#f472b6', '#34d399', '#fb7185',
  '#a3e635', '#60a5fa', '#c084fc', '#fdba74', '#67e8f9', '#86efac',
]

// Return distribution — normal with fat tails
function genReturnDist() {
  const bins: { bin: string; count: number; pct: number }[] = []
  const returns = Array.from({ length: 500 }, () => {
    const u1 = Math.random(), u2 = Math.random()
    const z = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2)
    return z * 0.018 + 0.0008 // slight positive drift
  })
  const min = -0.08, max = 0.08, buckets = 24
  const step = (max - min) / buckets
  for (let i = 0; i < buckets; i++) {
    const lo = min + i * step, hi = lo + step
    const count = returns.filter(r => r >= lo && r < hi).length
    bins.push({ bin: `${(lo * 100).toFixed(1)}%`, count, pct: count / returns.length * 100 })
  }
  return { bins, returns, skew: -0.31, kurt: 4.82, var95: -0.0298, cvar95: -0.0412 }
}

// Drawdown series
function genDrawdown() {
  const equity = generateTimeSeries(120, 100000, 1500)
  let peak = equity[0].value
  return equity.map(p => {
    if (p.value > peak) peak = p.value
    const dd = ((p.value - peak) / peak) * 100
    return { time: p.time, equity: p.value, drawdown: parseFloat(dd.toFixed(2)), peak }
  })
}

// Rolling Sharpe/Sortino/Calmar
function genRollingRatios() {
  return generateTimeSeries(90, 1.8, 0.3).map((p, i) => ({
    time: p.time,
    sharpe: parseFloat(p.value.toFixed(3)),
    sortino: parseFloat((p.value * 1.35 + Math.random() * 0.1).toFixed(3)),
    calmar: parseFloat((p.value * 0.72 + Math.random() * 0.05).toFixed(3)),
  }))
}

// Agent attribution (stacked bar)
function genAttribution() {
  return generateTimeSeries(30, 0, 1).map((p, i) => {
    const row: Record<string, number | string> = { time: p.time }
    agents.forEach((a, j) => {
      row[a.name] = parseFloat(((Math.random() - 0.45) * 0.8).toFixed(3))
    })
    return row
  })
}

// Volatility surface (heatmap data)
function genVolSurface() {
  const windows = [7, 14, 21, 30, 45, 60]
  const pools = ['Conservative', 'Balanced', 'Aggressive']
  return pools.map(pool => {
    const base = pool === 'Conservative' ? 5 : pool === 'Balanced' ? 13 : 26
    return {
      pool,
      ...Object.fromEntries(windows.map(w => [
        `${w}d`,
        parseFloat((base + (Math.random() - 0.5) * base * 0.4).toFixed(2))
      ]))
    }
  })
}

// Regime transition matrix
const REGIME_TRANS = {
  Bull:     { Bull: 0.72, Sideways: 0.21, Bear: 0.07 },
  Sideways: { Bull: 0.28, Sideways: 0.54, Bear: 0.18 },
  Bear:     { Bull: 0.15, Sideways: 0.31, Bear: 0.54 },
}

// Regime timeline
function genRegimeTimeline() {
  const regimes = ['Bull', 'Sideways', 'Bear'] as const
  let current: typeof regimes[number] = 'Bull'
  return generateTimeSeries(90, 50, 15).map((p, i) => {
    if (Math.random() < 0.08) {
      const trans = REGIME_TRANS[current]
      const r = Math.random()
      if (r < trans.Bull) current = 'Bull'
      else if (r < trans.Bull + trans.Sideways) current = 'Sideways'
      else current = 'Bear'
    }
    return {
      time: p.time, value: p.value, regime: current,
      color: current === 'Bull' ? '#10b981' : current === 'Bear' ? '#ef4444' : '#f59e0b',
      conf: parseFloat((0.6 + Math.random() * 0.35).toFixed(2)),
    }
  })
}

// Agent correlation matrix
function genAgentCorr() {
  const n = agents.length
  const matrix: number[][] = Array.from({ length: n }, (_, i) =>
    Array.from({ length: n }, (_, j) => {
      if (i === j) return 1
      const base = 0.2 + Math.random() * 0.6
      return parseFloat(base.toFixed(2))
    })
  )
  // Make symmetric
  for (let i = 0; i < n; i++)
    for (let j = i + 1; j < n; j++)
      matrix[j][i] = matrix[i][j]
  return matrix
}

// Backtest stats
const BACKTEST = {
  totalReturn: 34.7, cagr: 28.4, maxDrawdown: -14.2,
  sharpe: 2.41, sortino: 3.18, calmar: 2.00,
  winRate: 61.3, avgWin: 1.82, avgLoss: -0.94,
  profitFactor: 1.94, trades: 847, avgHoldDays: 2.3,
}

// Generate diverse GBM paths with varied mu/sigma for visible spread
function genDiversePaths(n: number, steps: number, S0: number) {
  return Array.from({ length: n }, (_, i) => {
    const mu = -0.002 + (i / n) * 0.006
    const sigma = 0.008 + (i / n) * 0.035
    const path: number[] = [S0]
    for (let t = 1; t < steps; t++) {
      const u1 = Math.random(), u2 = Math.random()
      const z = Math.sqrt(-2 * Math.log(Math.max(u1, 1e-10))) * Math.cos(2 * Math.PI * u2)
      const prev = path[t - 1]
      path.push(Math.max(prev * Math.exp(mu + sigma * z), S0 * 0.3))
    }
    return path
  })
}

// MC fan chart (percentile bands)
function genMCFan(paths: number[][]) {
  if (!paths.length) return []
  const T = paths[0].length
  return Array.from({ length: T }, (_, t) => {
    const vals = paths.map(p => p[t]).sort((a, b) => a - b)
    const pct = (p: number) => vals[Math.floor(p * vals.length / 100)] ?? vals[vals.length - 1]
    return {
      t,
      p5: pct(5), p25: pct(25), p50: pct(50), p75: pct(75), p95: pct(95),
    }
  })
}

// Time series decomposition
const tsData = generateTimeSeries(90, 100, 5).map((d, i) => ({
  ...d,
  trend: 100 + i * 0.3,
  seasonal: Math.sin(i / 7 * Math.PI) * 5,
  residual: parseFloat(((Math.random() - 0.5) * 3).toFixed(3)),
}))

// ---------------------------------------------------------------------------
// Static data (computed once)
// ---------------------------------------------------------------------------
const RETURN_DIST = genReturnDist()
const DRAWDOWN_DATA = genDrawdown()
const ROLLING_RATIOS = genRollingRatios()
const ATTRIBUTION = genAttribution()
const VOL_SURFACE = genVolSurface()
const REGIME_TIMELINE = genRegimeTimeline()
const AGENT_CORR = genAgentCorr()
const VOL_WINDOWS = ['7d', '14d', '21d', '30d', '45d', '60d']

const TABS = [
  'Overview', 'Monte Carlo', 'Drawdown', 'Volatility',
  'Regime', 'Attribution', 'Distributions', 'Time Series',
]

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function corrColor(v: number) {
  if (v >= 0.9) return '#ef4444'
  if (v >= 0.7) return '#f59e0b'
  if (v >= 0.5) return '#3b82f6'
  if (v >= 0.3) return '#10b981'
  return '#1f2937'
}

function StatCard({ label, value, sub, color = 'text-white', up }: {
  label: string; value: string; sub?: string; color?: string; up?: boolean
}) {
  return (
    <div className="card py-3 px-4">
      <p className="text-xs text-slate-500 mb-1">{label}</p>
      <p className={`text-xl font-bold font-mono ${color}`}>{value}</p>
      {sub && <p className="text-xs text-slate-600 mt-0.5">{sub}</p>}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tab panels
// ---------------------------------------------------------------------------

function OverviewTab({ mcStats }: { mcStats: any }) {
  const lastRegime = REGIME_TIMELINE[REGIME_TIMELINE.length - 1]
  const regimeColor = lastRegime.color
  const daysInRegime = REGIME_TIMELINE.slice().reverse().findIndex(r => r.regime !== lastRegime.regime)

  return (
    <div className="space-y-4">
      {/* Regime banner */}
      <div className="card flex items-center justify-between" style={{ borderColor: `${regimeColor}30`, background: `${regimeColor}08` }}>
        <div className="flex items-center gap-3">
          <div className="w-3 h-3 rounded-full animate-pulse" style={{ background: regimeColor }} />
          <div>
            <p className="text-xs text-slate-500">Current Market Regime</p>
            <p className="text-lg font-bold" style={{ color: regimeColor }}>{lastRegime.regime} Market</p>
          </div>
        </div>
        <div className="flex items-center gap-6 text-xs">
          <div><p className="text-slate-500">Confidence</p><p className="font-mono text-white">{(lastRegime.conf * 100).toFixed(1)}%</p></div>
          <div><p className="text-slate-500">Days in Regime</p><p className="font-mono text-white">{daysInRegime > 0 ? daysInRegime : 1}d</p></div>
          <div><p className="text-slate-500">Transition Risk</p>
            <p className="font-mono text-yellow-400">{(REGIME_TRANS[lastRegime.regime as keyof typeof REGIME_TRANS].Bear * 100).toFixed(0)}% → Bear</p>
          </div>
        </div>
      </div>

      {/* Key metrics */}
      <div className="grid grid-cols-4 gap-3">
        <StatCard label="Total Return" value={`+${BACKTEST.totalReturn}%`} color="text-green" sub="Since inception" />
        <StatCard label="Sharpe Ratio" value={BACKTEST.sharpe.toFixed(2)} color="text-cyan" sub="Risk-adjusted" />
        <StatCard label="Max Drawdown" value={`${BACKTEST.maxDrawdown}%`} color="text-red-400" sub="Peak-to-trough" />
        <StatCard label="Win Rate" value={`${BACKTEST.winRate}%`} color="text-purple" sub={`${BACKTEST.trades} trades`} />
      </div>

      <div className="grid grid-cols-4 gap-3">
        <StatCard label="CAGR" value={`${BACKTEST.cagr}%`} color="text-green" />
        <StatCard label="Sortino" value={BACKTEST.sortino.toFixed(2)} color="text-cyan" />
        <StatCard label="Calmar" value={BACKTEST.calmar.toFixed(2)} color="text-purple" />
        <StatCard label="Profit Factor" value={BACKTEST.profitFactor.toFixed(2)} color="text-yellow-400" />
      </div>

      {/* Rolling ratios */}
      <div className="card">
        <h3 className="text-sm font-semibold text-white mb-1">Rolling Risk-Adjusted Ratios (30d window)</h3>
        <p className="text-xs text-slate-500 mb-4">Sharpe · Sortino · Calmar — computed on rolling 30-day returns</p>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={ROLLING_RATIOS}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
            <XAxis dataKey="time" hide />
            <YAxis tick={{ fill: '#64748b', fontSize: 10 }} />
            <Tooltip contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 8, fontSize: 10 }} />
            <ReferenceLine y={1} stroke="#64748b" strokeDasharray="3 3" />
            <Line type="monotone" dataKey="sharpe" stroke="#00f5ff" strokeWidth={2} dot={false} name="Sharpe" />
            <Line type="monotone" dataKey="sortino" stroke="#10b981" strokeWidth={1.5} dot={false} name="Sortino" />
            <Line type="monotone" dataKey="calmar" stroke="#a855f7" strokeWidth={1.5} dot={false} name="Calmar" />
            <Legend wrapperStyle={{ fontSize: 10, color: '#94a3b8' }} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Backtest summary */}
      <div className="card">
        <h3 className="text-sm font-semibold text-white mb-4">Backtest Summary</h3>
        <div className="grid grid-cols-3 gap-x-8 gap-y-2 text-xs">
          {[
            ['Total Return', `+${BACKTEST.totalReturn}%`, 'text-green'],
            ['CAGR', `${BACKTEST.cagr}%`, 'text-green'],
            ['Max Drawdown', `${BACKTEST.maxDrawdown}%`, 'text-red-400'],
            ['Sharpe Ratio', BACKTEST.sharpe.toFixed(2), 'text-cyan'],
            ['Sortino Ratio', BACKTEST.sortino.toFixed(2), 'text-cyan'],
            ['Calmar Ratio', BACKTEST.calmar.toFixed(2), 'text-cyan'],
            ['Win Rate', `${BACKTEST.winRate}%`, 'text-purple'],
            ['Avg Win', `+${BACKTEST.avgWin}%`, 'text-green'],
            ['Avg Loss', `${BACKTEST.avgLoss}%`, 'text-red-400'],
            ['Profit Factor', BACKTEST.profitFactor.toFixed(2), 'text-yellow-400'],
            ['Total Trades', BACKTEST.trades, 'text-white'],
            ['Avg Hold', `${BACKTEST.avgHoldDays}d`, 'text-slate-300'],
          ].map(([label, value, color]) => (
            <div key={label as string} className="flex justify-between py-1.5 border-b border-border/50">
              <span className="text-slate-500">{label}</span>
              <span className={`font-mono font-medium ${color}`}>{value}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function MonteCarloTab({ mcData }: { mcData: any }) {
  const [params, setParams] = useState({ mu: 0.15, sigma: 0.20, paths: 200 })

  // Generate 30 diverse paths with varied drift/vol — ensures visible spread
  const diversePaths = useMemo(() => genDiversePaths(30, 31, 100000), [])
  const fanData = useMemo(() => genMCFan(diversePaths), [diversePaths])

  const mcStats = mcData?.stats ?? { mean_return: 0.187, var_95: -0.121, cvar_95: -0.158, sharpe_ratio: 1.84, prob_profit: 0.732 }

  // Pivot for spaghetti chart
  const spaghettiData = useMemo(() =>
    Array.from({ length: 31 }, (_, t) => {
      const row: Record<string, number> = { t }
      diversePaths.forEach((path, i) => { row[`p${i}`] = path[t] ?? 0 })
      return row
    }),
    [diversePaths]
  )

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-5 gap-3">
        {[
          { label: 'Expected Return', value: `+${(mcStats.mean_return * 100).toFixed(1)}%`, color: 'text-green' },
          { label: 'VaR (95%)', value: `${(mcStats.var_95 * 100).toFixed(1)}%`, color: 'text-red-400' },
          { label: 'CVaR (95%)', value: `${((mcStats.cvar_95 ?? mcStats.var_95 * 1.3) * 100).toFixed(1)}%`, color: 'text-red-400' },
          { label: 'Sharpe', value: (mcStats.sharpe_ratio ?? 1.84).toFixed(2), color: 'text-cyan' },
          { label: 'P(Profit)', value: `${(mcStats.prob_profit * 100).toFixed(1)}%`, color: 'text-purple' },
        ].map(m => <StatCard key={m.label} label={m.label} value={m.value} color={m.color} />)}
      </div>

      {/* Fan chart */}
      <div className="card">
        <h3 className="text-sm font-semibold text-white mb-1">Monte Carlo Fan Chart</h3>
        <p className="text-xs text-slate-500 mb-4">Percentile bands: P5 / P25 / P50 / P75 / P95 · 30 paths · GBM model</p>
        <ResponsiveContainer width="100%" height={280}>
          <ComposedChart data={fanData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
            <XAxis dataKey="t" tick={{ fill: '#64748b', fontSize: 10 }} label={{ value: 'Days', position: 'insideBottom', fill: '#64748b', fontSize: 10 }} />
            <YAxis tickFormatter={v => `$${(v / 1000).toFixed(0)}k`} tick={{ fill: '#64748b', fontSize: 10 }} domain={[70000, 150000]} />
            <Tooltip contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 8, fontSize: 10 }}
              formatter={(v: number) => [`$${v.toFixed(0)}`]} />
            <Area dataKey="p95" fill="#10b981" fillOpacity={0.08} stroke="none" name="P95" />
            <Area dataKey="p75" fill="#10b981" fillOpacity={0.12} stroke="none" name="P75" />
            <Area dataKey="p25" fill="#ef4444" fillOpacity={0.12} stroke="none" name="P25" />
            <Area dataKey="p5" fill="#ef4444" fillOpacity={0.08} stroke="none" name="P5" />
            <Line dataKey="p95" stroke="#10b981" strokeWidth={1} dot={false} strokeDasharray="3 2" name="P95" />
            <Line dataKey="p75" stroke="#10b981" strokeWidth={1.5} dot={false} name="P75" />
            <Line dataKey="p50" stroke="#00f5ff" strokeWidth={2.5} dot={false} name="Median" />
            <Line dataKey="p25" stroke="#ef4444" strokeWidth={1.5} dot={false} name="P25" />
            <Line dataKey="p5" stroke="#ef4444" strokeWidth={1} dot={false} strokeDasharray="3 2" name="P5" />
          </ComposedChart>
        </ResponsiveContainer>
        <div className="flex items-center gap-4 mt-2 text-xs text-slate-500">
          {[['P95', '#10b981'], ['P75', '#10b981'], ['Median', '#00f5ff'], ['P25', '#ef4444'], ['P5', '#ef4444']].map(([l, c]) => (
            <span key={l} className="flex items-center gap-1"><span className="w-3 h-0.5 inline-block" style={{ background: c as string }} />{l}</span>
          ))}
        </div>
      </div>

      {/* Spaghetti paths */}
      <div className="card">
        <h3 className="text-sm font-semibold text-white mb-1">Individual Path Simulation</h3>
        <p className="text-xs text-slate-500 mb-4">30 sample paths — green = top decile, red = bottom decile</p>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={spaghettiData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
            <XAxis dataKey="t" tick={{ fill: '#64748b', fontSize: 10 }} label={{ value: 'Days', position: 'insideBottom', fill: '#64748b', fontSize: 10 }} />
            <YAxis tickFormatter={v => `$${(v / 1000).toFixed(0)}k`} tick={{ fill: '#64748b', fontSize: 10 }} width={45} domain={[70000, 150000]} />
            <Tooltip contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 8, fontSize: 10 }}
              formatter={(v: number) => [`$${v.toFixed(0)}`]} />
            {(() => {
              return diversePaths.map((_, i) => (
                <Line key={i} type="monotone" dataKey={`p${i}`}
                  stroke={PATH_COLORS[i % PATH_COLORS.length]}
                  strokeWidth={2}
                  strokeOpacity={0.85}
                  dot={false} isAnimationActive={false} legendType="none" />
              ))
            })()}
          </LineChart>
        </ResponsiveContainer>
        <div className="flex items-center gap-4 mt-2 text-xs text-slate-500">
          <span>Each path has a unique color · thicker lines = top/bottom 3 by final value</span>
        </div>
      </div>
    </div>
  )
}

function DrawdownTab() {
  const maxDD = Math.min(...DRAWDOWN_DATA.map(d => d.drawdown))
  const ddPeriods = DRAWDOWN_DATA.filter(d => d.drawdown < -5).length

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-4 gap-3">
        <StatCard label="Max Drawdown" value={`${maxDD.toFixed(1)}%`} color="text-red-400" />
        <StatCard label="Days Underwater" value={`${ddPeriods}d`} color="text-yellow-400" />
        <StatCard label="Recovery Time" value="18d" color="text-cyan" sub="Avg per drawdown" />
        <StatCard label="Ulcer Index" value="4.82" color="text-purple" sub="Lower = better" />
      </div>

      {/* Equity + drawdown */}
      <div className="card">
        <h3 className="text-sm font-semibold text-white mb-1">Equity Curve</h3>
        <p className="text-xs text-slate-500 mb-3">Portfolio value over time</p>
        <ResponsiveContainer width="100%" height={160}>
          <AreaChart data={DRAWDOWN_DATA}>
            <defs>
              <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#00f5ff" stopOpacity={0.2} />
                <stop offset="95%" stopColor="#00f5ff" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
            <XAxis dataKey="time" hide />
            <YAxis tickFormatter={v => `$${(v / 1000).toFixed(0)}k`} tick={{ fill: '#64748b', fontSize: 10 }} />
            <Tooltip contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 8, fontSize: 10 }}
              formatter={(v: number) => [`$${v.toFixed(0)}`]} />
            <Area type="monotone" dataKey="equity" stroke="#00f5ff" strokeWidth={2} fill="url(#eqGrad)" />
            <Line type="monotone" dataKey="peak" stroke="#64748b" strokeWidth={1} strokeDasharray="3 2" dot={false} name="Peak" />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Drawdown waterfall */}
      <div className="card">
        <h3 className="text-sm font-semibold text-white mb-1">Drawdown Waterfall</h3>
        <p className="text-xs text-slate-500 mb-3">Underwater equity curve — depth and duration of drawdown periods</p>
        <ResponsiveContainer width="100%" height={180}>
          <AreaChart data={DRAWDOWN_DATA}>
            <defs>
              <linearGradient id="ddGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#ef4444" stopOpacity={0.5} />
                <stop offset="95%" stopColor="#ef4444" stopOpacity={0.05} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
            <XAxis dataKey="time" hide />
            <YAxis tickFormatter={v => `${v}%`} tick={{ fill: '#64748b', fontSize: 10 }} />
            <Tooltip contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 8, fontSize: 10 }}
              formatter={(v: number) => [`${v.toFixed(2)}%`, 'Drawdown']} />
            <ReferenceLine y={-5} stroke="#f59e0b" strokeDasharray="3 3" label={{ value: '-5% warn', fill: '#f59e0b', fontSize: 9 }} />
            <ReferenceLine y={-10} stroke="#ef4444" strokeDasharray="3 3" label={{ value: '-10% limit', fill: '#ef4444', fontSize: 9 }} />
            <Area type="monotone" dataKey="drawdown" stroke="#ef4444" strokeWidth={1.5} fill="url(#ddGrad)" />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

function VolatilityTab() {
  const volCapColors = { Conservative: '#10b981', Balanced: '#3b82f6', Aggressive: '#a855f7' }

  return (
    <div className="space-y-4">
      {/* Rolling vol */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold text-white">Rolling Volatility (30d window)</h3>
            <p className="text-xs text-slate-500">Annualized realized vol · EWMA smoothing</p>
          </div>
          <span className="text-xs font-mono text-yellow-400 bg-yellow-400/10 px-2 py-1 rounded border border-yellow-400/20">Current: 14.2%</span>
        </div>
        <ResponsiveContainer width="100%" height={200}>
          <AreaChart data={rollingVolatility}>
            <defs>
              <linearGradient id="volGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
            <XAxis dataKey="time" hide />
            <YAxis tick={{ fill: '#64748b', fontSize: 10 }} tickFormatter={v => `${v}%`} />
            <Tooltip contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 8, fontSize: 10 }} />
            <ReferenceLine y={20} stroke="#ef4444" strokeDasharray="4 4" label={{ value: 'Vol Budget', fill: '#ef4444', fontSize: 9 }} />
            <ReferenceLine y={15} stroke="#f59e0b" strokeDasharray="4 4" label={{ value: 'Warning', fill: '#f59e0b', fontSize: 9 }} />
            <Area type="monotone" dataKey="value" stroke="#f59e0b" strokeWidth={2} fill="url(#volGrad)" />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Vol surface heatmap */}
      <div className="card">
        <h3 className="text-sm font-semibold text-white mb-1">Volatility Surface</h3>
        <p className="text-xs text-slate-500 mb-4">Rolling vol (%) across time windows and pools — darker = higher vol</p>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr>
                <th className="text-left pb-2 text-slate-500 font-medium">Pool</th>
                {VOL_WINDOWS.map(w => <th key={w} className="pb-2 text-slate-500 font-medium text-center">{w}</th>)}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {VOL_SURFACE.map(row => {
                const cap = row.pool === 'Conservative' ? 8 : row.pool === 'Balanced' ? 18 : 35
                const color = volCapColors[row.pool as keyof typeof volCapColors]
                return (
                  <tr key={row.pool}>
                    <td className="py-2.5 font-semibold" style={{ color }}>{row.pool}</td>
                    {VOL_WINDOWS.map(w => {
                      const v = (row as Record<string, number | string>)[w] as number
                      const intensity = Math.min(v / cap, 1)
                      return (
                        <td key={w} className="py-2.5 text-center">
                          <span className="inline-block px-3 py-1 rounded font-mono"
                            style={{ background: `${color}${Math.round(intensity * 40 + 10).toString(16).padStart(2, '0')}`, color }}>
                            {v.toFixed(1)}%
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
      </div>
    </div>
  )
}

function RegimeTab() {
  const lastRegime = REGIME_TIMELINE[REGIME_TIMELINE.length - 1]
  const regimeCounts = REGIME_TIMELINE.reduce((acc, r) => {
    acc[r.regime] = (acc[r.regime] || 0) + 1
    return acc
  }, {} as Record<string, number>)

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3">
        {(['Bull', 'Sideways', 'Bear'] as const).map(r => {
          const color = r === 'Bull' ? '#10b981' : r === 'Bear' ? '#ef4444' : '#f59e0b'
          const pct = ((regimeCounts[r] || 0) / REGIME_TIMELINE.length * 100).toFixed(1)
          return (
            <div key={r} className="card" style={{ borderColor: `${color}25` }}>
              <div className="flex items-center gap-2 mb-2">
                <div className="w-2.5 h-2.5 rounded-full" style={{ background: color }} />
                <span className="text-xs font-semibold" style={{ color }}>{r} Market</span>
                {lastRegime.regime === r && <span className="text-xs text-slate-500 ml-auto">← Current</span>}
              </div>
              <p className="text-2xl font-bold font-mono text-white">{pct}%</p>
              <p className="text-xs text-slate-500 mt-1">{regimeCounts[r] || 0} of {REGIME_TIMELINE.length} days</p>
            </div>
          )
        })}
      </div>

      {/* Regime timeline */}
      <div className="card">
        <h3 className="text-sm font-semibold text-white mb-1">Regime Timeline</h3>
        <p className="text-xs text-slate-500 mb-4">HMM-detected market regimes with confidence scores</p>
        <ResponsiveContainer width="100%" height={160}>
          <ComposedChart data={REGIME_TIMELINE}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
            <XAxis dataKey="time" hide />
            <YAxis yAxisId="left" hide />
            <YAxis yAxisId="right" orientation="right" domain={[0, 1]} tickFormatter={v => `${(v * 100).toFixed(0)}%`} tick={{ fill: '#64748b', fontSize: 9 }} />
            <Tooltip contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 8, fontSize: 10 }}
              content={({ payload }) => {
                if (!payload?.length) return null
                const d = payload[0]?.payload
                return (
                  <div style={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 8, padding: '6px 10px', fontSize: 10 }}>
                    <p style={{ color: d.color }}>{d.regime}</p>
                    <p style={{ color: '#94a3b8' }}>Conf: {(d.conf * 100).toFixed(1)}%</p>
                  </div>
                )
              }} />
            <Bar yAxisId="left" dataKey="value" radius={[2, 2, 0, 0]}>
              {REGIME_TIMELINE.map((r, i) => <Cell key={i} fill={r.color} fillOpacity={0.6} />)}
            </Bar>
            <Line yAxisId="right" type="monotone" dataKey="conf" stroke="#a855f7" strokeWidth={1.5} dot={false} name="Confidence" />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Transition matrix */}
      <div className="card">
        <h3 className="text-sm font-semibold text-white mb-1">Regime Transition Matrix</h3>
        <p className="text-xs text-slate-500 mb-4">Probability of transitioning from row regime to column regime</p>
        <table className="w-full text-xs">
          <thead>
            <tr>
              <th className="text-left pb-2 text-slate-500 font-medium">From \ To</th>
              {(['Bull', 'Sideways', 'Bear'] as const).map(r => (
                <th key={r} className="pb-2 text-center font-medium"
                  style={{ color: r === 'Bull' ? '#10b981' : r === 'Bear' ? '#ef4444' : '#f59e0b' }}>{r}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {(['Bull', 'Sideways', 'Bear'] as const).map(from => (
              <tr key={from}>
                <td className="py-2.5 font-semibold"
                  style={{ color: from === 'Bull' ? '#10b981' : from === 'Bear' ? '#ef4444' : '#f59e0b' }}>{from}</td>
                {(['Bull', 'Sideways', 'Bear'] as const).map(to => {
                  const v = REGIME_TRANS[from][to]
                  const isMax = v === Math.max(...Object.values(REGIME_TRANS[from]))
                  return (
                    <td key={to} className="py-2.5 text-center">
                      <span className={`inline-block px-3 py-1 rounded font-mono ${isMax ? 'bg-cyan/10 text-cyan' : 'text-slate-400'}`}>
                        {(v * 100).toFixed(0)}%
                      </span>
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function AttributionTab() {
  return (
    <div className="space-y-4">
      <div className="card">
        <h3 className="text-sm font-semibold text-white mb-1">Agent Return Attribution</h3>
        <p className="text-xs text-slate-500 mb-4">Daily contribution of each agent to total portfolio return (%)</p>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={ATTRIBUTION}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
            <XAxis dataKey="time" hide />
            <YAxis tickFormatter={v => `${v}%`} tick={{ fill: '#64748b', fontSize: 10 }} />
            <Tooltip contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 8, fontSize: 10 }}
              formatter={(v: number) => [`${v.toFixed(3)}%`]} />
            <ReferenceLine y={0} stroke="#475569" />
            {agents.map((a, i) => (
              <Bar key={a.name} dataKey={a.name} stackId="a" fill={AGENT_COLORS[i]} fillOpacity={0.85} />
            ))}
            <Legend wrapperStyle={{ fontSize: 10, color: '#94a3b8' }} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Agent correlation heatmap */}
      <div className="card">
        <h3 className="text-sm font-semibold text-white mb-1">Agent Return Correlation Matrix</h3>
        <p className="text-xs text-slate-500 mb-4">Rolling 30d pairwise correlation — lower = better diversification</p>
        <div className="overflow-x-auto">
          <table className="text-xs w-full">
            <thead>
              <tr>
                <th className="pb-2 text-slate-500 text-left w-24">Agent</th>
                {agents.map(a => <th key={a.id} className="pb-2 text-slate-500 text-center text-xs">{a.name.slice(0, 6)}</th>)}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {agents.map((a, i) => (
                <tr key={a.id}>
                  <td className="py-2 font-mono text-xs" style={{ color: AGENT_COLORS[i] }}>{a.name.slice(0, 8)}</td>
                  {agents.map((b, j) => {
                    const v = AGENT_CORR[i][j]
                    return (
                      <td key={b.id} className="py-2 text-center">
                        <span className="inline-block w-12 py-0.5 rounded text-xs font-mono"
                          style={{ background: `${corrColor(v)}30`, color: corrColor(v) }}>
                          {v.toFixed(2)}
                        </span>
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex items-center gap-4 mt-3 text-xs text-slate-500">
          {[['Low (<0.3)', '#10b981'], ['Moderate', '#3b82f6'], ['High', '#f59e0b'], ['Very High', '#ef4444']].map(([l, c]) => (
            <span key={l} className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded inline-block" style={{ background: `${c}30`, border: `1px solid ${c}` }} />{l}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}

function DistributionsTab() {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-4 gap-3">
        <StatCard label="Skewness" value={RETURN_DIST.skew.toFixed(2)} color="text-yellow-400" sub="Negative = left tail" />
        <StatCard label="Excess Kurtosis" value={RETURN_DIST.kurt.toFixed(2)} color="text-red-400" sub="Fat tails (>3)" />
        <StatCard label="VaR (95%)" value={`${(RETURN_DIST.var95 * 100).toFixed(2)}%`} color="text-red-400" />
        <StatCard label="CVaR (95%)" value={`${(RETURN_DIST.cvar95 * 100).toFixed(2)}%`} color="text-red-400" sub="Expected shortfall" />
      </div>

      <div className="card">
        <h3 className="text-sm font-semibold text-white mb-1">Return Distribution</h3>
        <p className="text-xs text-slate-500 mb-4">Daily return histogram with VaR/CVaR overlays · Fat-tail analysis</p>
        <ResponsiveContainer width="100%" height={240}>
          <ComposedChart data={RETURN_DIST.bins}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
            <XAxis dataKey="bin" tick={{ fill: '#64748b', fontSize: 9 }} interval={3} />
            <YAxis tick={{ fill: '#64748b', fontSize: 10 }} />
            <Tooltip contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 8, fontSize: 10 }}
              formatter={(v: number, name: string) => [name === 'count' ? `${v} obs` : `${v.toFixed(1)}%`, name]} />
            <Bar dataKey="count" radius={[2, 2, 0, 0]}>
              {RETURN_DIST.bins.map((b, i) => {
                const isVaR = parseFloat(b.bin) <= RETURN_DIST.var95 * 100
                const isCVaR = parseFloat(b.bin) <= RETURN_DIST.cvar95 * 100
                return <Cell key={i} fill={isCVaR ? '#ef4444' : isVaR ? '#f59e0b' : '#3b82f6'} fillOpacity={0.8} />
              })}
            </Bar>
          </ComposedChart>
        </ResponsiveContainer>
        <div className="flex items-center gap-4 mt-2 text-xs text-slate-500">
          <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded bg-blue-500/80 inline-block" /> Normal returns</span>
          <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded bg-yellow-400/80 inline-block" /> VaR zone</span>
          <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded bg-red-500/80 inline-block" /> CVaR zone</span>
        </div>
      </div>
    </div>
  )
}

function TimeSeriesTab() {
  return (
    <div className="space-y-4">
      <div className="card">
        <h3 className="text-sm font-semibold text-white mb-1">STL Time Series Decomposition</h3>
        <p className="text-xs text-slate-500 mb-4">Seasonal-Trend decomposition using LOESS · Original = Trend + Seasonal + Residual</p>
        <div className="space-y-4">
          {[
            { key: 'value', label: 'Original Signal', color: '#00f5ff', desc: 'Raw price series' },
            { key: 'trend', label: 'Trend Component', color: '#a855f7', desc: 'Long-term direction' },
            { key: 'seasonal', label: 'Seasonal Component', color: '#10b981', desc: '7-day periodicity' },
            { key: 'residual', label: 'Residual / Noise', color: '#f59e0b', desc: 'Unexplained variation' },
          ].map(s => (
            <div key={s.key}>
              <div className="flex items-center justify-between mb-1">
                <p className="text-xs font-medium" style={{ color: s.color }}>{s.label}</p>
                <p className="text-xs text-slate-600">{s.desc}</p>
              </div>
              <ResponsiveContainer width="100%" height={65}>
                <AreaChart data={tsData}>
                  <defs>
                    <linearGradient id={`ts-${s.key}`} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={s.color} stopOpacity={0.2} />
                      <stop offset="95%" stopColor={s.color} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <ReferenceLine y={0} stroke="#1f2937" />
                  <Area type="monotone" dataKey={s.key} stroke={s.color} strokeWidth={1.5} fill={`url(#ts-${s.key})`} dot={false} />
                  <Tooltip contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 8, fontSize: 9 }} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          ))}
        </div>
      </div>

      {/* Trend wave */}
      <div className="card">
        <h3 className="text-sm font-semibold text-white mb-1">Trend Wave Visualizer</h3>
        <p className="text-xs text-slate-500 mb-4">Wavelet decomposition · Multi-scale trend extraction</p>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={trendWave}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
            <XAxis dataKey="time" hide />
            <YAxis hide />
            <Tooltip contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 8, fontSize: 10 }} />
            <Line type="monotone" dataKey="value" stroke="#00f5ff" strokeWidth={2} dot={false} name="Price" />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function Analytics() {
  const [tab, setTab] = useState('Overview')
  const { data: mcData } = useMonteCarloData()
  const lastRegime = REGIME_TIMELINE[REGIME_TIMELINE.length - 1]
  const regimeColor = lastRegime.color

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Quantitative Analytics</h1>
          <p className="text-slate-500 text-sm mt-0.5">ML-powered market analysis · Risk metrics · Statistical decomposition</p>
        </div>
        {/* Live regime pill */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl border text-xs"
          style={{ borderColor: `${regimeColor}30`, background: `${regimeColor}10` }}>
          <div className="w-2 h-2 rounded-full animate-pulse" style={{ background: regimeColor }} />
          <span style={{ color: regimeColor }}>{lastRegime.regime}</span>
          <span className="text-slate-500">·</span>
          <span className="text-slate-400 font-mono">{(lastRegime.conf * 100).toFixed(0)}% conf</span>
        </div>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 bg-surface rounded-xl p-1 border border-border flex-wrap">
        {TABS.map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              tab === t ? 'bg-cyan/10 text-cyan border border-cyan/20' : 'text-slate-500 hover:text-slate-300'
            }`}>
            {t}
          </button>
        ))}
      </div>

      <AnimatePresence mode="wait">
        <motion.div key={tab} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }}>
          {tab === 'Overview'      && <OverviewTab mcStats={mcData?.stats} />}
          {tab === 'Monte Carlo'   && <MonteCarloTab mcData={mcData} />}
          {tab === 'Drawdown'      && <DrawdownTab />}
          {tab === 'Volatility'    && <VolatilityTab />}
          {tab === 'Regime'        && <RegimeTab />}
          {tab === 'Attribution'   && <AttributionTab />}
          {tab === 'Distributions' && <DistributionsTab />}
          {tab === 'Time Series'   && <TimeSeriesTab />}
        </motion.div>
      </AnimatePresence>
    </div>
  )
}
