"use client"

import { cn } from "@/lib/utils"

interface StatusBadgeProps {
  status: "live" | "beta" | "coming" | "maintenance"
  className?: string
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const styles = {
    live: "bg-accent/20 text-accent border-accent/30",
    beta: "bg-primary/20 text-primary border-primary/30",
    coming: "bg-muted/30 text-muted-foreground border-border/30",
    maintenance: "bg-destructive/20 text-destructive border-destructive/30",
  }

  const labels = {
    live: "Live",
    beta: "Beta",
    coming: "Coming Soon",
    maintenance: "Maintenance",
  }

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-medium uppercase tracking-wider border",
        styles[status],
        className
      )}
    >
      {status === "live" && <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />}
      {labels[status]}
    </span>
  )
}
