"use client"

import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Clock, CheckCircle2, XCircle, AlertTriangle } from "lucide-react"

export interface ProposalData {
  id: string
  title: string
  description: string
  status: "active" | "passed" | "failed" | "vetoed"
  forPercentage: number
  againstPercentage: number
  quorum: number
  quorumRequired: number
  endTime: string
  category: string
  author: string
}

interface ProposalCardProps {
  proposal: ProposalData
  className?: string
}

export function ProposalCard({ proposal, className }: ProposalCardProps) {
  const statusStyles = {
    active: {
      icon: Clock,
      label: "Active",
      color: "text-primary",
      bg: "bg-primary/10",
      border: "border-primary/30",
    },
    passed: {
      icon: CheckCircle2,
      label: "Passed",
      color: "text-accent",
      bg: "bg-accent/10",
      border: "border-accent/30",
    },
    failed: {
      icon: XCircle,
      label: "Failed",
      color: "text-destructive",
      bg: "bg-destructive/10",
      border: "border-destructive/30",
    },
    vetoed: {
      icon: AlertTriangle,
      label: "Vetoed",
      color: "text-chart-4",
      bg: "bg-chart-4/10",
      border: "border-chart-4/30",
    },
  }

  const style = statusStyles[proposal.status]
  const Icon = style.icon
  const quorumPercent = (proposal.quorum / proposal.quorumRequired) * 100

  return (
    <div
      className={cn(
        "glass rounded-xl p-5 border border-border/30 hover:border-primary/30 transition-colors",
        className
      )}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-mono text-primary">{proposal.id}</span>
            <Badge variant="outline" className="text-[10px]">
              {proposal.category}
            </Badge>
          </div>
          <h3 className="font-semibold text-foreground">{proposal.title}</h3>
          <p className="text-sm text-muted-foreground mt-1 line-clamp-2">
            {proposal.description}
          </p>
        </div>
        <Badge variant="outline" className={cn("shrink-0", style.color, style.bg, style.border)}>
          <Icon className="w-3 h-3 mr-1" />
          {style.label}
        </Badge>
      </div>

      {/* Vote bars */}
      <div className="mb-4">
        <div className="flex items-center justify-between text-sm mb-2">
          <span className="text-accent">For: {proposal.forPercentage.toFixed(1)}%</span>
          <span className="text-destructive">Against: {proposal.againstPercentage.toFixed(1)}%</span>
        </div>
        <div className="h-3 rounded-full bg-destructive/30 overflow-hidden">
          <div
            className="h-full bg-accent rounded-full transition-all"
            style={{ width: `${proposal.forPercentage}%` }}
          />
        </div>
      </div>

      {/* Quorum */}
      <div className="mb-4">
        <div className="flex items-center justify-between text-xs mb-1">
          <span className="text-muted-foreground">Quorum</span>
          <span className="font-mono text-foreground">
            {proposal.quorum}% / {proposal.quorumRequired}%
          </span>
        </div>
        <Progress value={Math.min(quorumPercent, 100)} className="h-1" />
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <div className="flex items-center gap-2">
          <Clock className="w-3 h-3" />
          {proposal.status === "active" ? `Ends in ${proposal.endTime}` : proposal.endTime}
        </div>
        <span className="font-mono">{proposal.author}</span>
      </div>
    </div>
  )
}
