"use client"

import { use } from "react"
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
  BarChart3,
  Target,
  Clock,
} from "lucide-react"

// Mock agent data
const agentData: Record<string, {
  id: string
  name: string
  strategy: string
  description: string
  riskLevel: "Conservative" | "Balanced" | "Aggressive"
  modelFamily: string
  score: number
  trustScore: number
  confidenceScore: number
  anomalyScore: number
  sharpe: number
  sortino: number
  calmar: number
  pnl: number
  pnlPercent: number
  drawdown: number
  maxDrawdown: number
  allocation: number
  stake: number
  isActive: boolean
  badges: string[]
  portfolio: { asset: string; weight: number }[]
  recentTrades: { time: string; action: string; asset: string; pnl: number }[]
}> = {
  "alpha-wave": {
    id: "alpha-wave",
    name: "AlphaWave",
    strategy: "Momentum + Mean Reversion",
    description: "Combines short-term momentum signals with mean reversion at key support/resistance levels. Uses adaptive position sizing based on volatility regime.",
    riskLevel: "Balanced",
    modelFamily: "Transformer-XL",
    score: 94,
    trustScore: 92,
    confidenceScore: 88,
    anomalyScore: 12,
    sharpe: 2.34,
    sortino: 3.12,
    calmar: 2.98,
    pnl: 127450,
    pnlPercent: 12.5,
    drawdown: 4.2,
    maxDrawdown: 8.5,
    allocation: 18.5,
    stake: 250000,
    isActive: true,
    badges: ["Top Sharpe", "Ranked #1"],
    portfolio: [
      { asset: "ETH", weight: 35 },
      { asset: "BTC", weight: 25 },
      { asset: "SOL", weight: 20 },
      { asset: "USDC", weight: 20 },
    ],
    recentTrades: [
      { time: "2m ago", action: "BUY", asset: "ETH", pnl: 1250 },
      { time: "15m ago", action: "SELL", asset: "SOL", pnl: 890 },
      { time: "1h ago", action: "BUY", asset: "BTC", pnl: -320 },
    ],
  },
  "neural-arb": {
    id: "neural-arb",
    name: "NeuralArb",
    strategy: "Statistical Arbitrage",
    description: "Identifies statistical mispricings across correlated asset pairs using neural network pattern recognition.",
    riskLevel: "Aggressive",
    modelFamily: "LSTM Ensemble",
    score: 89,
    trustScore: 85,
    confidenceScore: 82,
    anomalyScore: 18,
    sharpe: 2.12,
    sortino: 2.78,
    calmar: 2.45,
    pnl: 98200,
    pnlPercent: 10.2,
    drawdown: 6.8,
    maxDrawdown: 12.4,
    allocation: 14.2,
    stake: 180000,
    isActive: true,
    badges: ["Top PnL"],
    portfolio: [
      { asset: "ETH", weight: 40 },
      { asset: "BTC", weight: 30 },
      { asset: "ARB", weight: 20 },
      { asset: "USDC", weight: 10 },
    ],
    recentTrades: [
      { time: "5m ago", action: "BUY", asset: "ARB", pnl: 2100 },
      { time: "22m ago", action: "SELL", asset: "ETH", pnl: 1540 },
    ],
  },
}

export default function AgentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const agent = agentData[id] || agentData["alpha-wave"]

  const riskColors = {
    Conservative: "bg-chart-3/20 text-chart-3 border-chart-3/30",
    Balanced: "bg-primary/20 text-primary border-primary/30",
    Aggressive: "bg-destructive/20 text-destructive border-destructive/30",
  }

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
                  <h1 className="text-2xl md:text-3xl font-bold text-foreground">
                    {agent.name}
                  </h1>
                  {agent.isActive && (
                    <span className="w-3 h-3 rounded-full bg-accent animate-pulse" />
                  )}
                </div>
                <p className="text-muted-foreground mb-3">{agent.strategy}</p>
                <div className="flex flex-wrap gap-2">
                  <Badge variant="outline" className={riskColors[agent.riskLevel]}>
                    {agent.riskLevel}
                  </Badge>
                  {agent.badges.map((badge) => (
                    <Badge key={badge} variant="secondary" className="bg-primary/10 text-primary border-0">
                      {badge}
                    </Badge>
                  ))}
                </div>
              </div>
            </div>

            <div className="flex gap-3">
              <Button variant="outline">
                <DollarSign className="w-4 h-4 mr-2" />
                Delegate Capital
              </Button>
              <Button className={agent.isActive ? "bg-destructive hover:bg-destructive/90" : "glow-cyan"}>
                {agent.isActive ? (
                  <>
                    <Pause className="w-4 h-4 mr-2" />
                    Stop AI
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4 mr-2" />
                    Start AI
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-[1800px] mx-auto px-4 md:px-6 py-8">
        {/* Description */}
        <div className="glass rounded-xl p-6 border border-border/30 mb-8">
          <h3 className="font-semibold text-foreground mb-3">Strategy Description</h3>
          <p className="text-muted-foreground">{agent.description}</p>
          <div className="mt-4 pt-4 border-t border-border/30 flex items-center gap-4">
            <div>
              <span className="text-xs text-muted-foreground">Model Family</span>
              <p className="font-mono text-sm text-foreground">{agent.modelFamily}</p>
            </div>
          </div>
        </div>

        {/* Score Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <MetricCard
            title="Trust Score"
            value={`${agent.trustScore}/100`}
            icon={<Shield className="w-4 h-4" />}
            variant="cyan"
          />
          <MetricCard
            title="Confidence"
            value={`${agent.confidenceScore}/100`}
            icon={<Target className="w-4 h-4" />}
            variant="emerald"
          />
          <MetricCard
            title="Anomaly Score"
            value={`${agent.anomalyScore}/100`}
            icon={<AlertTriangle className="w-4 h-4" />}
            variant={agent.anomalyScore > 50 ? "amber" : "default"}
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
                <span className="font-mono font-semibold text-foreground">{agent.sharpe.toFixed(2)}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Sortino Ratio</span>
                <span className="font-mono font-semibold text-foreground">{agent.sortino.toFixed(2)}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Calmar Ratio</span>
                <span className="font-mono font-semibold text-foreground">{agent.calmar.toFixed(2)}</span>
              </div>
              <div className="pt-4 border-t border-border/30">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Total PnL</span>
                  <span className={`font-mono font-semibold flex items-center gap-1 ${agent.pnl >= 0 ? "text-accent" : "text-destructive"}`}>
                    {agent.pnl >= 0 ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
                    ${agent.pnl.toLocaleString()}
                  </span>
                </div>
                <div className="flex items-center justify-between mt-2">
                  <span className="text-muted-foreground">PnL %</span>
                  <span className={`font-mono font-semibold ${agent.pnlPercent >= 0 ? "text-accent" : "text-destructive"}`}>
                    {agent.pnlPercent >= 0 ? "+" : ""}{agent.pnlPercent.toFixed(2)}%
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
                  <span className="text-muted-foreground">Current Drawdown</span>
                  <span className="font-mono font-semibold text-destructive">-{agent.drawdown.toFixed(2)}%</span>
                </div>
                <Progress value={agent.drawdown * 5} className="h-2" />
              </div>
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-muted-foreground">Max Drawdown</span>
                  <span className="font-mono font-semibold text-destructive">-{agent.maxDrawdown.toFixed(2)}%</span>
                </div>
                <Progress value={agent.maxDrawdown * 5} className="h-2" />
              </div>
              <div className="pt-4 border-t border-border/30">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Capital Allocated</span>
                  <span className="font-mono font-semibold text-foreground">{agent.allocation.toFixed(1)}%</span>
                </div>
                <div className="flex items-center justify-between mt-2">
                  <span className="text-muted-foreground">Stake</span>
                  <span className="font-mono font-semibold text-foreground">${agent.stake.toLocaleString()}</span>
                </div>
              </div>
            </div>

            {agent.drawdown > 7 && (
              <div className="mt-4 p-3 rounded-lg bg-destructive/10 border border-destructive/30">
                <div className="flex items-center gap-2 text-destructive text-sm">
                  <AlertTriangle className="w-4 h-4" />
                  <span>Slashing Watch - Approaching drawdown limit</span>
                </div>
              </div>
            )}
          </div>

          {/* Portfolio Exposure */}
          <div className="glass rounded-xl p-6 border border-border/30">
            <h3 className="font-semibold text-foreground mb-6">Portfolio Exposure</h3>
            <div className="space-y-3">
              {agent.portfolio.map((position) => (
                <div key={position.asset}>
                  <div className="flex items-center justify-between text-sm mb-1">
                    <span className="text-foreground font-medium">{position.asset}</span>
                    <span className="font-mono text-muted-foreground">{position.weight}%</span>
                  </div>
                  <Progress value={position.weight} className="h-2" />
                </div>
              ))}
            </div>

            <div className="mt-6 pt-4 border-t border-border/30">
              <h4 className="text-sm font-medium text-muted-foreground mb-3">Recent Trades</h4>
              <div className="space-y-2">
                {agent.recentTrades.map((trade, i) => (
                  <div key={i} className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <Badge variant="outline" className={trade.action === "BUY" ? "text-accent border-accent/30" : "text-destructive border-destructive/30"}>
                        {trade.action}
                      </Badge>
                      <span className="text-foreground">{trade.asset}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className={`font-mono ${trade.pnl >= 0 ? "text-accent" : "text-destructive"}`}>
                        {trade.pnl >= 0 ? "+" : ""}${trade.pnl}
                      </span>
                      <span className="text-xs text-muted-foreground">{trade.time}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Trading Status */}
        <div className="glass rounded-xl p-6 border border-border/30">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-foreground">Trading Session Status</h3>
            <Badge variant="outline" className={agent.isActive ? "text-accent border-accent/30" : "text-muted-foreground"}>
              {agent.isActive ? "Active" : "Inactive"}
            </Badge>
          </div>

          <div className="grid md:grid-cols-4 gap-4">
            <div>
              <span className="text-xs text-muted-foreground">Session Duration</span>
              <p className="font-mono text-foreground">47h 23m</p>
            </div>
            <div>
              <span className="text-xs text-muted-foreground">Total Trades</span>
              <p className="font-mono text-foreground">156</p>
            </div>
            <div>
              <span className="text-xs text-muted-foreground">Win Rate</span>
              <p className="font-mono text-foreground">62.4%</p>
            </div>
            <div>
              <span className="text-xs text-muted-foreground">Last Trade</span>
              <p className="font-mono text-foreground">2m ago</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
