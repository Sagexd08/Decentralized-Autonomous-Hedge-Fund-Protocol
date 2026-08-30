"use client"

import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { SectionHeader } from "@/components/iris/section-header"
import { AnimatedGlobe } from "@/components/visuals/animated-globe"
import {
  Globe,
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  Activity,
  DollarSign,
  Zap,
  RefreshCw,
  Bell,
  MapPin,
} from "lucide-react"

const worldEvents = [
  {
    region: "North America",
    event: "Fed Rate Decision",
    impact: "high",
    type: "macro",
    description: "Federal Reserve maintains rates, signals potential cut in Q2",
    time: "2h ago",
    sentiment: "bullish",
  },
  {
    region: "Europe",
    event: "ECB Policy Update",
    impact: "medium",
    type: "macro",
    description: "European Central Bank holds steady, inflation concerns ease",
    time: "4h ago",
    sentiment: "neutral",
  },
  {
    region: "Asia",
    event: "China Manufacturing PMI",
    impact: "high",
    type: "economic",
    description: "Manufacturing PMI beats expectations at 51.2 vs 50.5 expected",
    time: "6h ago",
    sentiment: "bullish",
  },
  {
    region: "Middle East",
    event: "Geopolitical Tension",
    impact: "high",
    type: "geopolitical",
    description: "Escalating tensions affecting oil futures and risk sentiment",
    time: "8h ago",
    sentiment: "bearish",
  },
  {
    region: "Global",
    event: "BTC ETF Flows",
    impact: "medium",
    type: "crypto",
    description: "Net inflows of $245M across spot Bitcoin ETFs",
    time: "12h ago",
    sentiment: "bullish",
  },
]

const marketRegimes = [
  { name: "Risk Appetite", value: 67, trend: "up", color: "accent" },
  { name: "Volatility Index", value: 18.4, trend: "down", color: "primary" },
  { name: "Liquidity Score", value: 82, trend: "up", color: "chart-3" },
  { name: "Correlation Index", value: 0.45, trend: "stable", color: "chart-4" },
]

const liquidityHotspots = [
  { exchange: "Binance", volume: "$2.1B", share: "28%", change: "+5.2%" },
  { exchange: "Coinbase", volume: "$1.4B", share: "19%", change: "+3.1%" },
  { exchange: "OKX", volume: "$980M", share: "13%", change: "-1.2%" },
  { exchange: "Bybit", volume: "$720M", share: "10%", change: "+8.4%" },
  { exchange: "Kraken", volume: "$540M", share: "7%", change: "+2.1%" },
]

const alerts = [
  { type: "warning", message: "High correlation detected between BTC and traditional risk assets", time: "1h ago" },
  { type: "info", message: "Unusual volume spike on ETH/USDT pair", time: "3h ago" },
  { type: "warning", message: "Geopolitical risk score elevated above threshold", time: "5h ago" },
]

export default function WorldMonitorPage() {
  return (
    <div className="min-h-screen bg-transparent">
      <div className="max-w-[1800px] mx-auto px-4 md:px-6 py-8">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
          <SectionHeader
            eyebrow="Intelligence"
            title="World Monitor"
            description="Global market intelligence and event monitoring for protocol decision-making."
            className="mb-0"
          />
          <div className="flex items-center gap-3">
            <Badge variant="outline" className="bg-accent/10 text-accent border-accent/30">
              <span className="w-2 h-2 rounded-full bg-accent animate-pulse mr-2" />
              Live Feed
            </Badge>
            <Button variant="outline" size="sm">
              <Bell className="w-4 h-4 mr-2" />
              Alerts
            </Button>
            <Button variant="outline" size="sm">
              <RefreshCw className="w-4 h-4 mr-2" />
              Refresh
            </Button>
          </div>
        </div>

        {/* Market Regime Indicators */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          {marketRegimes.map((regime) => (
            <div key={regime.name} className="glass rounded-xl p-6 border border-border/30">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-muted-foreground">{regime.name}</span>
                {regime.trend === "up" && <TrendingUp className="w-4 h-4 text-accent" />}
                {regime.trend === "down" && <TrendingDown className="w-4 h-4 text-destructive" />}
                {regime.trend === "stable" && <Activity className="w-4 h-4 text-muted-foreground" />}
              </div>
              <div className="text-2xl font-bold text-foreground">
                {typeof regime.value === "number" && regime.value < 1 ? regime.value.toFixed(2) : regime.value}
                {regime.name.includes("Index") && regime.name !== "Correlation Index" ? "" : regime.name.includes("Score") || regime.name.includes("Appetite") ? "%" : ""}
              </div>
            </div>
          ))}
        </div>

        {/* Main Content Grid */}
        <div className="grid lg:grid-cols-3 gap-6">
          {/* Globe Visualization */}
          <div className="lg:col-span-2">
            <div className="glass rounded-xl border border-border/30 overflow-hidden">
              <div className="p-4 border-b border-border/30 flex items-center justify-between">
                <h3 className="font-semibold text-foreground flex items-center gap-2">
                  <Globe className="w-5 h-5 text-primary" />
                  Global Activity Map
                </h3>
                <div className="flex items-center gap-4 text-xs">
                  <div className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-accent" />
                    <span className="text-muted-foreground">Bullish</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-destructive" />
                    <span className="text-muted-foreground">Bearish</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-muted-foreground" />
                    <span className="text-muted-foreground">Neutral</span>
                  </div>
                </div>
              </div>
              <div className="h-[400px]">
                <AnimatedGlobe />
              </div>
            </div>

            {/* World Events Feed */}
            <div className="glass rounded-xl p-6 border border-border/30 mt-6">
              <h3 className="font-semibold text-foreground mb-4 flex items-center gap-2">
                <Zap className="w-5 h-5 text-primary" />
                Live Event Feed
              </h3>

              <div className="space-y-4">
                {worldEvents.map((event, i) => (
                  <div key={i} className="flex items-start gap-4 p-4 rounded-lg bg-muted/20 border border-border/20">
                    <div className={`w-3 h-3 rounded-full mt-1.5 ${
                      event.sentiment === "bullish" ? "bg-accent" :
                      event.sentiment === "bearish" ? "bg-destructive" : "bg-muted-foreground"
                    }`} />
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-sm font-medium text-foreground">{event.event}</span>
                        <Badge variant="outline" className={`text-[10px] ${
                          event.impact === "high" ? "border-destructive/50 text-destructive" :
                          event.impact === "medium" ? "border-chart-4/50 text-chart-4" :
                          "border-muted-foreground/50 text-muted-foreground"
                        }`}>
                          {event.impact.toUpperCase()}
                        </Badge>
                        <Badge variant="outline" className="text-[10px]">
                          {event.type}
                        </Badge>
                      </div>
                      <p className="text-sm text-muted-foreground mb-1">{event.description}</p>
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <MapPin className="w-3 h-3" />
                        <span>{event.region}</span>
                        <span>•</span>
                        <span>{event.time}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Active Alerts */}
            <div className="glass rounded-xl p-6 border border-border/30">
              <h3 className="font-semibold text-foreground mb-4 flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-destructive" />
                Active Alerts
              </h3>

              <div className="space-y-3">
                {alerts.map((alert, i) => (
                  <div key={i} className={`p-3 rounded-lg border ${
                    alert.type === "warning" ? "bg-destructive/10 border-destructive/30" : "bg-primary/10 border-primary/30"
                  }`}>
                    <p className="text-sm text-foreground mb-1">{alert.message}</p>
                    <span className="text-xs text-muted-foreground">{alert.time}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Liquidity Hotspots */}
            <div className="glass rounded-xl p-6 border border-border/30">
              <h3 className="font-semibold text-foreground mb-4 flex items-center gap-2">
                <DollarSign className="w-5 h-5 text-primary" />
                Liquidity Hotspots
              </h3>

              <div className="space-y-3">
                {liquidityHotspots.map((hotspot, i) => (
                  <div key={i} className="flex items-center justify-between py-2 border-b border-border/20 last:border-0">
                    <div>
                      <div className="text-sm text-foreground font-medium">{hotspot.exchange}</div>
                      <div className="text-xs text-muted-foreground">{hotspot.share} market share</div>
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-mono text-foreground">{hotspot.volume}</div>
                      <div className={`text-xs font-mono ${hotspot.change.startsWith("+") ? "text-accent" : "text-destructive"}`}>
                        {hotspot.change}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Protocol Response */}
            <div className="glass rounded-xl p-6 border border-primary/30">
              <h3 className="font-semibold text-foreground mb-4 flex items-center gap-2">
                <Activity className="w-5 h-5 text-primary" />
                Protocol Response
              </h3>

              <div className="space-y-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Current Regime</span>
                  <Badge className="bg-accent/20 text-accent">Risk-On</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Allocation Bias</span>
                  <span className="text-foreground font-mono">+2.3% Aggressive</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Next Rebalance</span>
                  <span className="text-foreground font-mono">1h 42m</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Active Agents</span>
                  <span className="text-foreground font-mono">23/24</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
