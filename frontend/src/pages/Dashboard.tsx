import { DollarSign, TrendingUp, Users, Shield } from 'lucide-react'

const metrics = [
  { label: 'Total Portfolio Value', value: '$1,284,720', icon: DollarSign },
  { label: 'Unrealized PnL', value: '+$142,380', icon: TrendingUp },
  { label: 'Active Agents', value: '6 / 47', icon: Users },
  { label: 'Risk Score', value: '72 / 100', icon: Shield },
]

function useSimulatedPnL() {
  const [simPnL, setSimPnL] = useState<{ x: number; pnl: number }[]>([])
  const cumRef = useRef(0)
  const tickRef = useRef(0)
  useEffect(() => {
    const interval = setInterval(() => {
      const delta = (Math.random() - 0.48) * 0.002
      cumRef.current += delta
      tickRef.current += 1
      setSimPnL(prev => [...prev, { x: tickRef.current, pnl: cumRef.current }].slice(-100))
    }, 3000)
    return () => clearInterval(interval)
  }, [])
  return simPnL
}

function ActiveSessionPanel() {
  const navigate = useNavigate()
  const { sessions, activeSessionId, endSession, addTradeRecord, incrementSessionTrades } = useProtocolStore()
  const session = sessions.find(s => s.id === activeSessionId && s.status === 'active')
  const { messages } = useWebSocket(WS_TRADING_URL)

  const agentMessages = messages

  const [livePnL, setLivePnL] = useState(0)
  const [pnlHistory, setPnlHistory] = useState<{ t: number; pnl: number }[]>([])
  const [elapsed, setElapsed] = useState(0)
  const [stopping, setStopping] = useState(false)
  const tradeCountRef = useRef(0)
  const tradeRecordsRef = useRef<TradeRecord[]>([])
  const livePnLRef = useRef(0)

  const TOKENS = ['WBTC', 'USDC', 'LINK', 'UNI']
  const TOKEN_PRICES: Record<string, number> = { WBTC: 30000, USDC: 1, LINK: 15, UNI: 8 }

  useEffect(() => {
    if (!session || agentMessages.length === 0) return
    const last = agentMessages[agentMessages.length - 1]
    const tokenVal = Number(last.amountOut) * (TOKEN_PRICE_ETH[last.token] ?? 0) / 1e18
    const ethSpent = Number(last.amountIn) / 1e18
    const delta = tokenVal - ethSpent
    setLivePnL(prev => {
      const next = prev + delta
      livePnLRef.current = next
      setPnlHistory(h => [...h, { t: h.length, pnl: next }].slice(-120))
      return next
    })
    tradeCountRef.current += 1
    incrementSessionTrades(session.agentId)
  }, [agentMessages.length])

  useEffect(() => {
    if (!session) return
    const t = setInterval(() => setElapsed(Math.floor((Date.now() - session.startTime) / 1000)), 1000)
    return () => clearInterval(t)
  }, [session?.id])

  useEffect(() => {
    if (!session) return
    const t = setInterval(() => {
      const token = TOKENS[Math.floor(Math.random() * TOKENS.length)]
      const tradeSize = session.ethDeposited * (0.05 + Math.random() * 0.1)
      const returnPct = (Math.random() - 0.46) * 0.008
      const delta = tradeSize * returnPct
      const price = TOKEN_PRICES[token] * (1 + (Math.random() - 0.5) * 0.02)
      const tokenAmount = (tradeSize / price) * 1e18

      const record: TradeRecord = {
        id: `trade-${Date.now()}`,
        timestamp: Date.now(),
        token,
        type: returnPct > 0 ? 'BUY' : 'SELL',
        ethAmount: tradeSize,
        tokenAmount,
        price,
        pnlDelta: delta,
        decision: returnPct > 0.002 ? 'BUY' : returnPct < -0.002 ? 'SELL' : 'HOLD',
        confidence: 0.5 + Math.random() * 0.45,
      }

      tradeRecordsRef.current = [...tradeRecordsRef.current, record].slice(-500)
      addTradeRecord(session.id, record)

      setLivePnL(prev => {
        const next = prev + delta
        livePnLRef.current = next
        setPnlHistory(h => [...h, { t: h.length, pnl: next }].slice(-120))
        return next
      })
      tradeCountRef.current += 1
      incrementSessionTrades(session.agentId)
    }, 3000)
    return () => clearInterval(t)
  }, [session?.id])

  const handleStop = async () => {
    if (!session) return
    setStopping(true)

    fetch(`${API_BASE_URL}/api/agents/${session.agentId}/stop-trading`, { method: 'POST' }).catch(() => {})

    const currentSession = useProtocolStore.getState().sessions.find(s => s.id === session.id)
    const finalPnL = livePnLRef.current !== 0 ? livePnLRef.current : (currentSession?.tradeRecords ?? []).reduce((s, t) => s + t.pnlDelta, 0)
    const finalTrades = tradeCountRef.current > 0 ? tradeCountRef.current : (currentSession?.tradeRecords?.length ?? 0)
    endSession(
      session.id,
      finalPnL,
      finalTrades,
      currentSession?.tradeRecords ?? tradeRecordsRef.current
    )
    navigate('/pnl-history')
  }

  if (!session) return null

  const pnlColor = livePnL >= 0 ? '#10b981' : '#ef4444'
  const riskColor = RISK_COLORS[session.agentRisk] ?? '#64748b'
  const pnlPct = session.ethDeposited > 0 ? (livePnL / session.ethDeposited) * 100 : 0
  const elapsed_fmt = `${Math.floor(elapsed / 60)}m ${elapsed % 60}s`

  return (
    <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
      className="card border-2" style={{ borderColor: `${riskColor}40` }}>
      {}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-3 h-3 rounded-full animate-pulse" style={{ background: riskColor }} />
          <div>
            <div className="flex items-center gap-2">
              <p className="text-sm font-bold text-white">{session.agentName}</p>
              <span className="text-xs px-2 py-0.5 rounded-full border font-medium"
                style={{ color: riskColor, borderColor: `${riskColor}30`, background: `${riskColor}10` }}>
                {session.agentRisk}
              </span>
              <span className="flex items-center gap-1 text-xs text-green bg-green/10 border border-green/20 px-2 py-0.5 rounded-full">
                <Activity size={9} className="animate-pulse" /> Live Trading
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Deposited: <span className="font-mono text-white">{session.ethDeposited.toFixed(4)} ETH</span>
              <span className="mx-2">·</span>
              <Clock size={9} className="inline mr-1" />{elapsed_fmt}
              <span className="mx-2">·</span>
              {session.trades} trades
            </p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          {}
          <div className="text-right">
            <p className="text-xs text-slate-500">Net PnL</p>
            <p className={`text-xl font-bold font-mono ${livePnL >= 0 ? 'text-green' : 'text-red-400'}`}>
              {livePnL >= 0 ? '+' : ''}{livePnL.toFixed(6)} ETH
            </p>
            <p className={`text-xs font-mono ${pnlPct >= 0 ? 'text-green' : 'text-red-400'}`}>
              {pnlPct >= 0 ? '+' : ''}{pnlPct.toFixed(2)}% of deposit
            </p>
          </div>
          <button onClick={handleStop} disabled={stopping}
            className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20 transition-all disabled:opacity-50">
            <Square size={12} fill="currentColor" />
            {stopping ? 'Stopping…' : 'Stop Trading'}
          </button>
        </div>
      </div>

      {}
      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-2">
          <p className="text-xs text-slate-500 mb-2">Live PnL vs Deposited ETH</p>
          <ResponsiveContainer width="100%" height={120}>
            <AreaChart data={pnlHistory}>
              <defs>
                <linearGradient id="sessionPnl" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={pnlColor} stopOpacity={0.3} />
                  <stop offset="95%" stopColor={pnlColor} stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="t" hide />
              <YAxis tickFormatter={(v: number) => `${v > 0 ? '+' : ''}${v.toFixed(4)}`}
                tick={{ fontSize: 9, fill: '#64748b' }} width={55} />
              <ReferenceLine y={0} stroke="#475569" strokeDasharray="3 3" />
              <Tooltip contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 6, fontSize: 10 }}
                formatter={(v: number) => [`${v >= 0 ? '+' : ''}${v.toFixed(6)} ETH`, 'PnL']} />
              <Area type="monotone" dataKey="pnl" stroke={pnlColor} strokeWidth={2}
                fill="url(#sessionPnl)" dot={false} isAnimationActive={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
        <div className="space-y-2">
          {[
            { label: 'Deposited', value: `${session.ethDeposited.toFixed(4)} ETH`, color: 'text-white' },
            { label: 'Current Value', value: `${(session.ethDeposited + livePnL).toFixed(4)} ETH`, color: livePnL >= 0 ? 'text-green' : 'text-red-400' },
            { label: 'Net PnL', value: `${livePnL >= 0 ? '+' : ''}${livePnL.toFixed(6)} ETH`, color: livePnL >= 0 ? 'text-green' : 'text-red-400' },
            { label: 'Return %', value: `${pnlPct >= 0 ? '+' : ''}${pnlPct.toFixed(3)}%`, color: pnlPct >= 0 ? 'text-green' : 'text-red-400' },
            { label: 'Trades', value: session.trades, color: 'text-cyan' },
          ].map(s => (
            <div key={s.label} className="flex justify-between text-xs">
              <span className="text-slate-500">{s.label}</span>
              <span className={`font-mono ${s.color}`}>{s.value}</span>
            </div>
          ))}
          <button onClick={() => navigate('/pnl-history')}
            className="w-full mt-2 py-1 rounded-lg text-xs text-slate-400 border border-border hover:border-slate-500 transition-all flex items-center justify-center gap-1">
            <History size={10} /> View History
          </button>
        </div>
      </div>

      {}
      <div className="mt-3 pt-3 border-t border-border">
        <AgentTradingDashboard
          agentId={session.agentId}
          agentName={session.agentName}
          messages={agentMessages}
          sessionId={session.id}
        />
      </div>
    </motion.div>
  )
}

export default function Dashboard() {
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold text-white">Autonomous Capital Brain</h1>
        <p className="text-slate-500 text-sm mt-0.5">Real-time orchestration of agent intelligence, risk, and capital rotation</p>
      </div>

      {}
      <AnimatePresence>
        {activeSession && <ActiveSessionPanel />}
      </AnimatePresence>

      <IntelligencePanel loop={loop} demo={demo} compact />

<<<<<<< HEAD
      <div className={`card border ${supabaseHealthy ? 'border-emerald-500/20' : 'border-amber-500/20'}`}>
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${supabaseHealthy ? 'bg-emerald-500/10' : 'bg-amber-500/10'}`}>
              <Database size={16} className={supabaseHealthy ? 'text-emerald-400' : 'text-amber-400'} />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">Supabase Bridge</h3>
              <p className="text-xs text-slate-500 mt-1">
                {supabaseStatusLoading
                  ? 'Checking backend connectivity to Supabase...'
                  : supabaseStatus?.configured
                    ? `${supabaseStatus.project_ref || 'Configured project'} is wired into the FastAPI backend.`
                    : 'Supabase credentials are not configured for the backend.'}
              </p>
            </div>
          </div>
          <div className={`text-xs font-mono px-3 py-1.5 rounded-lg border ${
            supabaseHealthy
              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
              : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
          }`}>
            {supabaseStatusLoading ? 'Checking' : supabaseHealthy ? 'Live' : 'Needs Attention'}
          </div>
        </div>

        <div className="grid grid-cols-3 gap-3 mt-4">
          <div className="rounded-xl border border-border bg-slate-950/70 p-3">
            <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Auth API</p>
            <p className={`mt-2 text-sm font-semibold ${supabaseStatus?.auth_reachable ? 'text-emerald-400' : 'text-slate-300'}`}>
              {supabaseStatus?.auth_reachable ? 'Reachable' : 'Pending'}
            </p>
          </div>
          <div className="rounded-xl border border-border bg-slate-950/70 p-3">
            <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Storage API</p>
            <p className={`mt-2 text-sm font-semibold ${supabaseStatus?.storage_reachable ? 'text-emerald-400' : 'text-slate-300'}`}>
              {supabaseStatus?.storage_reachable ? 'Reachable' : 'Pending'}
            </p>
          </div>
          <div className="rounded-xl border border-border bg-slate-950/70 p-3">
            <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Database URL</p>
            <p className={`mt-2 text-sm font-semibold ${supabaseStatus?.using_supabase_database ? 'text-cyan' : 'text-slate-300'}`}>
              {supabaseStatus?.using_supabase_database ? 'Supabase Postgres' : 'Not Detected'}
            </p>
          </div>
        </div>

        {supabaseStatus?.error && (
          <p className="mt-3 text-xs text-amber-300">{supabaseStatus.error}</p>
        )}
      </div>

=======
>>>>>>> D!
      {}
      <div className="grid grid-cols-3 gap-4">
        {metrics.map((m, i) => (
          <motion.div key={m.label} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }} className="card">
            <div className="flex items-start justify-between mb-3">
              <div className="w-8 h-8 rounded-lg bg-cyan/10 flex items-center justify-center">
                <m.icon size={14} className="text-cyan" />
              </div>
            </div>
            <div className="text-xl font-bold text-white">{m.value}</div>
            <div className="text-xs text-slate-500 mt-0.5">{m.label}</div>
          </motion.div>
        ))}
      </div>

      {}
      <LivePriceChart prices={prices} connected={pricesConnected} />

      {}
      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-2 card">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h3 className="text-sm font-semibold text-white">Portfolio Value</h3>
              <p className="text-xs text-slate-500">90-day OHLC · simulated</p>
            </div>
            <span className="text-xs font-mono text-green bg-green/10 px-2 py-1 rounded">+12.4%</span>
          </div>
          <CandlestickChart
            data={portfolioOHLC}
            height={220}
          />
        </div>

        <div className="card">
          <h3 className="text-sm font-semibold text-white mb-1">Capital Allocation</h3>
          <p className="text-xs text-slate-500 mb-3">By agent weight</p>
          <ResponsiveContainer width="100%" height={140}>
            <PieChart>
              <Pie data={allocationData} cx="50%" cy="50%" innerRadius={40} outerRadius={65} dataKey="value" paddingAngle={3}>
                {allocationData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 8, fontSize: 11 }} />
            </PieChart>
          </ResponsiveContainer>
          <div className="space-y-1 mt-2">
            {allocationData.slice(0, 4).map((d, i) => (
              <div key={d.name} className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-1.5">
                  <div className="w-2 h-2 rounded-full" style={{ background: COLORS[i] }} />
                  <span className="text-slate-400">{d.name}</span>
                </div>
                <span className="text-slate-300 font-mono">{d.value}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {}
      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-2 card">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h3 className="text-sm font-semibold text-white">Live PnL</h3>
              <p className="text-xs text-slate-500">
                {messages.length > 0 ? 'From real trades · OHLC' : 'Simulated OHLC · no trades yet'}
              </p>
            </div>
            <div className={`text-xs font-mono px-2 py-0.5 rounded-full ${
              displayPnL >= 0 ? 'bg-green/10 text-green' : 'bg-red-500/10 text-red-400'
            }`}>
              {displayPnL >= 0 ? '+' : ''}{displayPnL.toFixed(6)} ETH
            </div>
          </div>
          <CandlestickChart
            data={pnlOHLC}
            height={220}
          />
        </div>
        <AgentPredictionPanel agentId={activeAgentId} agentMode={agentMode} onToggleMode={setAgentMode} />
      </div>

      {}
      <TradingFeed messages={messages} />

      {}
      <div className="card">
        <h3 className="text-sm font-semibold text-white mb-4">Top Agents by Allocation</h3>
        <table className="w-full text-xs">
          <thead>
            <tr className="text-slate-500 border-b border-border">
              {['Agent', 'Strategy', 'Sharpe', 'Drawdown', 'Allocation', 'PnL', 'Status'].map(h => (
                <th key={h} className="text-left pb-2 font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {mockAgents.map(a => (
              <tr key={a.id} className="hover:bg-white/2 transition-colors">
                <td className="py-2.5 font-mono text-cyan">{a.name}</td>
                <td className="py-2.5 text-slate-400">{a.strategy}</td>
                <td className="py-2.5 text-green font-mono">{a.sharpe}</td>
                <td className="py-2.5 text-red-400 font-mono">{a.drawdown}%</td>
                <td className="py-2.5">
                  <div className="flex items-center gap-2">
                    <div className="w-16 h-1.5 bg-border rounded-full overflow-hidden">
                      <div className="h-full bg-cyan rounded-full" style={{ width: `${a.allocation}%` }} />
                    </div>
                    <span className="font-mono text-slate-300">{a.allocation}%</span>
                  </div>
                </td>
                <td className={`py-2.5 font-mono ${a.pnl > 0 ? 'text-green' : 'text-red-400'}`}>+{a.pnl}%</td>
                <td className="py-2.5">
                  <span className={`px-2 py-0.5 rounded-full text-xs ${a.status === 'active' ? 'bg-green/10 text-green' : 'bg-yellow-400/10 text-yellow-400'}`}>
                    {a.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
