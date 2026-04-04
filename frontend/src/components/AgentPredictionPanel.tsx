import { useEffect, useState } from 'react'
import { TrendingUp, TrendingDown, Minus, Brain } from 'lucide-react'

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

interface Props {
  agentId: string
  agentMode: boolean
  onToggleMode: (enabled: boolean) => void
}

const DECISION_STYLES: Record<string, { bg: string; text: string; icon: React.ElementType }> = {
  BUY:  { bg: 'bg-green/10 border-green/20',   text: 'text-green',   icon: TrendingUp },
  SELL: { bg: 'bg-red-500/10 border-red-500/20', text: 'text-red-400', icon: TrendingDown },
  HOLD: { bg: 'bg-slate-700/50 border-border',   text: 'text-slate-400', icon: Minus },
}

export default function AgentPredictionPanel({ agentId, agentMode, onToggleMode }: Props) {
  const [predictions, setPredictions] = useState<Prediction[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!agentMode) return
    const fetchPredictions = async () => {
      try {
        const res = await fetch(`/api/prices/predictions/${agentId}`)
        if (res.ok) {
          const data = await res.json()
          setPredictions(data.predictions ?? [])
        }
      } catch {  }
    }

    fetchPredictions()
    const interval = setInterval(fetchPredictions, 5000)
    return () => clearInterval(interval)
  }, [agentId, agentMode])

  const handleToggle = async (enabled: boolean) => {
    setLoading(true)
    try {
      await fetch(`/api/agent-mode/${agentId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled }),
      })
      onToggleMode(enabled)
    } catch {  }
    setLoading(false)
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Brain size={16} className={agentMode ? 'text-cyan' : 'text-slate-500'} />
          <div>
            <h3 className="text-sm font-semibold text-white">Agent Mode</h3>
            <p className="text-xs text-slate-500">AI autonomous trading</p>
          </div>
        </div>

        {}
        <button
          onClick={() => handleToggle(!agentMode)}
          disabled={loading}
          className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none ${
            agentMode ? 'bg-cyan' : 'bg-slate-700'
          } disabled:opacity-50`}
        >
          <span
            className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
              agentMode ? 'translate-x-6' : 'translate-x-1'
            }`}
          />
        </button>
      </div>

      {agentMode ? (
        <>
          <div className="text-xs text-cyan bg-cyan/5 border border-cyan/10 rounded-lg px-3 py-2 mb-4">
            Agent is actively trading. Predictions update every 5s.
          </div>

          {predictions.length === 0 ? (
            <div className="text-slate-500 text-xs text-center py-4">Loading predictions...</div>
          ) : (
            <div className="space-y-2">
              {predictions.map(pred => {
                const style = DECISION_STYLES[pred.decision] ?? DECISION_STYLES.HOLD
                const Icon = style.icon
                return (
                  <div
                    key={pred.symbol}
                    className={`flex items-start gap-3 p-3 rounded-xl border ${style.bg}`}
                  >
                    <div className="shrink-0 mt-0.5">
                      <Icon size={14} className={style.text} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-bold text-white">{pred.symbol}</span>
                        <span className={`text-xs font-bold px-2 py-0.5 rounded-full border ${style.bg} ${style.text}`}>
                          {pred.decision}
                        </span>
                      </div>
                      <div className="flex items-center gap-3 text-xs text-slate-400 mb-1">
                        <span>Price: <span className="text-white font-mono">${pred.current_price.toLocaleString()}</span></span>
                        <span>Predicted: <span className={`font-mono ${pred.predicted_change_pct >= 0 ? 'text-green' : 'text-red-400'}`}>
                          {pred.predicted_change_pct >= 0 ? '+' : ''}{pred.predicted_change_pct.toFixed(3)}%
                        </span></span>
                      </div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs text-slate-500">Confidence:</span>
                        <div className="flex-1 h-1 bg-border rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full bg-cyan"
                            style={{ width: `${pred.confidence * 100}%` }}
                          />
                        </div>
                        <span className="text-xs font-mono text-slate-400">{(pred.confidence * 100).toFixed(0)}%</span>
                      </div>
                      <p className="text-xs text-slate-500 truncate">{pred.reasoning}</p>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </>
      ) : (
        <div className="text-center py-6 space-y-2">
          <div className="text-slate-500 text-sm">Agent mode is OFF</div>
          <div className="text-slate-600 text-xs">Toggle ON to let the AI agent trade autonomously</div>
          <div className="text-slate-600 text-xs">You can still watch the market and trade manually</div>
        </div>
      )}
    </div>
  )
}
