import { Brain, Sparkles, ShieldAlert } from 'lucide-react'
import IntelligencePanel from '../components/IntelligencePanel'
import { useDemoState, useIntelligenceLoop } from '../hooks/useIntelligence'

export default function Intelligence() {
  const { data: loop } = useIntelligenceLoop()
  const { data: demo } = useDemoState()

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white">Financial Intelligence Engine</h1>
          <p className="text-slate-500 text-sm mt-0.5">LangGraph-style orchestration for autonomous capital allocation, visible in real time.</p>
        </div>
        <div className="rounded-xl border border-cyan/20 bg-cyan/10 px-3 py-2 text-right">
          <p className="text-xs text-cyan">Protocol Posture</p>
          <p className="text-sm font-semibold text-white capitalize">{loop?.meta_agent.capital_posture ?? 'loading'}</p>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div className="card">
          <div className="flex items-center gap-2 mb-2 text-cyan">
            <Brain size={14} />
            <h3 className="text-sm font-semibold text-white">Core Claim</h3>
          </div>
          <p className="text-sm text-slate-300 leading-relaxed">
            This is not a DeFi dashboard. It is a self-evolving financial intelligence system where capital, risk,
            and governance move through a visible autonomous loop.
          </p>
        </div>
        <div className="card">
          <div className="flex items-center gap-2 mb-2 text-purple">
            <Sparkles size={14} />
            <h3 className="text-sm font-semibold text-white">Judge Prompt</h3>
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">
            {demo?.contract_prompt_example ?? 'Loading contract builder prompt…'}
          </p>
        </div>
        <div className="card">
          <div className="flex items-center gap-2 mb-2 text-red-300">
            <ShieldAlert size={14} />
            <h3 className="text-sm font-semibold text-white">Enforcement</h3>
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">
            {loop?.slashing_summary.candidates.length
              ? `${loop.slashing_summary.candidates[0].name} is currently on slashing watch after breaching protocol trust thresholds.`
              : 'No agents are currently breaching the rogue-agent thresholds.'}
          </p>
        </div>
      </div>

      <IntelligencePanel loop={loop} demo={demo} />

      {demo && (
        <div className="grid grid-cols-2 gap-4">
          <div className="card">
            <h3 className="text-sm font-semibold text-white mb-3">Judge Talking Points</h3>
            <div className="space-y-2">
              {demo.talking_points.map(point => (
                <div key={point} className="rounded-lg border border-border bg-slate-900/50 px-3 py-2 text-sm text-slate-300">
                  {point}
                </div>
              ))}
            </div>
          </div>
          <div className="card">
            <h3 className="text-sm font-semibold text-white mb-3">Live Agent Decisions</h3>
            <div className="space-y-2">
              {loop?.agents.slice(0, 5).map(agent => (
                <div key={agent.id} className="rounded-lg border border-border bg-slate-900/50 px-3 py-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-white">{agent.name}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full border ${agent.decision === 'BUY' ? 'bg-green/10 text-green border-green/20' : agent.decision === 'SELL' ? 'bg-red-500/10 text-red-300 border-red-500/20' : 'bg-slate-500/10 text-slate-300 border-slate-500/20'}`}>
                      {agent.decision}
                    </span>
                  </div>
                  <div className="flex items-center justify-between mt-1 text-xs text-slate-500">
                    <span>{agent.model}</span>
                    <span>Confidence {(agent.confidence_score * 100).toFixed(0)}%</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
