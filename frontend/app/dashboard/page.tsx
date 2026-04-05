"use client"

import Link from "next/link"
import { MetricCard } from "@/components/dacap/metric-card"
import { AgentCard, type AgentData } from "@/components/dacap/agent-card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Activity,
  TrendingUp,
  Shield,
  Brain,
  Layers,
  BarChart3,
  Vote,
  AlertTriangle,
  ArrowRight,
  Zap,
  Globe2,
  Clock,
  Loader2,
  Wifi,
  WifiOff,
} from "lucide-react"
import { useAgents } from "@/hooks/use-agents"
import { useLivePrices } from "@/hooks/use-live-prices"
import { useTradingFeed } from "@/hooks/use-trading-feed"
import type { Agent } from "@/lib/api"

const quickLinks = [
  { icon: Brain, label: "Agents", href: "/agents", color: "text-primary" },
  { icon: Shield, label: "Risk Pools", href: "/risk-pools", color: "text-chart-3" },
  { icon: Layers, label: "Allocation", href: "/allocation-engine", color: "text-accent" },
  { icon: BarChart3, label: "Analytics", href: "/analytics", color: "text-chart-4" },
  { icon: Vote, label: "Governance", href: "/governance", color: "text-chart-5" },
  { icon: Globe2, label: "World", href: "/world-monitor", color: "text-destructive" },
]

function agentToCard(a: Agent): AgentData {
  return {
    id: a.id,
    name: a.name,
    strategy: a.strategy,
    riskLevel: a.risk as AgentData["riskLevel"],
    score: a.score,
    sharpe: a.sharpe,
    pnl: a.pnl,
    pnlPercent: a.pnl / 10000,
    drawdown: Math.abs(a.drawdown),
    allocation: a.allocation,
    stake: a.stake,
    isActive: a.status === "active",
    badges: [],
  }
}

export default function DashboardPage() {
  const { agents, loading: agentsLoading } = useAgents()
  const { prices, connected: pricesConnected } = useLivePrices()
  const { events, connected: tradingConnected } = useTradingFeed()

  const topAgents = [...agents]
    .sort((a, b) => b.sharpe - a.sharpe)
    .slice(0, 3)
    .map(agentToCard)

  const activeAgents = agents.filter((a) => a.status === "active")
  const totalPnL = agents.reduce((s, a) => s + a.pnl, 0)
  const avgSharpe = agents.length
    ? agents.reduce((s, a) => s + a.sharpe, 0) / agents.length
    : 0

  // Pool breakdown from live agents
  const poolTvl = {
    Conservative: agents
      .filter((a) => a.risk === "Conservative")
      .reduce((s, a) => s + a.stake, 0),
    Balanced: agents.filter((a) => a.risk === "Balanced").reduce((s, a) => s + a.stake, 0),
    Aggressive: agents.filter((a) => a.risk === "Aggressive").reduce((s, a) => s + a.stake, 0),
  }
  const maxTvl = Math.max(...Object.values(poolTvl), 1)

  const recentTrades = events.slice(0, 3)

  return (
    <div className="min-h-screen bg-transparent">
      {/* Header */}
      <div className="border-b border-border/30 bg-muted/10">
        <div className="max-w-[1800px] mx-auto px-4 md:px-6 py-8">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div>
              <h1 className="text-2xl md:text-3xl font-bold text-foreground mb-2">
                Autonomous Capital Brain
              </h1>
              <p className="text-muted-foreground">
                Real-time protocol monitoring and system overview
              </p>
            </div>
            <div className="flex items-center gap-3">
              <Badge variant="outline" className="text-accent border-accent/30 bg-accent/5">
                <span className="w-2 h-2 rounded-full bg-accent animate-pulse mr-2" />
                System Online
              </Badge>
              <Badge
                variant="outline"
                className={
                  pricesConnected ? "text-accent border-accent/30" : "text-muted-foreground"
                }
              >
                {pricesConnected ? (
                  <Wifi className="w-3 h-3 mr-1" />
                ) : (
                  <WifiOff className="w-3 h-3 mr-1" />
                )}
                Prices {pricesConnected ? "Live" : "Offline"}
              </Badge>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-[1800px] mx-auto px-4 md:px-6 py-8">
        {/* KPI Row */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mb-8">
          <MetricCard
            title="Total PnL"
            value={`$${totalPnL.toLocaleString()}`}
            change={avgSharpe}
            changeLabel="Sharpe"
            icon={<TrendingUp className="w-4 h-4" />}
            variant="cyan"
          />
          <MetricCard
            title="Active Agents"
            value={agentsLoading ? "…" : String(activeAgents.length)}
            icon={<Brain className="w-4 h-4" />}
          />
          <MetricCard
            title="WBTC"
            value={prices["WBTC"] ? `$${prices["WBTC"].price.toFixed(0)}` : "…"}
            change={prices["WBTC"]?.change_pct}
            changeLabel="24h"
            icon={<Activity className="w-4 h-4" />}
            variant="emerald"
          />
          <MetricCard
            title="LINK"
            value={prices["LINK"] ? `$${prices["LINK"].price.toFixed(2)}` : "…"}
            change={prices["LINK"]?.change_pct}
            changeLabel="24h"
            icon={<Activity className="w-4 h-4" />}
            variant="blue"
          />
          <MetricCard
            title="UNI"
            value={prices["UNI"] ? `$${prices["UNI"].price.toFixed(2)}` : "…"}
            change={prices["UNI"]?.change_pct}
            changeLabel="24h"
            icon={<Activity className="w-4 h-4" />}
          />
          <MetricCard
            title="Total Agents"
            value={agentsLoading ? "…" : String(agents.length)}
            icon={<Layers className="w-4 h-4" />}
          />
        </div>

        <div className="grid lg:grid-cols-3 gap-6 mb-8">
          {/* Live Price Feed */}
          <div className="glass rounded-xl p-6 border border-border/30">
            <div className="flex items-center justify-between mb-6">
              <h3 className="font-semibold text-foreground">Live Prices</h3>
              <Badge
                variant="outline"
                className={
                  pricesConnected ? "text-accent border-accent/30" : "text-muted-foreground"
                }
              >
                {pricesConnected ? "Live" : "Connecting…"}
              </Badge>
            </div>
            <div className="space-y-4">
              {["WBTC", "USDC", "LINK", "UNI"].map((sym) => {
                const p = prices[sym]
                return (
                  <div key={sym} className="flex items-center justify-between">
                    <span className="text-muted-foreground font-mono">{sym}</span>
                    <div className="text-right">
                      {p ? (
                        <>
                          <p className="font-mono font-semibold text-foreground">
                            ${sym === "WBTC" ? p.price.toFixed(0) : p.price.toFixed(4)}
                          </p>
                          <p
                            className={`text-xs font-mono ${
                              p.change_pct >= 0 ? "text-accent" : "text-destructive"
                            }`}
                          >
                            {p.change_pct >= 0 ? "+" : ""}
                            {p.change_pct.toFixed(3)}%
                          </p>
                        </>
                      ) : (
                        <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Risk Pool Summary */}
          <div className="glass rounded-xl p-6 border border-border/30">
            <div className="flex items-center justify-between mb-6">
              <h3 className="font-semibold text-foreground">Risk Pool Summary</h3>
              <Button variant="ghost" size="sm" asChild>
                <Link href="/risk-pools">
                  View All <ArrowRight className="w-3 h-3 ml-1" />
                </Link>
              </Button>
            </div>
            <div className="space-y-4">
              {[
                { name: "Conservative", color: "bg-chart-3" },
                { name: "Balanced", color: "bg-primary" },
                { name: "Aggressive", color: "bg-destructive" },
              ].map((pool) => {
                const tvl = poolTvl[pool.name as keyof typeof poolTvl]
                return (
                  <div key={pool.name}>
                    <div className="flex items-center justify-between text-sm mb-1">
                      <span className="text-foreground">{pool.name}</span>
                      <span className="font-mono text-muted-foreground">
                        ${(tvl / 1000).toFixed(0)}K stake
                      </span>
                    </div>
                    <div className="h-2 rounded-full bg-muted overflow-hidden">
                      <div
                        className={`h-full rounded-full ${pool.color}`}
                        style={{ width: `${(tvl / maxTvl) * 100}%` }}
                      />
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Live Trading Feed */}
          <div className="glass rounded-xl p-6 border border-border/30">
            <div className="flex items-center justify-between mb-6">
              <h3 className="font-semibold text-foreground">Live Trading</h3>
              <Badge
                variant="outline"
                className={
                  tradingConnected ? "text-accent border-accent/30" : "text-muted-foreground"
                }
              >
                {tradingConnected ? "Live" : "Connecting…"}
              </Badge>
            </div>
            {recentTrades.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No recent trades. Start an agent to see live trades.
              </p>
            ) : (
              <div className="space-y-3">
                {recentTrades.map((trade, i) => (
                  <div key={i} className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <Badge variant="outline" className="text-accent border-accent/30 text-xs">
                        {trade.type.toUpperCase()}
                      </Badge>
                      <span className="text-foreground font-mono">{trade.token}</span>
                    </div>
                    <div className="text-right">
                      <p className="font-mono text-xs text-muted-foreground">
                        {(parseInt(trade.amountIn) / 1e18).toFixed(4)} ETH
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {new Date(trade.timestamp * 1000).toLocaleTimeString()}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Agent Leaderboard & Alerts */}
        <div className="grid lg:grid-cols-2 gap-6 mb-8">
          {/* Agent Leaderboard */}
          <div className="glass rounded-xl p-6 border border-border/30">
            <div className="flex items-center justify-between mb-6">
              <h3 className="font-semibold text-foreground">Top Performing Agents</h3>
              <Button variant="ghost" size="sm" asChild>
                <Link href="/agents">
                  View All <ArrowRight className="w-3 h-3 ml-1" />
                </Link>
              </Button>
            </div>
            {agentsLoading ? (
              <div className="flex justify-center py-8">
                <Loader2 className="w-6 h-6 animate-spin text-primary" />
              </div>
            ) : (
              <div className="space-y-3">
                {topAgents.map((agent) => (
                  <AgentCard key={agent.id} agent={agent} variant="row" />
                ))}
                {topAgents.length === 0 && (
                  <p className="text-sm text-muted-foreground">No agents available.</p>
                )}
              </div>
            )}
          </div>

          {/* System Alerts based on live agent data */}
          <div className="glass rounded-xl p-6 border border-border/30">
            <div className="flex items-center justify-between mb-6">
              <h3 className="font-semibold text-foreground">System Alerts</h3>
              <Badge variant="outline" className="text-muted-foreground">
                {agents.filter((a) => Math.abs(a.drawdown) > 7).length} Active
              </Badge>
            </div>
            <div className="space-y-3">
              {agents
                .filter((a) => Math.abs(a.drawdown) > 7)
                .slice(0, 3)
                .map((a) => (
                  <div
                    key={a.id}
                    className="p-4 rounded-lg border bg-destructive/5 border-destructive/30"
                  >
                    <div className="flex items-start gap-3">
                      <AlertTriangle className="w-4 h-4 mt-0.5 text-destructive" />
                      <div className="flex-1">
                        <p className="text-sm text-foreground">
                          {a.name} approaching drawdown limit ({a.drawdown.toFixed(1)}%)
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              {agents.filter((a) => Math.abs(a.drawdown) > 7).length === 0 && (
                <p className="text-sm text-muted-foreground">
                  No active alerts. All agents within risk thresholds.
                </p>
              )}
            </div>

            <div className="mt-4 pt-4 border-t border-border/30">
              <div className="glass-accent rounded-lg p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Zap className="w-4 h-4 text-primary" />
                  <span className="text-sm font-medium text-foreground">Intelligence Loop</span>
                </div>
                <p className="text-xs text-muted-foreground">
                  {activeAgents.length} agents active. Avg Sharpe: {avgSharpe.toFixed(2)}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Quick Navigation */}
        <div className="glass rounded-xl p-6 border border-border/30">
          <h3 className="font-semibold text-foreground mb-6">Quick Navigation</h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-4">
            {quickLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="glass rounded-lg p-4 text-center hover:bg-muted/30 transition-colors border border-border/30 hover:border-primary/30"
              >
                <link.icon className={`w-6 h-6 mx-auto mb-2 ${link.color}`} />
                <span className="text-sm text-foreground">{link.label}</span>
              </Link>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
