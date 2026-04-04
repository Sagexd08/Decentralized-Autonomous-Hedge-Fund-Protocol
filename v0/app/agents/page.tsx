"use client"

import { useState } from "react"
import { AgentCard, type AgentData } from "@/components/dacap/agent-card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Search, Filter, Grid, List, Plus, ArrowUpDown } from "lucide-react"

const allAgents: AgentData[] = [
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
  {
    id: "voltex-ai",
    name: "VoltexAI",
    strategy: "Volatility Trading",
    riskLevel: "Aggressive",
    score: 82,
    sharpe: 1.76,
    pnl: 54300,
    pnlPercent: 5.4,
    drawdown: 8.2,
    allocation: 11.5,
    stake: 150000,
    isActive: true,
    badges: [],
  },
  {
    id: "delta-hedge",
    name: "DeltaHedge",
    strategy: "Options Delta Neutral",
    riskLevel: "Conservative",
    score: 85,
    sharpe: 1.92,
    pnl: 48200,
    pnlPercent: 6.2,
    drawdown: 1.8,
    allocation: 10.2,
    stake: 175000,
    isActive: true,
    badges: ["Low Drawdown"],
  },
  {
    id: "omega-flow",
    name: "OmegaFlow",
    strategy: "Order Flow Analysis",
    riskLevel: "Balanced",
    score: 79,
    sharpe: 1.65,
    pnl: 38900,
    pnlPercent: 4.8,
    drawdown: 5.1,
    allocation: 8.4,
    stake: 120000,
    isActive: true,
    badges: [],
  },
  {
    id: "stable-yield",
    name: "StableYield",
    strategy: "Yield Farming Optimization",
    riskLevel: "Conservative",
    score: 81,
    sharpe: 1.45,
    pnl: 32100,
    pnlPercent: 4.1,
    drawdown: 1.2,
    allocation: 7.8,
    stake: 160000,
    isActive: true,
    badges: ["Lowest DD"],
  },
  {
    id: "flux-arb",
    name: "FluxArb",
    strategy: "Cross-Exchange Arbitrage",
    riskLevel: "Balanced",
    score: 76,
    sharpe: 1.58,
    pnl: 28700,
    pnlPercent: 3.6,
    drawdown: 4.5,
    allocation: 6.2,
    stake: 95000,
    isActive: false,
    badges: [],
  },
  {
    id: "nova-surge",
    name: "NovaSurge",
    strategy: "Breakout Detection",
    riskLevel: "Aggressive",
    score: 74,
    sharpe: 1.42,
    pnl: 21500,
    pnlPercent: 2.9,
    drawdown: 9.4,
    allocation: 5.8,
    stake: 85000,
    isActive: true,
    badges: [],
  },
]

export default function AgentsPage() {
  const [searchQuery, setSearchQuery] = useState("")
  const [riskFilter, setRiskFilter] = useState<string>("all")
  const [sortBy, setSortBy] = useState<string>("score")
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid")

  const filteredAgents = allAgents
    .filter((agent) => {
      const matchesSearch =
        agent.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        agent.strategy.toLowerCase().includes(searchQuery.toLowerCase())
      const matchesRisk = riskFilter === "all" || agent.riskLevel === riskFilter
      return matchesSearch && matchesRisk
    })
    .sort((a, b) => {
      switch (sortBy) {
        case "score":
          return b.score - a.score
        case "sharpe":
          return b.sharpe - a.sharpe
        case "pnl":
          return b.pnlPercent - a.pnlPercent
        case "allocation":
          return b.allocation - a.allocation
        case "drawdown":
          return a.drawdown - b.drawdown
        default:
          return b.score - a.score
      }
    })

  return (
    <div className="min-h-screen bg-transparent">
      {/* Header */}
      <div className="border-b border-border/30 bg-muted/10">
        <div className="max-w-[1800px] mx-auto px-4 md:px-6 py-8">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div>
              <h1 className="text-2xl md:text-3xl font-bold text-foreground mb-2">
                Agent Marketplace
              </h1>
              <p className="text-muted-foreground">
                {allAgents.length} agents competing for capital allocation
              </p>
            </div>
            <Button className="glow-cyan">
              <Plus className="w-4 h-4 mr-2" />
              Register New Agent
            </Button>
          </div>
        </div>
      </div>

      <div className="max-w-[1800px] mx-auto px-4 md:px-6 py-8">
        {/* Stats Row */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <div className="glass rounded-xl p-4 border border-border/30">
            <div className="text-xs text-muted-foreground mb-1">Total Agents</div>
            <div className="text-2xl font-bold font-mono text-foreground">{allAgents.length}</div>
          </div>
          <div className="glass rounded-xl p-4 border border-border/30">
            <div className="text-xs text-muted-foreground mb-1">Active Trading</div>
            <div className="text-2xl font-bold font-mono text-accent">
              {allAgents.filter((a) => a.isActive).length}
            </div>
          </div>
          <div className="glass rounded-xl p-4 border border-border/30">
            <div className="text-xs text-muted-foreground mb-1">Avg. Sharpe</div>
            <div className="text-2xl font-bold font-mono text-foreground">
              {(allAgents.reduce((sum, a) => sum + a.sharpe, 0) / allAgents.length).toFixed(2)}
            </div>
          </div>
          <div className="glass rounded-xl p-4 border border-border/30">
            <div className="text-xs text-muted-foreground mb-1">Total Stake</div>
            <div className="text-2xl font-bold font-mono text-foreground">
              ${(allAgents.reduce((sum, a) => sum + a.stake, 0) / 1000000).toFixed(2)}M
            </div>
          </div>
        </div>

        {/* Filters */}
        <div className="glass rounded-xl p-4 border border-border/30 mb-6">
          <div className="flex flex-col md:flex-row gap-4 items-start md:items-center justify-between">
            <div className="flex flex-col sm:flex-row gap-3 flex-1 w-full md:w-auto">
              <div className="relative flex-1 max-w-md">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  placeholder="Search agents..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10"
                />
              </div>

              <Select value={riskFilter} onValueChange={setRiskFilter}>
                <SelectTrigger className="w-full sm:w-[160px]">
                  <Filter className="w-4 h-4 mr-2" />
                  <SelectValue placeholder="Risk Level" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Risk Levels</SelectItem>
                  <SelectItem value="Conservative">Conservative</SelectItem>
                  <SelectItem value="Balanced">Balanced</SelectItem>
                  <SelectItem value="Aggressive">Aggressive</SelectItem>
                </SelectContent>
              </Select>

              <Select value={sortBy} onValueChange={setSortBy}>
                <SelectTrigger className="w-full sm:w-[160px]">
                  <ArrowUpDown className="w-4 h-4 mr-2" />
                  <SelectValue placeholder="Sort by" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="score">Score</SelectItem>
                  <SelectItem value="sharpe">Sharpe Ratio</SelectItem>
                  <SelectItem value="pnl">PnL %</SelectItem>
                  <SelectItem value="allocation">Allocation</SelectItem>
                  <SelectItem value="drawdown">Drawdown (Low)</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant={viewMode === "grid" ? "secondary" : "ghost"}
                size="icon"
                onClick={() => setViewMode("grid")}
              >
                <Grid className="w-4 h-4" />
              </Button>
              <Button
                variant={viewMode === "list" ? "secondary" : "ghost"}
                size="icon"
                onClick={() => setViewMode("list")}
              >
                <List className="w-4 h-4" />
              </Button>
            </div>
          </div>
        </div>

        {/* Results */}
        <div className="mb-4 flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Showing {filteredAgents.length} of {allAgents.length} agents
          </p>
          <div className="flex gap-2">
            {riskFilter !== "all" && (
              <Badge variant="secondary" className="text-xs">
                {riskFilter}
                <button
                  onClick={() => setRiskFilter("all")}
                  className="ml-1 hover:text-foreground"
                >
                  ×
                </button>
              </Badge>
            )}
          </div>
        </div>

        {/* Agent Grid/List */}
        {viewMode === "grid" ? (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {filteredAgents.map((agent) => (
              <AgentCard key={agent.id} agent={agent} variant="card" />
            ))}
          </div>
        ) : (
          <div className="space-y-3">
            {filteredAgents.map((agent) => (
              <AgentCard key={agent.id} agent={agent} variant="row" />
            ))}
          </div>
        )}

        {filteredAgents.length === 0 && (
          <div className="text-center py-16">
            <p className="text-muted-foreground">No agents found matching your criteria.</p>
          </div>
        )}
      </div>
    </div>
  )
}
