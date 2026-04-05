"use client"

import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { SectionHeader } from "@/components/iris/section-header"
import { MetricCard } from "@/components/iris/metric-card"
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
  Cell,
} from "recharts"
import {
  TrendingUp,
  TrendingDown,
  Calendar,
  Download,
  Filter,
  DollarSign,
  Activity,
  BarChart3,
  ArrowUpRight,
  ArrowDownRight,
} from "lucide-react"

const pnlData = [
  { date: "Jan 1", pnl: 0, cumulative: 0 },
  { date: "Jan 8", pnl: 12500, cumulative: 12500 },
  { date: "Jan 15", pnl: -3200, cumulative: 9300 },
  { date: "Jan 22", pnl: 18700, cumulative: 28000 },
  { date: "Jan 29", pnl: 8400, cumulative: 36400 },
  { date: "Feb 5", pnl: -5100, cumulative: 31300 },
  { date: "Feb 12", pnl: 22300, cumulative: 53600 },
  { date: "Feb 19", pnl: 15800, cumulative: 69400 },
  { date: "Feb 26", pnl: -8900, cumulative: 60500 },
  { date: "Mar 4", pnl: 31200, cumulative: 91700 },
  { date: "Mar 11", pnl: 19500, cumulative: 111200 },
  { date: "Mar 18", pnl: -4300, cumulative: 106900 },
  { date: "Mar 25", pnl: 28100, cumulative: 135000 },
]

const weeklyBreakdown = [
  { week: "W1", pnl: 12500, trades: 42, winRate: 67 },
  { week: "W2", pnl: -3200, trades: 38, winRate: 45 },
  { week: "W3", pnl: 18700, trades: 51, winRate: 72 },
  { week: "W4", pnl: 8400, trades: 45, winRate: 58 },
  { week: "W5", pnl: -5100, trades: 39, winRate: 42 },
  { week: "W6", pnl: 22300, trades: 48, winRate: 71 },
  { week: "W7", pnl: 15800, trades: 52, winRate: 65 },
  { week: "W8", pnl: -8900, trades: 41, winRate: 39 },
  { week: "W9", pnl: 31200, trades: 55, winRate: 78 },
  { week: "W10", pnl: 19500, trades: 49, winRate: 69 },
  { week: "W11", pnl: -4300, trades: 43, winRate: 47 },
  { week: "W12", pnl: 28100, trades: 57, winRate: 75 },
]

const agentAttribution = [
  { name: "AlphaWave", pnl: 45200, share: 33.5 },
  { name: "NeuralArb", pnl: 32100, share: 23.8 },
  { name: "QuantSigma", pnl: 28700, share: 21.3 },
  { name: "DeltaHedge", pnl: 18400, share: 13.6 },
  { name: "MomentumX", pnl: 10600, share: 7.8 },
]

const recentTransactions = [
  { time: "14:32", type: "profit", amount: 4250, agent: "AlphaWave", strategy: "ETH Long" },
  { time: "13:18", type: "loss", amount: -1820, agent: "NeuralArb", strategy: "BTC Arb" },
  { time: "12:45", type: "profit", amount: 2890, agent: "QuantSigma", strategy: "SOL Momentum" },
  { time: "11:22", type: "profit", amount: 5120, agent: "AlphaWave", strategy: "ETH Long" },
  { time: "10:08", type: "loss", amount: -980, agent: "DeltaHedge", strategy: "Delta Neutral" },
  { time: "09:41", type: "profit", amount: 3450, agent: "MomentumX", strategy: "Trend Follow" },
]

export default function PnLHistoryPage() {
  return (
    <div className="min-h-screen bg-transparent">
      <div className="max-w-[1800px] mx-auto px-4 md:px-6 py-8">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
          <SectionHeader
            eyebrow="Performance"
            title="PnL History"
            description="Historical profit and loss tracking across the protocol."
            className="mb-0"
          />
          <div className="flex items-center gap-3">
            <Button variant="outline" size="sm">
              <Calendar className="w-4 h-4 mr-2" />
              Date Range
            </Button>
            <Button variant="outline" size="sm">
              <Filter className="w-4 h-4 mr-2" />
              Filter
            </Button>
            <Button variant="outline" size="sm">
              <Download className="w-4 h-4 mr-2" />
              Export
            </Button>
          </div>
        </div>

        {/* Key Metrics */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <MetricCard
            title="Total PnL (YTD)"
            value="$135,000"
            change={{ value: 12.4, label: "vs last year" }}
            icon={DollarSign}
          />
          <MetricCard
            title="Win Rate"
            value="62.3%"
            change={{ value: 3.2, label: "vs last month" }}
            icon={TrendingUp}
          />
          <MetricCard
            title="Sharpe Ratio"
            value="1.87"
            change={{ value: 0.15, label: "vs last month" }}
            icon={Activity}
          />
          <MetricCard
            title="Max Drawdown"
            value="-6.2%"
            subtitle="Feb 26"
            icon={TrendingDown}
          />
        </div>

        {/* Main Content */}
        <div className="grid lg:grid-cols-3 gap-6">
          {/* Charts Column */}
          <div className="lg:col-span-2 space-y-6">
            {/* Cumulative PnL Chart */}
            <div className="glass rounded-xl p-6 border border-border/30">
              <div className="flex items-center justify-between mb-6">
                <h3 className="font-semibold text-foreground flex items-center gap-2">
                  <TrendingUp className="w-5 h-5 text-primary" />
                  Cumulative PnL
                </h3>
                <Tabs defaultValue="3m">
                  <TabsList>
                    <TabsTrigger value="1m">1M</TabsTrigger>
                    <TabsTrigger value="3m">3M</TabsTrigger>
                    <TabsTrigger value="6m">6M</TabsTrigger>
                    <TabsTrigger value="1y">1Y</TabsTrigger>
                  </TabsList>
                </Tabs>
              </div>

              <div className="h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={pnlData}>
                    <defs>
                      <linearGradient id="colorCumulative" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#00E5CC" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#00E5CC" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#2A2A32" />
                    <XAxis dataKey="date" stroke="#8B8B96" fontSize={12} />
                    <YAxis stroke="#8B8B96" fontSize={12} tickFormatter={(v) => `$${v / 1000}k`} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#111114",
                        border: "1px solid #2A2A32",
                        borderRadius: "8px",
                      }}
                      labelStyle={{ color: "#F0F0F2" }}
                      formatter={(value: number) => [`$${value.toLocaleString()}`, "Cumulative PnL"]}
                    />
                    <Area
                      type="monotone"
                      dataKey="cumulative"
                      stroke="#00E5CC"
                      strokeWidth={2}
                      fill="url(#colorCumulative)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Weekly PnL Breakdown */}
            <div className="glass rounded-xl p-6 border border-border/30">
              <h3 className="font-semibold text-foreground mb-6 flex items-center gap-2">
                <BarChart3 className="w-5 h-5 text-primary" />
                Weekly PnL Breakdown
              </h3>

              <div className="h-[250px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={weeklyBreakdown}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#2A2A32" />
                    <XAxis dataKey="week" stroke="#8B8B96" fontSize={12} />
                    <YAxis stroke="#8B8B96" fontSize={12} tickFormatter={(v) => `$${v / 1000}k`} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#111114",
                        border: "1px solid #2A2A32",
                        borderRadius: "8px",
                      }}
                      formatter={(value: number) => [`$${value.toLocaleString()}`, "PnL"]}
                    />
                    <Bar dataKey="pnl" radius={[4, 4, 0, 0]}>
                      {weeklyBreakdown.map((entry, index) => (
                        <Cell
                          key={`cell-${index}`}
                          fill={entry.pnl >= 0 ? "#10B981" : "#F59E0B"}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Agent Attribution */}
            <div className="glass rounded-xl p-6 border border-border/30">
              <h3 className="font-semibold text-foreground mb-4 flex items-center gap-2">
                <Activity className="w-5 h-5 text-primary" />
                Agent Attribution
              </h3>

              <div className="space-y-4">
                {agentAttribution.map((agent, i) => (
                  <div key={i}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm text-foreground">{agent.name}</span>
                      <span className="text-sm font-mono text-accent">
                        +${(agent.pnl / 1000).toFixed(1)}k
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-2 rounded-full bg-muted overflow-hidden">
                        <div
                          className="h-full bg-primary rounded-full"
                          style={{ width: `${agent.share}%` }}
                        />
                      </div>
                      <span className="text-xs text-muted-foreground w-12 text-right">
                        {agent.share}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Recent Transactions */}
            <div className="glass rounded-xl p-6 border border-border/30">
              <h3 className="font-semibold text-foreground mb-4 flex items-center gap-2">
                <DollarSign className="w-5 h-5 text-primary" />
                Recent Transactions
              </h3>

              <div className="space-y-3">
                {recentTransactions.map((tx, i) => (
                  <div key={i} className="flex items-center justify-between py-2 border-b border-border/20 last:border-0">
                    <div className="flex items-center gap-3">
                      <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                        tx.type === "profit" ? "bg-accent/20" : "bg-destructive/20"
                      }`}>
                        {tx.type === "profit" ? (
                          <ArrowUpRight className="w-4 h-4 text-accent" />
                        ) : (
                          <ArrowDownRight className="w-4 h-4 text-destructive" />
                        )}
                      </div>
                      <div>
                        <div className="text-sm text-foreground">{tx.agent}</div>
                        <div className="text-xs text-muted-foreground">{tx.strategy}</div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className={`text-sm font-mono ${
                        tx.type === "profit" ? "text-accent" : "text-destructive"
                      }`}>
                        {tx.type === "profit" ? "+" : ""}${Math.abs(tx.amount).toLocaleString()}
                      </div>
                      <div className="text-xs text-muted-foreground">{tx.time}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Performance Summary */}
            <div className="glass rounded-xl p-6 border border-primary/30">
              <h3 className="font-semibold text-foreground mb-4">Performance Summary</h3>

              <div className="space-y-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Best Day</span>
                  <span className="text-accent font-mono">+$31,200</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Worst Day</span>
                  <span className="text-destructive font-mono">-$8,900</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Avg Daily PnL</span>
                  <span className="text-foreground font-mono">+$1,485</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Winning Days</span>
                  <span className="text-foreground font-mono">57 / 91</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Profit Factor</span>
                  <span className="text-foreground font-mono">2.14</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
