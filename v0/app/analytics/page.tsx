"use client"

import { SectionHeader } from "@/components/dacap/section-header"
import { MetricCard } from "@/components/dacap/metric-card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs"
import {
  BarChart3,
  TrendingUp,
  Activity,
  Shield,
  Calculator,
  PieChart,
  LineChart,
  Target,
  Percent,
} from "lucide-react"

const performanceData = [
  { period: "1D", return: 0.82, benchmark: 0.45 },
  { period: "7D", return: 3.24, benchmark: 2.12 },
  { period: "30D", return: 12.5, benchmark: 8.4 },
  { period: "90D", return: 28.7, benchmark: 18.2 },
  { period: "YTD", return: 45.2, benchmark: 32.1 },
]

const riskMetrics = [
  { name: "Value at Risk (95%)", value: "$2.4M", desc: "1-day VaR" },
  { name: "Expected Shortfall", value: "$3.1M", desc: "CVaR at 95%" },
  { name: "Max Drawdown", value: "-8.5%", desc: "Peak to trough" },
  { name: "Volatility (30d)", value: "18.2%", desc: "Annualized" },
  { name: "Beta vs BTC", value: "0.72", desc: "Market sensitivity" },
  { name: "Correlation", value: "0.65", desc: "vs benchmark" },
]

const attributionData = [
  { source: "Agent Selection", contribution: 42 },
  { source: "Timing", contribution: 28 },
  { source: "Risk Management", contribution: 18 },
  { source: "Residual Alpha", contribution: 12 },
]

const monteCarloResults = {
  median: 52.4,
  percentile5: 28.2,
  percentile95: 78.6,
  probabilityPositive: 94.2,
  simulations: 10000,
}

export default function AnalyticsPage() {
  return (
    <div className="min-h-screen bg-transparent">
      {/* Header */}
      <div className="border-b border-border/30 bg-muted/10">
        <div className="max-w-[1800px] mx-auto px-4 md:px-6 py-8">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div>
              <h1 className="text-2xl md:text-3xl font-bold text-foreground mb-2">
                Quantitative Analytics
              </h1>
              <p className="text-muted-foreground">
                Monte Carlo simulations, VaR, attribution analysis, and risk decomposition
              </p>
            </div>
            <Button variant="outline">
              <Calculator className="w-4 h-4 mr-2" />
              Export Report
            </Button>
          </div>
        </div>
      </div>

      <div className="max-w-[1800px] mx-auto px-4 md:px-6 py-8">
        {/* Key Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <MetricCard
            title="Total Return"
            value="+45.2%"
            change={12.8}
            changeLabel="vs benchmark"
            icon={<TrendingUp className="w-4 h-4" />}
            variant="emerald"
          />
          <MetricCard
            title="Sharpe Ratio"
            value="2.14"
            icon={<Activity className="w-4 h-4" />}
            variant="cyan"
          />
          <MetricCard
            title="Information Ratio"
            value="1.82"
            icon={<Target className="w-4 h-4" />}
          />
          <MetricCard
            title="Win Rate"
            value="62.4%"
            icon={<Percent className="w-4 h-4" />}
          />
        </div>

        <Tabs defaultValue="performance" className="space-y-6">
          <TabsList className="glass border border-border/30">
            <TabsTrigger value="performance">Performance</TabsTrigger>
            <TabsTrigger value="risk">Risk Metrics</TabsTrigger>
            <TabsTrigger value="attribution">Attribution</TabsTrigger>
            <TabsTrigger value="montecarlo">Monte Carlo</TabsTrigger>
          </TabsList>

          {/* Performance Tab */}
          <TabsContent value="performance" className="space-y-6">
            <div className="grid lg:grid-cols-2 gap-6">
              <div className="glass rounded-xl p-6 border border-border/30">
                <h3 className="font-semibold text-foreground mb-6">Return Comparison</h3>
                <div className="space-y-4">
                  {performanceData.map((period) => (
                    <div key={period.period}>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm text-foreground">{period.period}</span>
                        <div className="flex items-center gap-4">
                          <span className="text-sm font-mono">
                            <span className="text-accent">+{period.return}%</span>
                            <span className="text-muted-foreground"> vs </span>
                            <span className="text-muted-foreground">+{period.benchmark}%</span>
                          </span>
                        </div>
                      </div>
                      <div className="flex gap-1 h-4">
                        <div
                          className="bg-primary rounded-l-full"
                          style={{ width: `${period.return}%` }}
                        />
                        <div
                          className="bg-muted-foreground/30 rounded-r-full"
                          style={{ width: `${period.benchmark}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
                <div className="mt-4 pt-4 border-t border-border/30 flex items-center gap-4 text-sm">
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full bg-primary" />
                    <span className="text-muted-foreground">Protocol</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full bg-muted-foreground/30" />
                    <span className="text-muted-foreground">Benchmark</span>
                  </div>
                </div>
              </div>

              <div className="glass rounded-xl p-6 border border-border/30">
                <h3 className="font-semibold text-foreground mb-6">Rolling Performance</h3>
                <div className="space-y-4">
                  {[
                    { metric: "30-day Sharpe", value: "2.34", trend: "up" },
                    { metric: "30-day Sortino", value: "3.12", trend: "up" },
                    { metric: "30-day Calmar", value: "2.98", trend: "stable" },
                    { metric: "Rolling Alpha", value: "+4.2%", trend: "up" },
                    { metric: "Tracking Error", value: "5.8%", trend: "down" },
                  ].map((metric) => (
                    <div key={metric.metric} className="flex items-center justify-between py-2 border-b border-border/30 last:border-0">
                      <span className="text-sm text-muted-foreground">{metric.metric}</span>
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-foreground">{metric.value}</span>
                        {metric.trend === "up" && <TrendingUp className="w-4 h-4 text-accent" />}
                        {metric.trend === "down" && <TrendingUp className="w-4 h-4 text-destructive rotate-180" />}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </TabsContent>

          {/* Risk Tab */}
          <TabsContent value="risk" className="space-y-6">
            <div className="grid lg:grid-cols-2 gap-6">
              <div className="glass rounded-xl p-6 border border-border/30">
                <h3 className="font-semibold text-foreground mb-6">Risk Metrics</h3>
                <div className="grid sm:grid-cols-2 gap-4">
                  {riskMetrics.map((metric) => (
                    <div key={metric.name} className="p-4 rounded-lg bg-muted/30 border border-border/30">
                      <div className="text-xs text-muted-foreground mb-1">{metric.desc}</div>
                      <div className="text-lg font-mono font-semibold text-foreground">{metric.value}</div>
                      <div className="text-sm text-foreground mt-1">{metric.name}</div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="glass rounded-xl p-6 border border-border/30">
                <h3 className="font-semibold text-foreground mb-6">Drawdown Analysis</h3>
                <div className="space-y-4">
                  {[
                    { date: "Mar 2024", drawdown: -8.5, recovery: "12 days" },
                    { date: "Jan 2024", drawdown: -5.2, recovery: "6 days" },
                    { date: "Nov 2023", drawdown: -4.8, recovery: "8 days" },
                  ].map((dd, i) => (
                    <div key={i} className="p-4 rounded-lg bg-destructive/5 border border-destructive/20">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm text-foreground">{dd.date}</span>
                        <Badge variant="outline" className="text-destructive border-destructive/30">
                          {dd.drawdown}%
                        </Badge>
                      </div>
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-muted-foreground">Recovery Time</span>
                        <span className="text-foreground">{dd.recovery}</span>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="mt-4 p-4 rounded-lg bg-accent/5 border border-accent/20">
                  <div className="text-sm font-medium text-foreground mb-1">Average Recovery</div>
                  <div className="text-2xl font-mono font-bold text-accent">8.7 days</div>
                </div>
              </div>
            </div>
          </TabsContent>

          {/* Attribution Tab */}
          <TabsContent value="attribution" className="space-y-6">
            <div className="grid lg:grid-cols-2 gap-6">
              <div className="glass rounded-xl p-6 border border-border/30">
                <h3 className="font-semibold text-foreground mb-6">Return Attribution</h3>
                <div className="space-y-4">
                  {attributionData.map((item) => (
                    <div key={item.source}>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm text-foreground">{item.source}</span>
                        <span className="font-mono text-sm text-muted-foreground">{item.contribution}%</span>
                      </div>
                      <Progress value={item.contribution} className="h-3" />
                    </div>
                  ))}
                </div>

                <div className="mt-6 p-4 rounded-lg bg-primary/5 border border-primary/20">
                  <p className="text-sm text-muted-foreground">
                    Agent selection accounts for the majority of returns, followed by market timing 
                    decisions. Risk management contributes by limiting drawdowns.
                  </p>
                </div>
              </div>

              <div className="glass rounded-xl p-6 border border-border/30">
                <h3 className="font-semibold text-foreground mb-6">Agent Contribution</h3>
                <div className="space-y-3">
                  {[
                    { name: "AlphaWave", contribution: 32, pnl: "+$1.2M" },
                    { name: "NeuralArb", contribution: 24, pnl: "+$890K" },
                    { name: "QuantSigma", contribution: 18, pnl: "+$680K" },
                    { name: "VoltexAI", contribution: 14, pnl: "+$520K" },
                    { name: "Others", contribution: 12, pnl: "+$450K" },
                  ].map((agent) => (
                    <div key={agent.name} className="flex items-center gap-4 p-3 rounded-lg bg-muted/30 border border-border/30">
                      <div className="flex-1">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-sm font-medium text-foreground">{agent.name}</span>
                          <span className="font-mono text-sm text-accent">{agent.pnl}</span>
                        </div>
                        <Progress value={agent.contribution} className="h-1.5" />
                      </div>
                      <span className="font-mono text-xs text-muted-foreground w-12 text-right">
                        {agent.contribution}%
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </TabsContent>

          {/* Monte Carlo Tab */}
          <TabsContent value="montecarlo" className="space-y-6">
            <div className="grid lg:grid-cols-2 gap-6">
              <div className="glass rounded-xl p-6 border border-border/30">
                <h3 className="font-semibold text-foreground mb-6">Monte Carlo Simulation</h3>
                <div className="text-center py-8">
                  <div className="text-5xl font-bold font-mono text-primary mb-2">
                    {monteCarloResults.median}%
                  </div>
                  <div className="text-muted-foreground mb-6">Median Expected Return (1Y)</div>

                  <div className="grid grid-cols-3 gap-4">
                    <div className="p-4 rounded-lg bg-destructive/5 border border-destructive/20">
                      <div className="text-sm text-muted-foreground">5th Percentile</div>
                      <div className="text-xl font-mono font-semibold text-foreground">
                        +{monteCarloResults.percentile5}%
                      </div>
                    </div>
                    <div className="p-4 rounded-lg bg-primary/5 border border-primary/20">
                      <div className="text-sm text-muted-foreground">Median</div>
                      <div className="text-xl font-mono font-semibold text-foreground">
                        +{monteCarloResults.median}%
                      </div>
                    </div>
                    <div className="p-4 rounded-lg bg-accent/5 border border-accent/20">
                      <div className="text-sm text-muted-foreground">95th Percentile</div>
                      <div className="text-xl font-mono font-semibold text-foreground">
                        +{monteCarloResults.percentile95}%
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="glass rounded-xl p-6 border border-border/30">
                <h3 className="font-semibold text-foreground mb-6">Simulation Details</h3>
                <div className="space-y-4">
                  <div className="flex items-center justify-between py-3 border-b border-border/30">
                    <span className="text-muted-foreground">Simulations Run</span>
                    <span className="font-mono text-foreground">{monteCarloResults.simulations.toLocaleString()}</span>
                  </div>
                  <div className="flex items-center justify-between py-3 border-b border-border/30">
                    <span className="text-muted-foreground">Probability of Positive Return</span>
                    <span className="font-mono text-accent">{monteCarloResults.probabilityPositive}%</span>
                  </div>
                  <div className="flex items-center justify-between py-3 border-b border-border/30">
                    <span className="text-muted-foreground">Confidence Interval</span>
                    <span className="font-mono text-foreground">90%</span>
                  </div>
                  <div className="flex items-center justify-between py-3">
                    <span className="text-muted-foreground">Holding Period</span>
                    <span className="font-mono text-foreground">12 months</span>
                  </div>
                </div>

                <div className="mt-6 p-4 rounded-lg bg-accent/5 border border-accent/20">
                  <div className="flex items-center gap-2 mb-2">
                    <Shield className="w-4 h-4 text-accent" />
                    <span className="font-medium text-foreground">High Confidence</span>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    94.2% of simulations resulted in positive returns over the 1-year horizon, 
                    indicating strong risk-adjusted performance expectations.
                  </p>
                </div>
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}
