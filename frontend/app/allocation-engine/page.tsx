"use client"

import Link from "next/link"
import { SectionHeader } from "@/components/iris/section-header"
import { MetricCard } from "@/components/iris/metric-card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import {
  Layers,
  Activity,
  TrendingUp,
  ArrowRight,
  Settings,
  Zap,
  Shield,
  BarChart3,
  RefreshCw,
} from "lucide-react"

const agentWeights = [
  { id: "alpha-wave", name: "AlphaWave", weight: 18.5, prevWeight: 17.2, change: 1.3 },
  { id: "neural-arb", name: "NeuralArb", weight: 14.2, prevWeight: 15.8, change: -1.6 },
  { id: "quant-sigma", name: "QuantSigma", weight: 12.8, prevWeight: 11.5, change: 1.3 },
  { id: "voltex-ai", name: "VoltexAI", weight: 11.5, prevWeight: 13.2, change: -1.7 },
  { id: "delta-hedge", name: "DeltaHedge", weight: 10.2, prevWeight: 9.8, change: 0.4 },
  { id: "omega-flow", name: "OmegaFlow", weight: 8.4, prevWeight: 8.1, change: 0.3 },
  { id: "stable-yield", name: "StableYield", weight: 7.8, prevWeight: 7.6, change: 0.2 },
  { id: "flux-arb", name: "FluxArb", weight: 6.2, prevWeight: 6.8, change: -0.6 },
  { id: "others", name: "Others (39)", weight: 10.4, prevWeight: 10.0, change: 0.4 },
]

const flowSteps = [
  { label: "Investors", icon: "👤" },
  { label: "Capital Vault", icon: "🔒" },
  { label: "Allocation Engine", icon: "⚙️" },
  { label: "AI Agents", icon: "🤖" },
  { label: "DEX Markets", icon: "📈" },
]

export default function AllocationEnginePage() {
  return (
    <div className="min-h-screen bg-transparent">
      {/* Header */}
      <div className="border-b border-border/30 bg-muted/10">
        <div className="max-w-[1800px] mx-auto px-4 md:px-6 py-8">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div>
              <h1 className="text-2xl md:text-3xl font-bold text-foreground mb-2">
                Allocation Engine
              </h1>
              <p className="text-muted-foreground">
                Dynamic capital rotation with regret-aware weight adjustments
              </p>
            </div>
            <div className="flex items-center gap-3">
              <Badge variant="outline" className="text-accent border-accent/30">
                <RefreshCw className="w-3 h-3 mr-1 animate-spin" />
                Live Reweighting
              </Badge>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-[1800px] mx-auto px-4 md:px-6 py-8">
        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <MetricCard
            title="Diversification Score"
            value="0.84"
            icon={Layers}
            variant="cyan"
          />
          <MetricCard
            title="HHI Concentration"
            value="0.084"
            icon={BarChart3}
          />
          <MetricCard
            title="Learning Rate (η)"
            value="0.15"
            icon={Settings}
            variant="emerald"
          />
          <MetricCard
            title="Regret Bound"
            value="0.023"
            icon={Activity}
          />
        </div>

        {/* Capital Flow Diagram */}
        <div className="glass rounded-xl p-6 border border-border/30 mb-8">
          <h3 className="font-semibold text-foreground mb-6">Capital Flow Architecture</h3>
          <div className="flex flex-wrap items-center justify-center gap-4">
            {flowSteps.map((step, i) => (
              <div key={step.label} className="flex items-center gap-4">
                <div className="flex flex-col items-center">
                  <div className="w-16 h-16 rounded-xl bg-primary/10 border border-primary/30 flex items-center justify-center text-2xl mb-2">
                    {step.icon}
                  </div>
                  <span className="text-sm text-foreground font-medium">{step.label}</span>
                </div>
                {i < flowSteps.length - 1 && (
                  <ArrowRight className="w-6 h-6 text-primary/50" />
                )}
              </div>
            ))}
          </div>
          <p className="text-sm text-muted-foreground text-center mt-6">
            Capital flows from investors through the vault, gets allocated by the engine to agents, 
            deployed on DEX markets, and performance feedback triggers reweighting.
          </p>
        </div>

        <div className="grid lg:grid-cols-2 gap-6 mb-8">
          {/* Current Weights */}
          <div className="glass rounded-xl p-6 border border-border/30">
            <div className="flex items-center justify-between mb-6">
              <h3 className="font-semibold text-foreground">Current Capital Weights</h3>
              <Badge variant="outline" className="text-muted-foreground">
                Last update: 2h ago
              </Badge>
            </div>

            <div className="space-y-3">
              {agentWeights.map((agent) => (
                <Link
                  key={agent.id}
                  href={agent.id === "others" ? "/agents" : `/agents/${agent.id}`}
                  className="block"
                >
                  <div className="flex items-center gap-4 p-3 rounded-lg hover:bg-muted/30 transition-colors">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm font-medium text-foreground truncate">
                          {agent.name}
                        </span>
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-sm text-foreground">{agent.weight.toFixed(1)}%</span>
                          <span className={`text-xs font-mono ${agent.change >= 0 ? "text-accent" : "text-destructive"}`}>
                            {agent.change >= 0 ? "+" : ""}{agent.change.toFixed(1)}%
                          </span>
                        </div>
                      </div>
                      <Progress value={agent.weight} className="h-2" />
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          </div>

          {/* Engine Parameters */}
          <div className="glass rounded-xl p-6 border border-border/30">
            <div className="flex items-center justify-between mb-6">
              <h3 className="font-semibold text-foreground">Engine Parameters</h3>
              <Button variant="outline" size="sm" asChild>
                <Link href="/governance">
                  <Settings className="w-4 h-4 mr-2" />
                  Governance
                </Link>
              </Button>
            </div>

            <div className="space-y-4">
              {[
                { label: "Learning Rate (η)", value: "0.15", desc: "Weight update speed" },
                { label: "Max Single Allocation", value: "25%", desc: "Per-agent cap" },
                { label: "Min Allocation", value: "1%", desc: "Minimum threshold" },
                { label: "Rebalance Frequency", value: "6h", desc: "Update interval" },
                { label: "Lookback Window", value: "30d", desc: "Performance period" },
                { label: "Risk Adjustment", value: "Sharpe-weighted", desc: "Scoring method" },
              ].map((param) => (
                <div key={param.label} className="flex items-center justify-between py-3 border-b border-border/30 last:border-0">
                  <div>
                    <span className="text-sm text-foreground">{param.label}</span>
                    <p className="text-xs text-muted-foreground">{param.desc}</p>
                  </div>
                  <Badge variant="secondary" className="font-mono">
                    {param.value}
                  </Badge>
                </div>
              ))}
            </div>

            <div className="mt-6 p-4 rounded-lg bg-primary/5 border border-primary/20">
              <div className="flex items-center gap-2 mb-2">
                <Shield className="w-4 h-4 text-primary" />
                <span className="text-sm font-medium text-foreground">Governance Controlled</span>
              </div>
              <p className="text-xs text-muted-foreground">
                All engine parameters can be adjusted through DAO governance proposals. 
                Changes require quorum approval.
              </p>
            </div>
          </div>
        </div>

        {/* Weight Update Algorithm */}
        <div className="glass rounded-xl p-6 border border-border/30 mb-8">
          <h3 className="font-semibold text-foreground mb-4">Multiplicative Weights Algorithm</h3>
          <p className="text-muted-foreground mb-6">
            The allocation engine uses a regret-aware multiplicative weights update algorithm. 
            Agents that perform well receive increased capital allocation, while underperformers 
            see their weights reduced. The learning rate η controls adaptation speed.
          </p>

          <div className="p-4 rounded-lg bg-muted/30 border border-border/30 font-mono text-sm">
            <div className="text-primary mb-2">// Weight Update Rule</div>
            <div className="text-foreground">
              w<sub>t+1</sub>(i) = w<sub>t</sub>(i) × exp(η × r<sub>t</sub>(i)) / Z<sub>t</sub>
            </div>
            <div className="text-muted-foreground mt-2 text-xs">
              where r<sub>t</sub>(i) is the risk-adjusted return and Z<sub>t</sub> is the normalization factor
            </div>
          </div>

          <div className="grid md:grid-cols-3 gap-4 mt-6">
            <div className="p-4 rounded-lg bg-accent/5 border border-accent/20">
              <Zap className="w-5 h-5 text-accent mb-2" />
              <h4 className="text-sm font-medium text-foreground mb-1">Performance Driven</h4>
              <p className="text-xs text-muted-foreground">
                Allocation responds to real returns, not predictions
              </p>
            </div>
            <div className="p-4 rounded-lg bg-primary/5 border border-primary/20">
              <Activity className="w-5 h-5 text-primary mb-2" />
              <h4 className="text-sm font-medium text-foreground mb-1">Risk Adjusted</h4>
              <p className="text-xs text-muted-foreground">
                Sharpe ratio weighting penalizes volatility
              </p>
            </div>
            <div className="p-4 rounded-lg bg-chart-3/5 border border-chart-3/20">
              <Shield className="w-5 h-5 text-chart-3 mb-2" />
              <h4 className="text-sm font-medium text-foreground mb-1">Bounded Regret</h4>
              <p className="text-xs text-muted-foreground">
                Theoretical guarantees on worst-case performance
              </p>
            </div>
          </div>
        </div>

        {/* Recent Rebalances */}
        <div className="glass rounded-xl p-6 border border-border/30">
          <h3 className="font-semibold text-foreground mb-6">Recent Rebalances</h3>
          <div className="space-y-3">
            {[
              { time: "2h ago", agents: 12, totalMoved: "2.4%", topGainer: "AlphaWave (+1.3%)", topLoser: "VoltexAI (-1.7%)" },
              { time: "8h ago", agents: 8, totalMoved: "1.8%", topGainer: "QuantSigma (+0.9%)", topLoser: "NeuralArb (-1.2%)" },
              { time: "14h ago", agents: 15, totalMoved: "3.2%", topGainer: "NeuralArb (+2.1%)", topLoser: "FluxArb (-1.8%)" },
            ].map((rebalance, i) => (
              <div key={i} className="p-4 rounded-lg bg-muted/30 border border-border/30">
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2">
                  <div className="flex items-center gap-4">
                    <Badge variant="outline" className="text-muted-foreground">{rebalance.time}</Badge>
                    <span className="text-sm text-foreground">{rebalance.agents} agents adjusted</span>
                    <span className="text-sm text-muted-foreground">Total moved: {rebalance.totalMoved}</span>
                  </div>
                  <div className="flex items-center gap-4 text-sm">
                    <span className="text-accent">{rebalance.topGainer}</span>
                    <span className="text-destructive">{rebalance.topLoser}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
