"use client"

import { PoolCard, type PoolData } from "@/components/iris/pool-card"
import { SectionHeader } from "@/components/iris/section-header"
import { MetricCard } from "@/components/iris/metric-card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import {
  Shield,
  Zap,
  Flame,
  TrendingUp,
  DollarSign,
  BarChart3,
  ArrowRight,
} from "lucide-react"

const pools: PoolData[] = [
  {
    id: "conservative",
    name: "Conservative",
    tvl: 12400000,
    apy: 8.2,
    volatilityCap: 12,
    capacityUsed: 78,
    drawdownLimit: 5,
    activeAgents: 12,
    rollingVolatility: 8.4,
  },
  {
    id: "balanced",
    name: "Balanced",
    tvl: 28700000,
    apy: 15.6,
    volatilityCap: 25,
    capacityUsed: 92,
    drawdownLimit: 12,
    activeAgents: 24,
    rollingVolatility: 18.2,
  },
  {
    id: "aggressive",
    name: "Aggressive",
    tvl: 8200000,
    apy: 28.4,
    volatilityCap: 45,
    capacityUsed: 45,
    drawdownLimit: 25,
    activeAgents: 11,
    rollingVolatility: 32.1,
  },
]

const comparisonData = [
  { metric: "Expected APY", conservative: "6-10%", balanced: "12-18%", aggressive: "20-35%" },
  { metric: "Volatility Cap", conservative: "12%", balanced: "25%", aggressive: "45%" },
  { metric: "Max Drawdown", conservative: "5%", balanced: "12%", aggressive: "25%" },
  { metric: "Min Sharpe", conservative: "1.5", balanced: "1.2", aggressive: "0.8" },
  { metric: "Lock Period", conservative: "24h", balanced: "48h", aggressive: "72h" },
]

export default function RiskPoolsPage() {
  const totalTVL = pools.reduce((sum, p) => sum + p.tvl, 0)

  return (
    <div className="min-h-screen bg-transparent">
      {/* Header */}
      <div className="border-b border-border/30 bg-muted/10">
        <div className="max-w-[1800px] mx-auto px-4 md:px-6 py-8">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div>
              <h1 className="text-2xl md:text-3xl font-bold text-foreground mb-2">
                Risk Pools
              </h1>
              <p className="text-muted-foreground">
                Tiered capital pools with volatility caps and drawdown enforcement
              </p>
            </div>
            <Button className="glow-cyan">
              <DollarSign className="w-4 h-4 mr-2" />
              Deposit Capital
            </Button>
          </div>
        </div>
      </div>

      <div className="max-w-[1800px] mx-auto px-4 md:px-6 py-8">
        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <MetricCard
            title="Total TVL"
            value={`$${(totalTVL / 1000000).toFixed(1)}M`}
            change={2.4}
            changeLabel="7d"
            icon={<TrendingUp className="w-4 h-4" />}
            variant="cyan"
          />
          <MetricCard
            title="Active Pools"
            value="3"
            icon={<Shield className="w-4 h-4" />}
          />
          <MetricCard
            title="Total Agents"
            value={pools.reduce((sum, p) => sum + p.activeAgents, 0).toString()}
            icon={<Zap className="w-4 h-4" />}
          />
          <MetricCard
            title="Avg APY"
            value={`${(pools.reduce((sum, p) => sum + p.apy, 0) / pools.length).toFixed(1)}%`}
            icon={<BarChart3 className="w-4 h-4" />}
            variant="emerald"
          />
        </div>

        {/* Pool Cards */}
        <SectionHeader
          title="Available Pools"
          description="Select a risk tier based on your risk tolerance and return expectations."
        />

        <div className="grid md:grid-cols-3 gap-6 mb-12">
          {pools.map((pool) => (
            <PoolCard key={pool.id} pool={pool} />
          ))}
        </div>

        {/* Comparison Table */}
        <SectionHeader
          title="Pool Comparison"
          description="Detailed comparison of risk parameters across all pools."
        />

        <div className="glass rounded-xl border border-border/30 overflow-hidden mb-12">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border/30 bg-muted/30">
                  <th className="text-left p-4 text-sm font-medium text-muted-foreground">Metric</th>
                  <th className="text-center p-4">
                    <div className="flex items-center justify-center gap-2">
                      <Shield className="w-4 h-4 text-chart-3" />
                      <span className="text-sm font-medium text-foreground">Conservative</span>
                    </div>
                  </th>
                  <th className="text-center p-4">
                    <div className="flex items-center justify-center gap-2">
                      <Zap className="w-4 h-4 text-primary" />
                      <span className="text-sm font-medium text-foreground">Balanced</span>
                    </div>
                  </th>
                  <th className="text-center p-4">
                    <div className="flex items-center justify-center gap-2">
                      <Flame className="w-4 h-4 text-destructive" />
                      <span className="text-sm font-medium text-foreground">Aggressive</span>
                    </div>
                  </th>
                </tr>
              </thead>
              <tbody>
                {comparisonData.map((row, i) => (
                  <tr key={row.metric} className={i < comparisonData.length - 1 ? "border-b border-border/30" : ""}>
                    <td className="p-4 text-sm text-muted-foreground">{row.metric}</td>
                    <td className="p-4 text-center font-mono text-sm text-foreground">{row.conservative}</td>
                    <td className="p-4 text-center font-mono text-sm text-foreground">{row.balanced}</td>
                    <td className="p-4 text-center font-mono text-sm text-foreground">{row.aggressive}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* TVL Distribution */}
        <div className="grid lg:grid-cols-2 gap-6">
          <div className="glass rounded-xl p-6 border border-border/30">
            <h3 className="font-semibold text-foreground mb-6">TVL Distribution</h3>
            <div className="space-y-4">
              {pools.map((pool) => {
                const percentage = (pool.tvl / totalTVL) * 100
                const colors = {
                  Conservative: "bg-chart-3",
                  Balanced: "bg-primary",
                  Aggressive: "bg-destructive",
                }
                return (
                  <div key={pool.id}>
                    <div className="flex items-center justify-between text-sm mb-2">
                      <span className="text-foreground">{pool.name}</span>
                      <span className="font-mono text-muted-foreground">
                        ${(pool.tvl / 1000000).toFixed(1)}M ({percentage.toFixed(1)}%)
                      </span>
                    </div>
                    <div className="h-3 rounded-full bg-muted overflow-hidden">
                      <div
                        className={`h-full rounded-full ${colors[pool.name]}`}
                        style={{ width: `${percentage}%` }}
                      />
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          <div className="glass rounded-xl p-6 border border-border/30">
            <h3 className="font-semibold text-foreground mb-6">Risk/Return Profile</h3>
            <div className="space-y-4">
              {pools.map((pool) => {
                const riskScore = pool.name === "Conservative" ? 25 : pool.name === "Balanced" ? 50 : 80
                return (
                  <div key={pool.id} className="flex items-center gap-4">
                    <div className="w-24 text-sm text-foreground">{pool.name}</div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs text-muted-foreground">Risk</span>
                        <Progress value={riskScore} className="h-2 flex-1" />
                        <span className="text-xs font-mono text-muted-foreground w-8">{riskScore}%</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-muted-foreground">Return</span>
                        <Progress value={pool.apy * 2} className="h-2 flex-1" />
                        <span className="text-xs font-mono text-muted-foreground w-8">{pool.apy}%</span>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>

            <div className="mt-6 p-4 rounded-lg bg-primary/5 border border-primary/20">
              <p className="text-sm text-muted-foreground">
                Higher risk pools offer greater return potential but come with increased volatility exposure 
                and drawdown limits. Choose based on your risk tolerance.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
