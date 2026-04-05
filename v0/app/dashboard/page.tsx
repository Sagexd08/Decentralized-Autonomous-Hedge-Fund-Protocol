"use client"

import Link from "next/link"
import { MetricCard } from "@/components/dacap/metric-card"
import { SectionHeader } from "@/components/dacap/section-header"
import { AgentCard, type AgentData } from "@/components/dacap/agent-card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
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
} from "lucide-react"

const topAgents: AgentData[] = [
  {
    id: "alpha-wave",
    name: "AlphaWave",
    strategy: "Momentum + Mean Reversion",
    riskLevel: "Balanced",
    score: 94,
    sharpe: 2.34,
    pnl: 127450,
    pnlPercent: 12.5,
    drawdown: 4.2,
    allocation: 18.5,
    stake: 250000,
    isActive: true,
    badges: ["Top Sharpe", "Ranked #1"],
  },
  {
    id: "neural-arb",
    name: "NeuralArb",
    strategy: "Statistical Arbitrage",
    riskLevel: "Aggressive",
    score: 89,
    sharpe: 2.12,
    pnl: 98200,
    pnlPercent: 10.2,
    drawdown: 6.8,
    allocation: 14.2,
    stake: 180000,
    isActive: true,
    badges: ["Top PnL"],
  },
  {
    id: "quant-sigma",
    name: "QuantSigma",
    strategy: "Factor-based Allocation",
    riskLevel: "Conservative",
    score: 87,
    sharpe: 1.98,
    pnl: 72100,
    pnlPercent: 7.9,
    drawdown: 2.1,
    allocation: 12.8,
    stake: 200000,
    isActive: true,
    badges: ["Low Drawdown"],
  },
]

const quickLinks = [
  { icon: Brain, label: "Agents", href: "/agents", color: "text-primary" },
  { icon: Shield, label: "Risk Pools", href: "/risk-pools", color: "text-chart-3" },
  { icon: Layers, label: "Allocation", href: "/allocation-engine", color: "text-accent" },
  { icon: BarChart3, label: "Analytics", href: "/analytics", color: "text-chart-4" },
  { icon: Vote, label: "Governance", href: "/governance", color: "text-chart-5" },
  { icon: Globe2, label: "World", href: "/world-monitor", color: "text-destructive" },
]

const recentAlerts = [
  { type: "warning", message: "VoltexAI approaching drawdown limit (-8.2%)", time: "2m ago" },
  { type: "info", message: "New governance proposal: Increase eta to 0.18", time: "15m ago" },
  { type: "success", message: "AlphaWave achieved new Sharpe high (2.34)", time: "1h ago" },
]

export default function DashboardPage() {
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
              <Badge variant="outline" className="text-muted-foreground">
                <Clock className="w-3 h-3 mr-1" />
                Last sync: 2s ago
              </Badge>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-[1800px] mx-auto px-4 md:px-6 py-8">
        {/* KPI Row */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mb-8">
          <MetricCard
            title="Portfolio Value"
            value="$49.3M"
            change={3.24}
            changeLabel="24h"
            icon={<TrendingUp className="w-4 h-4" />}
            variant="cyan"
          />
          <MetricCard
            title="Unrealized PnL"
            value="+$2.87M"
            change={5.82}
            changeLabel="24h"
            icon={<Activity className="w-4 h-4" />}
            variant="emerald"
          />
          <MetricCard
            title="Active Agents"
            value="47"
            change={2}
            changeLabel="new"
            icon={<Brain className="w-4 h-4" />}
          />
          <MetricCard
            title="Risk Score"
            value="32/100"
            icon={<Shield className="w-4 h-4" />}
            variant="blue"
          />
          <MetricCard
            title="Protocol TVL"
            value="$127.4M"
            change={1.85}
            changeLabel="7d"
            icon={<Layers className="w-4 h-4" />}
          />
          <MetricCard
            title="Active Proposals"
            value="3"
            icon={<Vote className="w-4 h-4" />}
          />
        </div>

        <div className="grid lg:grid-cols-3 gap-6 mb-8">
          {/* Protocol Posture */}
          <div className="glass rounded-xl p-6 border border-border/30">
            <div className="flex items-center justify-between mb-6">
              <h3 className="font-semibold text-foreground">Protocol Posture</h3>
              <Badge variant="outline" className="text-accent border-accent/30">
                Risk-On
              </Badge>
            </div>

            <div className="space-y-4">
              <div>
                <div className="flex items-center justify-between text-sm mb-2">
                  <span className="text-muted-foreground">Market Regime</span>
                  <span className="font-mono text-foreground">Trending</span>
                </div>
                <div className="flex items-center justify-between text-sm mb-2">
                  <span className="text-muted-foreground">Volatility State</span>
                  <span className="font-mono text-foreground">Low</span>
                </div>
                <div className="flex items-center justify-between text-sm mb-2">
                  <span className="text-muted-foreground">Correlation Regime</span>
                  <span className="font-mono text-foreground">Decorrelated</span>
                </div>
              </div>

              <div className="pt-4 border-t border-border/30">
                <div className="text-xs text-muted-foreground mb-2">System Recommendation</div>
                <p className="text-sm text-foreground">
                  Maintain aggressive allocation to momentum strategies. Consider increasing eta for faster adaptation.
                </p>
              </div>
            </div>
          </div>

          {/* Risk Pool Summary */}
          <div className="glass rounded-xl p-6 border border-border/30">
            <div className="flex items-center justify-between mb-6">
              <h3 className="font-semibold text-foreground">Risk Pool Summary</h3>
              <Button variant="ghost" size="sm" asChild>
                <Link href="/risk-pools">
                  View All
                  <ArrowRight className="w-3 h-3 ml-1" />
                </Link>
              </Button>
            </div>

            <div className="space-y-4">
              {[
                { name: "Conservative", tvl: 12.4, cap: 15, color: "bg-chart-3" },
                { name: "Balanced", tvl: 28.7, cap: 32, color: "bg-primary" },
                { name: "Aggressive", tvl: 8.2, cap: 18, color: "bg-destructive" },
              ].map((pool) => (
                <div key={pool.name}>
                  <div className="flex items-center justify-between text-sm mb-1">
                    <span className="text-foreground">{pool.name}</span>
                    <span className="font-mono text-muted-foreground">
                      ${pool.tvl}M / ${pool.cap}M
                    </span>
                  </div>
                  <div className="h-2 rounded-full bg-muted overflow-hidden">
                    <div
                      className={`h-full rounded-full ${pool.color}`}
                      style={{ width: `${(pool.tvl / pool.cap) * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Allocation Distribution */}
          <div className="glass rounded-xl p-6 border border-border/30">
            <div className="flex items-center justify-between mb-6">
              <h3 className="font-semibold text-foreground">Allocation Distribution</h3>
              <Button variant="ghost" size="sm" asChild>
                <Link href="/allocation-engine">
                  Details
                  <ArrowRight className="w-3 h-3 ml-1" />
                </Link>
              </Button>
            </div>

            <div className="space-y-3">
              {[
                { name: "AlphaWave", pct: 18.5, color: "bg-primary" },
                { name: "NeuralArb", pct: 14.2, color: "bg-accent" },
                { name: "QuantSigma", pct: 12.8, color: "bg-chart-3" },
                { name: "VoltexAI", pct: 11.5, color: "bg-chart-4" },
                { name: "Others (43)", pct: 43.0, color: "bg-muted-foreground" },
              ].map((agent) => (
                <div key={agent.name} className="flex items-center gap-3">
                  <div className={`w-3 h-3 rounded-full ${agent.color}`} />
                  <span className="text-sm text-foreground flex-1">{agent.name}</span>
                  <span className="text-sm font-mono text-muted-foreground">{agent.pct}%</span>
                </div>
              ))}
            </div>

            <div className="mt-4 pt-4 border-t border-border/30">
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">HHI Score</span>
                <span className="font-mono text-foreground">0.084 (Well Diversified)</span>
              </div>
            </div>
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
                  View All
                  <ArrowRight className="w-3 h-3 ml-1" />
                </Link>
              </Button>
            </div>

            <div className="space-y-3">
              {topAgents.map((agent, i) => (
                <AgentCard key={agent.id} agent={agent} variant="row" />
              ))}
            </div>
          </div>

          {/* System Alerts */}
          <div className="glass rounded-xl p-6 border border-border/30">
            <div className="flex items-center justify-between mb-6">
              <h3 className="font-semibold text-foreground">System Alerts</h3>
              <Badge variant="outline" className="text-muted-foreground">
                3 Active
              </Badge>
            </div>

            <div className="space-y-3">
              {recentAlerts.map((alert, i) => (
                <div
                  key={i}
                  className={`p-4 rounded-lg border ${
                    alert.type === "warning"
                      ? "bg-destructive/5 border-destructive/30"
                      : alert.type === "success"
                      ? "bg-accent/5 border-accent/30"
                      : "bg-primary/5 border-primary/30"
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <AlertTriangle
                      className={`w-4 h-4 mt-0.5 ${
                        alert.type === "warning"
                          ? "text-destructive"
                          : alert.type === "success"
                          ? "text-accent"
                          : "text-primary"
                      }`}
                    />
                    <div className="flex-1">
                      <p className="text-sm text-foreground">{alert.message}</p>
                      <p className="text-xs text-muted-foreground mt-1">{alert.time}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-4 pt-4 border-t border-border/30">
              <div className="glass-accent rounded-lg p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Zap className="w-4 h-4 text-primary" />
                  <span className="text-sm font-medium text-foreground">Intelligence Loop</span>
                </div>
                <p className="text-xs text-muted-foreground">
                  Next reweighting cycle in 4h 23m. Current eta: 0.15
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
