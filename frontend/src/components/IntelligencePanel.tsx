import { Brain, ShieldAlert, Sparkles, TrendingUp } from 'lucide-react'
import { DemoState, IntelligenceLoopState } from '../hooks/useIntelligence'

function statusClasses(status: 'complete' | 'active' | 'pending') {
  if (status === 'complete') return 'bg-green/10 text-green border-green/20'
  if (status === 'active') return 'bg-cyan/10 text-cyan border-cyan/20'
  return 'bg-slate-500/10 text-slate-400 border-slate-500/20'
}

export default function IntelligencePanel({
  loop,
  demo,
  compact = false,
}: {
  loop?: IntelligenceLoopState
  demo?: DemoState
  compact?: boolean
}) {
  if (!loop && !demo) {
    return (
      <div className="card">
        <p className="text-sm text-slate-400">Intelligence layer loading…</p>
      </div>
    )
  }

  const state = loop ?? demo?.loop_snapshot
  if (!state) return null

  return (
    <div className="card space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <Brain size={14} className="text-cyan" />
            <h3 className="text-sm font-semibold text-white">Autonomous Capital Brain</h3>
            <span className="text-xs px-2 py-0.5 rounded-full border bg-cyan/10 text-cyan border-cyan/20">
              {state.regime}
            </span>
          </div>
          <p className="text-xs text-slate-500">{state.meta_agent.recommendation}</p>
        </div>
        <div className="text-right shrink-0">
          <p className="text-xs text-slate-500">Autonomy Score</p>
          <p className="text-lg font-bold font-mono text-cyan">{state.system_metrics.autonomy_score}</p>
        </div>
      </div>

      <div className={`grid gap-3 ${compact ? 'grid-cols-2' : 'grid-cols-4'}`}>
        <div className="rounded-xl border border-border bg-slate-900/60 p-3">
          <p className="text-xs text-slate-500">Portfolio VaR</p>
          <p className="text-lg font-bold font-mono text-white mt-1">{state.system_metrics.portfolio_var_95_pct}%</p>
        </div>
        <div className="rounded-xl border border-border bg-slate-900/60 p-3">
          <p className="text-xs text-slate-500">Avg Confidence</p>
          <p className="text-lg font-bold font-mono text-white mt-1">{(state.system_metrics.avg_confidence * 100).toFixed(0)}%</p>
        </div>
        <div className="rounded-xl border border-border bg-slate-900/60 p-3">
          <p className="text-xs text-slate-500">Execution Latency</p>
          <p className="text-lg font-bold font-mono text-white mt-1">{state.system_metrics.execution_latency_ms}ms</p>
        </div>
        <div className="rounded-xl border border-border bg-slate-900/60 p-3">
          <p className="text-xs text-slate-500">Active Agents</p>
          <p className="text-lg font-bold font-mono text-white mt-1">{state.system_metrics.active_agents}</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2 text-xs text-slate-400">
            <Sparkles size={12} /> Orchestration Loop
          </div>
          <div className="space-y-2">
            {state.stage_status.map(stage => (
              <div key={stage.key} className="flex items-center justify-between rounded-lg border border-border bg-slate-900/50 px-3 py-2">
                <span className="text-xs text-slate-300">{stage.label}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full border ${statusClasses(stage.status)}`}>{stage.status}</span>
              </div>
            ))}
          </div>
        </div>

        <div>
          <div className="flex items-center gap-2 mb-2 text-xs text-slate-400">
            <TrendingUp size={12} /> Capital Winners
          </div>
          <div className="space-y-2">
            {state.leaderboard.slice(0, compact ? 3 : 4).map(item => (
              <div key={item.agent_id} className="rounded-lg border border-border bg-slate-900/50 px-3 py-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-white">#{item.rank} {item.name}</span>
                  <span className="text-xs text-cyan font-mono">{item.capital_allocated_pct}%</span>
                </div>
                <div className="flex items-center justify-between mt-1 text-xs text-slate-500">
                  <span>{item.model}</span>
                  <span>Trust {item.trust_score}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {state.slashing_summary.candidates.length > 0 && (
        <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-3">
          <div className="flex items-center gap-2 mb-2 text-xs text-red-300">
            <ShieldAlert size={12} /> Slashing Watchlist
          </div>
          <div className="space-y-1.5">
            {state.slashing_summary.candidates.slice(0, compact ? 1 : 2).map(candidate => (
              <div key={candidate.agent_id} className="flex items-center justify-between text-xs">
                <span className="text-slate-300">{candidate.name} · {candidate.reason}</span>
                <span className="font-mono text-red-300">-{candidate.slash_pct}%</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {demo && !compact && (
        <div className="rounded-xl border border-purple/20 bg-purple/5 p-3">
          <div className="flex items-center gap-2 mb-2 text-xs text-purple">
            <Sparkles size={12} /> Judge Demo Script
          </div>
          <div className="space-y-2">
            {demo.judge_script.slice(0, 4).map(item => (
              <div key={item.step} className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs text-white">{item.step}. {item.title}</p>
                  <p className="text-xs text-slate-500 mt-0.5">{item.description}</p>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded-full border shrink-0 ${statusClasses(item.status)}`}>{item.status}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
