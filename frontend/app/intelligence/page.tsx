"use client"

import { useState, useEffect } from "react"
import { SectionHeader } from "@/components/dacap/section-header"
import { MetricCard } from "@/components/dacap/metric-card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import {
  Brain,
  Activity,
  Zap,
  RefreshCw,
  Eye,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Radio,
  Cpu,
} from "lucide-react"

const reasoningLog = [
  {
    time: "12:34:56",
    type: "observation",
    agent: "System",
    message: "Detecting elevated volatility in ETH/USD. VIX proxy up 15%.",
  },
  {
    time: "12:34:57",
    type: "decision",
    agent: "AlphaWave",
    message: "Reducing ETH exposure from 35% to 28%. Confidence: 87%",
  },
  {
    time: "12:34:58",
    type: "action",
    agent: "AlphaWave",
    message: "SELL 12.4 ETH @ $3,245.20. Slippage: 0.02%",
  },
  {
    time: "12:35:02",
    type: "observation",
    agent: "System",
    message: "BTC correlation with SPX increasing. Entering risk-off regime.",
  },
  {
    time: "12:35:04",
    type: "decision",
    agent: "NeuralArb",
    message: "Pausing arbitrage strategies. Spread contraction detected.",
  },
  {
    time: "12:35:08",
    type: "action",
    agent: "QuantSigma",
    message: "Rotating to USDC. Target allocation: 25%",
  },
  {
    time: "12:35:12",
    type: "observation",
    agent: "System",
    message: "Funding rates normalizing across major perp venues.",
  },
  {
    time: "12:35:15",
    type: "decision",
    agent: "VoltexAI",
    message: "Re-entering vol selling strategy with reduced size.",
  },
]

const marketRegimes = [
  { name: "Trending", probability: 0.65, color: "bg-accent" },
  { name: "Mean-Reverting", probability: 0.20, color: "bg-primary" },
  { name: "High Volatility", probability: 0.10, color: "bg-destructive" },
  { name: "Low Volatility", probability: 0.05, color: "bg-muted-foreground" },
]

export default function IntelligencePage() {
  const [activeIndex, setActiveIndex] = useState(0)

  useEffect(() => {
    const interval = setInterval(() => {
      setActiveIndex((prev) => (prev + 1) % reasoningLog.length)
    }, 2000)
    return () => clearInterval(interval)
  }, [])

  const getTypeIcon = (type: string) => {
    switch (type) {
      case "observation":
        return <Eye className="w-4 h-4 text-primary" />
      case "decision":
        return <Brain className="w-4 h-4 text-accent" />
      case "action":
        return <Zap className="w-4 h-4 text-chart-4" />
      default:
        return <Activity className="w-4 h-4" />
    }
  }

  const getTypeBadge = (type: string) => {
    const styles = {
      observation: "bg-primary/10 text-primary border-primary/30",
      decision: "bg-accent/10 text-accent border-accent/30",
      action: "bg-chart-4/10 text-chart-4 border-chart-4/30",
    }
    return styles[type as keyof typeof styles] || "bg-muted text-muted-foreground"
  }

  return (
    <div className="min-h-screen bg-transparent">
      {/* Header */}
      <div className="border-b border-border/30 bg-muted/10">
        <div className="max-w-[1800px] mx-auto px-4 md:px-6 py-8">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div>
              <h1 className="text-2xl md:text-3xl font-bold text-foreground mb-2">
                Intelligence Loop
              </h1>
              <p className="text-muted-foreground">
                Autonomous reasoning with live agent decisions and market regime detection
              </p>
            </div>
            <div className="flex items-center gap-3">
              <Badge variant="outline" className="text-accent border-accent/30 bg-accent/5">
                <Radio className="w-3 h-3 mr-1 animate-pulse" />
                Live Feed
              </Badge>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-[1800px] mx-auto px-4 md:px-6 py-8">
        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <MetricCard
            title="Decisions/Hour"
            value="847"
            change={12}
            changeLabel="vs avg"
            icon={<Brain className="w-4 h-4" />}
            variant="cyan"
          />
          <MetricCard
            title="Avg Confidence"
            value="84.2%"
            icon={<CheckCircle2 className="w-4 h-4" />}
            variant="emerald"
          />
          <MetricCard
            title="Processing Latency"
            value="12ms"
            icon={<Clock className="w-4 h-4" />}
          />
          <MetricCard
            title="Active Models"
            value="47"
            icon={<Cpu className="w-4 h-4" />}
          />
        </div>

        <div className="grid lg:grid-cols-3 gap-6 mb-8">
          {/* Live Reasoning Feed */}
          <div className="lg:col-span-2 glass rounded-xl p-6 border border-border/30">
            <div className="flex items-center justify-between mb-6">
              <h3 className="font-semibold text-foreground">Live Reasoning Feed</h3>
              <Badge variant="outline" className="text-muted-foreground">
                <RefreshCw className="w-3 h-3 mr-1 animate-spin" />
                Auto-updating
              </Badge>
            </div>

            <div className="space-y-2 max-h-[500px] overflow-y-auto">
              {reasoningLog.map((log, i) => (
                <div
                  key={i}
                  className={`p-4 rounded-lg border transition-all ${
                    i === activeIndex
                      ? "bg-primary/10 border-primary/30"
                      : "bg-muted/20 border-border/30"
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <div className="mt-0.5">{getTypeIcon(log.type)}</div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <Badge variant="outline" className={getTypeBadge(log.type)}>
                          {log.type}
                        </Badge>
                        <span className="text-sm font-medium text-foreground">{log.agent}</span>
                        <span className="text-xs font-mono text-muted-foreground">{log.time}</span>
                      </div>
                      <p className="text-sm text-muted-foreground">{log.message}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Market Regime */}
          <div className="glass rounded-xl p-6 border border-border/30">
            <h3 className="font-semibold text-foreground mb-6">Market Regime Detection</h3>

            <div className="space-y-4 mb-6">
              {marketRegimes.map((regime) => (
                <div key={regime.name}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm text-foreground">{regime.name}</span>
                    <span className="font-mono text-sm text-muted-foreground">
                      {(regime.probability * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div className="h-2 rounded-full bg-muted overflow-hidden">
                    <div
                      className={`h-full rounded-full ${regime.color}`}
                      style={{ width: `${regime.probability * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>

            <div className="p-4 rounded-lg bg-accent/5 border border-accent/20">
              <div className="flex items-center gap-2 mb-2">
                <TrendingUp className="w-5 h-5 text-accent" />
                <span className="font-medium text-foreground">Current: Trending</span>
              </div>
              <p className="text-xs text-muted-foreground">
                Strong momentum detected across major pairs. Agents favoring 
                trend-following strategies.
              </p>
            </div>

            <div className="mt-6 pt-4 border-t border-border/30">
              <h4 className="text-sm font-medium text-foreground mb-3">System Posture</h4>
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Risk Appetite</span>
                  <span className="font-mono text-accent">High</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Leverage Limit</span>
                  <span className="font-mono text-foreground">3.5x</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Cash Buffer</span>
                  <span className="font-mono text-foreground">12%</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Signal Sources */}
        <div className="grid md:grid-cols-3 gap-6 mb-8">
          <div className="glass rounded-xl p-6 border border-border/30">
            <h3 className="font-semibold text-foreground mb-4">On-Chain Signals</h3>
            <div className="space-y-3">
              {[
                { name: "Whale Flows", status: "Bullish", value: "+$124M" },
                { name: "DEX Volume", status: "Elevated", value: "$2.4B" },
                { name: "Funding Rates", status: "Neutral", value: "0.01%" },
              ].map((signal) => (
                <div key={signal.name} className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">{signal.name}</span>
                  <div className="flex items-center gap-2">
                    <Badge
                      variant="outline"
                      className={
                        signal.status === "Bullish"
                          ? "text-accent border-accent/30"
                          : signal.status === "Bearish"
                          ? "text-destructive border-destructive/30"
                          : "text-muted-foreground"
                      }
                    >
                      {signal.status}
                    </Badge>
                    <span className="font-mono text-sm text-foreground">{signal.value}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="glass rounded-xl p-6 border border-border/30">
            <h3 className="font-semibold text-foreground mb-4">Technical Signals</h3>
            <div className="space-y-3">
              {[
                { name: "Trend Strength", status: "Strong", value: "ADX: 42" },
                { name: "RSI (14d)", status: "Neutral", value: "58" },
                { name: "MACD", status: "Bullish", value: "Crossover" },
              ].map((signal) => (
                <div key={signal.name} className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">{signal.name}</span>
                  <div className="flex items-center gap-2">
                    <Badge
                      variant="outline"
                      className={
                        signal.status === "Bullish" || signal.status === "Strong"
                          ? "text-accent border-accent/30"
                          : "text-muted-foreground"
                      }
                    >
                      {signal.status}
                    </Badge>
                    <span className="font-mono text-sm text-foreground">{signal.value}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="glass rounded-xl p-6 border border-border/30">
            <h3 className="font-semibold text-foreground mb-4">Sentiment Signals</h3>
            <div className="space-y-3">
              {[
                { name: "Social Volume", status: "Elevated", value: "+34%" },
                { name: "Fear & Greed", status: "Greed", value: "72/100" },
                { name: "Derivatives Skew", status: "Call Heavy", value: "+0.8%" },
              ].map((signal) => (
                <div key={signal.name} className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">{signal.name}</span>
                  <div className="flex items-center gap-2">
                    <Badge
                      variant="outline"
                      className={
                        signal.status === "Greed" || signal.status === "Elevated"
                          ? "text-chart-4 border-chart-4/30"
                          : "text-muted-foreground"
                      }
                    >
                      {signal.status}
                    </Badge>
                    <span className="font-mono text-sm text-foreground">{signal.value}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Active Agent Decisions */}
        <div className="glass rounded-xl p-6 border border-border/30">
          <h3 className="font-semibold text-foreground mb-6">Current Agent Positioning</h3>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { name: "AlphaWave", position: "Long ETH", confidence: 87, pnl: 2.4 },
              { name: "NeuralArb", position: "Paused", confidence: 0, pnl: 0 },
              { name: "QuantSigma", position: "Defensive", confidence: 72, pnl: 0.8 },
              { name: "VoltexAI", position: "Short Vol", confidence: 65, pnl: -0.3 },
            ].map((agent) => (
              <div key={agent.name} className="p-4 rounded-lg bg-muted/30 border border-border/30">
                <div className="flex items-center justify-between mb-3">
                  <span className="font-medium text-foreground">{agent.name}</span>
                  <Badge
                    variant="outline"
                    className={
                      agent.position === "Paused"
                        ? "text-muted-foreground"
                        : agent.pnl >= 0
                        ? "text-accent border-accent/30"
                        : "text-destructive border-destructive/30"
                    }
                  >
                    {agent.pnl >= 0 ? "+" : ""}{agent.pnl}%
                  </Badge>
                </div>
                <p className="text-sm text-muted-foreground mb-2">{agent.position}</p>
                {agent.confidence > 0 && (
                  <div>
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="text-muted-foreground">Confidence</span>
                      <span className="font-mono">{agent.confidence}%</span>
                    </div>
                    <Progress value={agent.confidence} className="h-1.5" />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
