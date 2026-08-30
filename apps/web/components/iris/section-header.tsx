"use client"

import { cn } from "@/lib/utils"

interface SectionHeaderProps {
  eyebrow?: string
  title: string
  description?: string
  align?: "left" | "center"
  className?: string
  children?: React.ReactNode
}

export function SectionHeader({
  eyebrow,
  title,
  description,
  align = "left",
  className,
  children,
}: SectionHeaderProps) {
  return (
    <div
      className={cn(
        "mb-8",
        align === "center" && "text-center",
        className
      )}
    >
      {eyebrow && (
        <div className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
          {eyebrow}
        </div>
      )}
      <h2 className="mb-3 text-2xl font-semibold text-foreground md:text-3xl lg:text-4xl">
        {title}
      </h2>
      {description && (
        <p className={cn(
          "text-muted-foreground text-lg max-w-3xl",
          align === "center" && "mx-auto"
        )}>
          {description}
        </p>
      )}
      {children}
    </div>
  )
}
