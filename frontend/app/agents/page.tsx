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
import { Search, Filter, Grid, List, Plus, ArrowUpDown, Loader2, AlertCircle } from "lucide-react"
import { useAgents } from "@/hooks/use-agents"
import type { Agent } from "@/lib/api"

function agentToCardData(a: Agent): AgentData {
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

export default function AgentsPage() {
  const [searchQuery, setSearchQuery] = useState("")
  const [riskFilter, setRiskFilter] = useState<string>("all")
  const [sortBy, setSortBy] = useState<string>("score")
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid")

  const { agents, loading, error } = useAgents()

  const filteredAgents = agents
    .filter((agent) => {
      const matchesSearch =
        agent.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        agent.strategy.toLowerCase().includes(searchQuery.toLowerCase())
      const matchesRisk = riskFilter === "all" || agent.risk === riskFilter
      return matchesSearch && matchesRisk
    })
    .sort((a, b) => {
      switch (sortBy) {
        case "score":
          return b.score - a.score
        case "sharpe":
          return b.sharpe - a.sharpe
        case "pnl":
          return b.pnl - a.pnl
        case "allocation":
          return b.allocation - a.allocation
        case "drawdown":
          return Math.abs(a.drawdown) - Math.abs(b.drawdown)
        default:
          return b.score - a.score
      }
    })

  const cardAgents = filteredAgents.map(agentToCardData)
  const activeCount = agents.filter((a) => a.status === "active").length
  const avgSharpe = agents.length
    ? agents.reduce((s, a) => s + a.sharpe, 0) / agents.length
    : 0
  const totalStake = agents.reduce((s, a) => s + a.stake, 0)

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
                {loading ? "Loading agents…" : `${agents.length} agents competing for capital allocation`}
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
            <div className="text-2xl font-bold font-mono text-foreground">
              {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : agents.length}
            </div>
          </div>
          <div className="glass rounded-xl p-4 border border-border/30">
            <div className="text-xs text-muted-foreground mb-1">Active Trading</div>
            <div className="text-2xl font-bold font-mono text-accent">{activeCount}</div>
          </div>
          <div className="glass rounded-xl p-4 border border-border/30">
            <div className="text-xs text-muted-foreground mb-1">Avg. Sharpe</div>
            <div className="text-2xl font-bold font-mono text-foreground">
              {avgSharpe.toFixed(2)}
            </div>
          </div>
          <div className="glass rounded-xl p-4 border border-border/30">
            <div className="text-xs text-muted-foreground mb-1">Total Stake</div>
            <div className="text-2xl font-bold font-mono text-foreground">
              ${(totalStake / 1_000_000).toFixed(2)}M
            </div>
          </div>
        </div>

        {/* Error banner */}
        {error && (
          <div className="flex items-center gap-2 mb-6 p-4 rounded-lg bg-destructive/10 border border-destructive/30 text-destructive text-sm">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            Backend unavailable — showing cached data. ({error})
          </div>
        )}

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
                  <SelectItem value="pnl">PnL</SelectItem>
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

        {/* Results header */}
        <div className="mb-4 flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Showing {cardAgents.length} of {agents.length} agents
          </p>
          <div className="flex gap-2">
            {riskFilter !== "all" && (
              <Badge variant="secondary" className="text-xs">
                {riskFilter}
                <button onClick={() => setRiskFilter("all")} className="ml-1 hover:text-foreground">
                  ×
                </button>
              </Badge>
            )}
          </div>
        </div>

        {/* Loading state */}
        {loading && (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-8 h-8 animate-spin text-primary" />
          </div>
        )}

        {/* Agent Grid/List */}
        {!loading && viewMode === "grid" ? (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {cardAgents.map((agent) => (
              <AgentCard key={agent.id} agent={agent} variant="card" />
            ))}
          </div>
        ) : (
          !loading && (
            <div className="space-y-3">
              {cardAgents.map((agent) => (
                <AgentCard key={agent.id} agent={agent} variant="row" />
              ))}
            </div>
          )
        )}

        {!loading && cardAgents.length === 0 && (
          <div className="text-center py-16">
            <p className="text-muted-foreground">No agents found matching your criteria.</p>
          </div>
        )}
      </div>
    </div>
  )
}
