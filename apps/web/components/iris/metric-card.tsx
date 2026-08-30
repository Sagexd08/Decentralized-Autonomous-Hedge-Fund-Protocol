"use client"

import { cn } from "@/lib/utils"
import { ArrowUp, ArrowDown, Minus, LucideIcon } from "lucide-react"
import { createElement, isValidElement, ReactNode, type ElementType } from "react"

interface MetricCardProps {
  title: string
  value: string
  // Support both object format and simple number format
  change?: number | {
    value: number
    label?: string
  }
  changeLabel?: string
  subtitle?: string
  // Support both LucideIcon and JSX elements
  icon?: LucideIcon | ReactNode
  variant?: "default" | "cyan" | "emerald" | "amber" | "blue"
  size?: "sm" | "md" | "lg"
  className?: string
}

export function MetricCard({
  title,
  value,
  change,
  changeLabel,
  subtitle,
  icon,
  variant = "default",
  size = "md",
  className,
}: MetricCardProps) {
  const variantStyles = {
    default: "border-border/50 bg-card/92",
    cyan: "border-border/50 bg-card/92",
    emerald: "border-border/50 bg-card/92",
    amber: "border-border/50 bg-card/92",
    blue: "border-border/50 bg-card/92",
  }

  const iconStyles = {
    default: "bg-secondary text-foreground/70",
    cyan: "bg-secondary text-primary",
    emerald: "bg-secondary text-accent",
    amber: "bg-secondary text-destructive",
    blue: "bg-secondary text-chart-3",
  }

  const sizeStyles = {
    sm: "p-3",
    md: "p-4",
    lg: "p-6",
  }

  const valueSizes = {
    sm: "text-xl",
    md: "text-2xl",
    lg: "text-4xl",
  }

  // Normalize change to object format
  const normalizedChange = typeof change === "number" 
    ? { value: change, label: changeLabel } 
    : change

  // Render icon - handle both LucideIcon and ReactNode
  const renderIcon = () => {
    if (!icon) return null

    if (isValidElement(icon)) {
      return (
        <div className={cn("flex h-8 w-8 items-center justify-center rounded-lg", iconStyles[variant])}>
          {icon}
        </div>
      )
    }

    const IconComponent = icon as LucideIcon | ElementType
    return (
      <div className={cn("flex h-8 w-8 items-center justify-center rounded-lg", iconStyles[variant])}>
        {createElement(IconComponent, { className: "w-4 h-4" })}
      </div>
    )
  }

  return (
    <div
      className={cn(
        "glass rounded-xl border",
        variantStyles[variant],
        sizeStyles[size],
        className
      )}
    >
      <div className="flex items-start justify-between mb-2">
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
          {title}
        </span>
        {renderIcon()}
      </div>

      <div className={cn("font-bold text-foreground", valueSizes[size])}>
        {value}
      </div>

      {subtitle && (
        <div className="text-xs text-muted-foreground mt-1">{subtitle}</div>
      )}

      {normalizedChange && (
        <div className="flex items-center gap-1 mt-2">
          {normalizedChange.value > 0 ? (
            <ArrowUp className="w-3 h-3 text-accent" />
          ) : normalizedChange.value < 0 ? (
            <ArrowDown className="w-3 h-3 text-destructive" />
          ) : (
            <Minus className="w-3 h-3 text-muted-foreground" />
          )}
          <span
            className={cn(
              "text-xs font-medium",
              normalizedChange.value > 0
                ? "text-accent"
                : normalizedChange.value < 0
                ? "text-destructive"
                : "text-muted-foreground"
            )}
          >
            {normalizedChange.value > 0 ? "+" : ""}
            {typeof normalizedChange.value === "number" && normalizedChange.value % 1 !== 0 
              ? normalizedChange.value.toFixed(1) 
              : normalizedChange.value}%
          </span>
          {normalizedChange.label && (
            <span className="text-xs text-muted-foreground">{normalizedChange.label}</span>
          )}
        </div>
      )}
    </div>
  )
}
