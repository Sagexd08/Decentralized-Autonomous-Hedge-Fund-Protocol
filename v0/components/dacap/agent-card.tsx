"use client"

import Link from "next/link"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { TrendingUp, TrendingDown, Activity, Zap } from "lucide-react"

export interface AgentData {
  id: string
  name: string
  strategy: string
  riskLevel: "Conservative" | "Balanced" | "Aggressive"
  score: number
  sharpe: number
  pnl: number
  pnlPercent: number
  drawdown: number
  allocation: number
  stake: number
  isActive: boolean
  badges?: string[]
}

interface AgentCardProps {
  agent: AgentData
  variant?: "card" | "row"
  className?: string
}

export function AgentCard({ agent, variant = "card", className }: AgentCardProps) {
  const riskColors = {
    Conservative: "bg-chart-3/20 text-chart-3 border-chart-3/30",
    Balanced: "bg-primary/20 text-primary border-primary/30",
    Aggressive: "bg-destructive/20 text-destructive border-destructive/30",
  }

  if (variant === "row") {
    return (
      <Link
        href={`/agents/${agent.id}`}
        className={cn(
          "glass rounded-lg p-4 flex items-center gap-4 hover:bg-muted/30 transition-colors border border-border/30",
          className
        )}
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-foreground truncate">{agent.name}</span>
            {agent.isActive && (
              <span className="w-2 h-2 rounded-full bg-accent animate-pulse" />
            )}
          </div>
          <span className="text-xs text-muted-foreground">{agent.strategy}</span>
        </div>

        <Badge variant="outline" className={cn("text-xs", riskColors[agent.riskLevel])}>
          {agent.riskLevel}
        </Badge>

        <div className="text-right">
          <div className={cn("font-mono font-semibold", agent.pnl >= 0 ? "text-accent" : "text-destructive")}>
            {agent.pnl >= 0 ? "+" : ""}{agent.pnlPercent.toFixed(2)}%
          </div>
          <div className="text-xs text-muted-foreground">PnL</div>
        </div>

        <div className="text-right">
          <div className="font-mono font-semibold text-foreground">{agent.sharpe.toFixed(2)}</div>
          <div className="text-xs text-muted-foreground">Sharpe</div>
        </div>

        <div className="text-right min-w-[80px]">
          <div className="font-mono font-semibold text-foreground">{agent.allocation.toFixed(1)}%</div>
          <Progress value={agent.allocation} className="h-1 mt-1" />
        </div>
      </Link>
    )
  }

  return (
    <Link
      href={`/agents/${agent.id}`}
      className={cn(
        "glass rounded-xl p-5 hover:bg-muted/30 transition-all border border-border/30 hover:border-primary/30 group block",
        className
      )}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-foreground group-hover:text-primary transition-colors">
              {agent.name}
            </h3>
            {agent.isActive && (
              <span className="w-2 h-2 rounded-full bg-accent animate-pulse" />
            )}
          </div>
          <p className="text-sm text-muted-foreground mt-0.5">{agent.strategy}</p>
        </div>
        <Badge variant="outline" className={cn("text-xs", riskColors[agent.riskLevel])}>
          {agent.riskLevel}
        </Badge>
      </div>

      {/* Badges */}
      {agent.badges && agent.badges.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-4">
          {agent.badges.map((badge) => (
            <Badge key={badge} variant="secondary" className="text-[10px] bg-primary/10 text-primary border-0">
              {badge}
            </Badge>
          ))}
        </div>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div>
          <div className="text-xs text-muted-foreground mb-1">Score</div>
          <div className="font-mono font-semibold text-foreground">{agent.score.toFixed(0)}</div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground mb-1">Sharpe</div>
          <div className="font-mono font-semibold text-foreground">{agent.sharpe.toFixed(2)}</div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground mb-1">PnL</div>
          <div className={cn("font-mono font-semibold flex items-center gap-1", agent.pnl >= 0 ? "text-accent" : "text-destructive")}>
            {agent.pnl >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
            {agent.pnl >= 0 ? "+" : ""}{agent.pnlPercent.toFixed(2)}%
          </div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground mb-1">Drawdown</div>
          <div className="font-mono font-semibold text-destructive">-{agent.drawdown.toFixed(2)}%</div>
        </div>
      </div>

      {/* Allocation */}
      <div>
        <div className="flex items-center justify-between text-xs mb-1">
          <span className="text-muted-foreground">Allocation</span>
          <span className="font-mono text-foreground">{agent.allocation.toFixed(1)}%</span>
        </div>
        <Progress value={agent.allocation} className="h-2" />
      </div>

      {/* Stake */}
      <div className="mt-3 pt-3 border-t border-border/30 flex items-center justify-between">
        <span className="text-xs text-muted-foreground">Stake</span>
        <span className="font-mono text-sm text-foreground">${agent.stake.toLocaleString()}</span>
      </div>
    </Link>
  )
}
