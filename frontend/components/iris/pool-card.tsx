"use client"

import Link from "next/link"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Shield, Zap, Flame, TrendingUp, Users } from "lucide-react"

export interface PoolData {
  id: string
  name: "Conservative" | "Balanced" | "Aggressive"
  tvl: number
  apy: number
  volatilityCap: number
  capacityUsed: number
  drawdownLimit: number
  activeAgents: number
  rollingVolatility: number
}

interface PoolCardProps {
  pool: PoolData
  className?: string
}

export function PoolCard({ pool, className }: PoolCardProps) {
  const poolStyles = {
    Conservative: {
      icon: Shield,
      gradient: "from-chart-3/20 to-chart-3/5",
      border: "border-chart-3/30 hover:border-chart-3/50",
      accent: "text-chart-3",
      bg: "bg-chart-3",
    },
    Balanced: {
      icon: Zap,
      gradient: "from-primary/20 to-primary/5",
      border: "border-primary/30 hover:border-primary/50",
      accent: "text-primary",
      bg: "bg-primary",
    },
    Aggressive: {
      icon: Flame,
      gradient: "from-destructive/20 to-destructive/5",
      border: "border-destructive/30 hover:border-destructive/50",
      accent: "text-destructive",
      bg: "bg-destructive",
    },
  }

  const style = poolStyles[pool.name]
  const Icon = style.icon

  return (
    <Link
      href={`/risk-pools?pool=${pool.id}`}
      className={cn(
        "glass rounded-xl p-6 hover:bg-muted/30 transition-all border group block",
        style.border,
        className
      )}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className={cn("w-12 h-12 rounded-xl flex items-center justify-center bg-gradient-to-br", style.gradient)}>
            <Icon className={cn("w-6 h-6", style.accent)} />
          </div>
          <div>
            <h3 className="font-semibold text-lg text-foreground">{pool.name}</h3>
            <p className="text-sm text-muted-foreground">Risk Pool</p>
          </div>
        </div>
        <Badge variant="outline" className={cn("font-mono", style.accent)}>
          {pool.apy.toFixed(1)}% APY
        </Badge>
      </div>

      {/* TVL */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm text-muted-foreground">Total Value Locked</span>
          <TrendingUp className="w-4 h-4 text-accent" />
        </div>
        <div className="text-3xl font-bold font-mono text-foreground">
          ${(pool.tvl / 1000000).toFixed(2)}M
        </div>
      </div>

      {/* Capacity */}
      <div className="mb-4">
        <div className="flex items-center justify-between text-sm mb-2">
          <span className="text-muted-foreground">Capacity</span>
          <span className="font-mono text-foreground">{pool.capacityUsed.toFixed(0)}%</span>
        </div>
        <Progress value={pool.capacityUsed} className="h-2" />
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 gap-4 pt-4 border-t border-border/30">
        <div>
          <div className="text-xs text-muted-foreground mb-1">Vol Cap</div>
          <div className="font-mono font-semibold text-foreground">{pool.volatilityCap}%</div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground mb-1">Max DD</div>
          <div className="font-mono font-semibold text-destructive">-{pool.drawdownLimit}%</div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground mb-1">Rolling Vol</div>
          <div className="font-mono font-semibold text-foreground">{pool.rollingVolatility.toFixed(1)}%</div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground mb-1 flex items-center gap-1">
            <Users className="w-3 h-3" />
            Agents
          </div>
          <div className="font-mono font-semibold text-foreground">{pool.activeAgents}</div>
        </div>
      </div>
    </Link>
  )
}
