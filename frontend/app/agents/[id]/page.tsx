"use client"

import { use, useState } from "react"
import Link from "next/link"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { MetricCard } from "@/components/dacap/metric-card"
import {
  ArrowLeft,
  TrendingUp,
  TrendingDown,
  Activity,
  Shield,
  Zap,
  AlertTriangle,
  Play,
  Pause,
  DollarSign,
  Target,
  Loader2,
} from "lucide-react"
import { useAgent } from "@/hooks/use-agents"
import { useTradingFeed } from "@/hooks/use-trading-feed"
import { agentsApi } from "@/lib/api"

const riskColors: Record<string, string> = {
  Conservative: "bg-chart-3/20 text-chart-3 border-chart-3/30",
  Balanced: "bg-primary/20 text-primary border-primary/30",
  Aggressive: "bg-destructive/20 text-destructive border-destructive/30",
}

export default function AgentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const { agent, loading, refetch } = useAgent(id)
  const { events } = useTradingFeed()
  const [actionLoading, setActionLoading] = useState(false)

  // Filter trade events for this agent
  const agentTrades = events
    .filter((e) => agent?.address && e.agent.toLowerCase() === agent.address.toLowerCase())
    .slice(0, 10)

  const handleToggleTrading = async () => {
    if (!agent) return
    setActionLoading(true)
    try {
      if (agent.status === "active") {
        await agentsApi.stopTrading(agent.id)
      } else {
        await agentsApi.startTrading(agent.id)
      }
      refetch()
    } catch (e) {
      console.error("Trading toggle failed", e)
    } finally {
      setActionLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-10 h-10 animate-spin text-primary" />
      </div>
    )
  }

  if (!agent) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4">
        <p className="text-muted-foreground">Agent not found.</p>
        <Button asChild variant="outline">
          <Link href="/agents">Back to Agents</Link>
        </Button>
      </div>
    )
  }

  const isActive = agent.status === "active"
  const riskColor = riskColors[agent.risk] ?? riskColors["Balanced"]

  return (
    <div className="min-h-screen bg-transparent">
      {/* Header */}
      <div className="border-b border-border/30 bg-muted/10">
        <div className="max-w-[1800px] mx-auto px-4 md:px-6 py-8">
          <Link
            href="/agents"
            className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground mb-4"
          >
            <ArrowLeft className="w-4 h-4 mr-1" />
            Back to Agents
          </Link>

          <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-6">
            <div className="flex items-start gap-4">
              <div className="w-16 h-16 rounded-xl bg-primary/10 flex items-center justify-center">
                <Zap className="w-8 h-8 text-primary" />
              </div>
              <div>
                <div className="flex items-center gap-3 mb-2">
                  <h1 className="text-2xl md:text-3xl font-bold text-foreground">{agent.name}</h1>
                  {isActive && (
                    <span className="w-3 h-3 rounded-full bg-accent animate-pulse" />
                  )}
                </div>
                <p className="text-muted-foreground mb-3">{agent.strategy}</p>
                <div className="flex flex-wrap gap-2">
                  <Badge variant="outline" className={riskColor}>
                    {agent.risk}
                  </Badge>
                  <Badge variant="outline" className="text-muted-foreground">
                    Score: {agent.score}
                  </Badge>
                </div>
              </div>
            </div>

            <div className="flex gap-3">
              <Button variant="outline">
                <DollarSign className="w-4 h-4 mr-2" />
                Delegate Capital
              </Button>
              <Button
                disabled={actionLoading}
                className={isActive ? "bg-destructive hover:bg-destructive/90" : "glow-cyan"}
                onClick={handleToggleTrading}
              >
                {actionLoading ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : isActive ? (
                  <Pause className="w-4 h-4 mr-2" />
                ) : (
                  <Play className="w-4 h-4 mr-2" />
                )}
                {isActive ? "Stop AI" : "Start AI"}
              </Button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-[1800px] mx-auto px-4 md:px-6 py-8">
        {/* Description */}
        <div className="glass rounded-xl p-6 border border-border/30 mb-8">
          <h3 className="font-semibold text-foreground mb-3">Strategy Description</h3>
          <p className="text-muted-foreground text-sm leading-relaxed">{agent.description}</p>
          {agent.model && (
            <div className="mt-4 pt-4 border-t border-border/30 flex items-center gap-4">
              <div>
                <span className="text-xs text-muted-foreground">Model Family</span>
                <p className="font-mono text-sm text-foreground">{agent.model}</p>
              </div>
            </div>
          )}
        </div>

        {/* Score Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <MetricCard
            title="Trust Score"
            value={`${agent.trust_score ?? agent.score}/100`}
            icon={<Shield className="w-4 h-4" />}
            variant="cyan"
          />
          <MetricCard
            title="Confidence"
            value={`${Math.round((agent.confidence_score ?? 0.5) * 100)}/100`}
            icon={<Target className="w-4 h-4" />}
            variant="emerald"
          />
          <MetricCard
            title="Anomaly Score"
            value={`${Math.round((agent.anomaly_score ?? 0.1) * 100)}/100`}
            icon={<AlertTriangle className="w-4 h-4" />}
            variant={(agent.anomaly_score ?? 0) > 0.5 ? "amber" : "default"}
          />
          <MetricCard
            title="Overall Score"
            value={`${agent.score}/100`}
            icon={<Activity className="w-4 h-4" />}
            variant="blue"
          />
        </div>

        <div className="grid lg:grid-cols-3 gap-6 mb-8">
          {/* Performance Metrics */}
          <div className="glass rounded-xl p-6 border border-border/30">
            <h3 className="font-semibold text-foreground mb-6">Performance Metrics</h3>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Sharpe Ratio</span>
                <span className="font-mono font-semibold text-foreground">
                  {agent.sharpe.toFixed(2)}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Volatility</span>
                <span className="font-mono font-semibold text-foreground">
                  {agent.volatility.toFixed(2)}%
                </span>
              </div>
              <div className="pt-4 border-t border-border/30">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Total PnL</span>
                  <span
                    className={`font-mono font-semibold flex items-center gap-1 ${
                      agent.pnl >= 0 ? "text-accent" : "text-destructive"
                    }`}
                  >
                    {agent.pnl >= 0 ? (
                      <TrendingUp className="w-4 h-4" />
                    ) : (
                      <TrendingDown className="w-4 h-4" />
                    )}
                    ${agent.pnl.toLocaleString()}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Risk Metrics */}
          <div className="glass rounded-xl p-6 border border-border/30">
            <h3 className="font-semibold text-foreground mb-6">Risk Metrics</h3>
            <div className="space-y-4">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-muted-foreground">Drawdown</span>
                  <span className="font-mono font-semibold text-destructive">
                    -{Math.abs(agent.drawdown).toFixed(2)}%
                  </span>
                </div>
                <Progress value={Math.abs(agent.drawdown) * 5} className="h-2" />
              </div>
              <div className="pt-4 border-t border-border/30">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Capital Allocated</span>
                  <span className="font-mono font-semibold text-foreground">
                    {agent.allocation.toFixed(1)}%
                  </span>
                </div>
                <div className="flex items-center justify-between mt-2">
                  <span className="text-muted-foreground">Stake</span>
                  <span className="font-mono font-semibold text-foreground">
                    ${agent.stake.toLocaleString()}
                  </span>
                </div>
              </div>
            </div>

            {Math.abs(agent.drawdown) > 7 && (
              <div className="mt-4 p-3 rounded-lg bg-destructive/10 border border-destructive/30">
                <div className="flex items-center gap-2 text-destructive text-sm">
                  <AlertTriangle className="w-4 h-4" />
                  Slashing Watch — Approaching drawdown limit
                </div>
              </div>
            )}
          </div>

          {/* Live Trade Feed */}
          <div className="glass rounded-xl p-6 border border-border/30">
            <h3 className="font-semibold text-foreground mb-6">Live Trade Feed</h3>
            {agentTrades.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                {isActive ? "Waiting for trades…" : "Start the agent to see live trades."}
              </p>
            ) : (
              <div className="space-y-2">
                {agentTrades.map((trade, i) => (
                  <div key={i} className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <Badge
                        variant="outline"
                        className={
                          trade.type === "swap"
                            ? "text-accent border-accent/30"
                            : "text-destructive border-destructive/30"
                        }
                      >
                        {trade.type.toUpperCase()}
                      </Badge>
                      <span className="text-foreground">{trade.token}</span>
                    </div>
                    <span className="text-xs text-muted-foreground">
                      {new Date(trade.timestamp * 1000).toLocaleTimeString()}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Trading Status */}
        <div className="glass rounded-xl p-6 border border-border/30">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-foreground">Trading Session Status</h3>
            <Badge
              variant="outline"
              className={isActive ? "text-accent border-accent/30" : "text-muted-foreground"}
            >
              {isActive ? "Active" : "Inactive"}
            </Badge>
          </div>
          <div className="grid md:grid-cols-3 gap-4">
            <div>
              <span className="text-xs text-muted-foreground">Wallet Address</span>
              <p className="font-mono text-xs text-foreground truncate">{agent.address ?? "—"}</p>
            </div>
            <div>
              <span className="text-xs text-muted-foreground">Agent ID</span>
              <p className="font-mono text-foreground">{agent.id}</p>
            </div>
            <div>
              <span className="text-xs text-muted-foreground">Status</span>
              <p className="font-mono text-foreground capitalize">{agent.status}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
