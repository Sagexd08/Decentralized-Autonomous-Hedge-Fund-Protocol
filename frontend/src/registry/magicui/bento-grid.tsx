import type { ReactNode } from 'react'

import { cn } from '../../utils/cn'

type BentoGridProps = {
  children: ReactNode
  className?: string
}

type BentoCardProps = {
  name: string
  description: string
  className?: string
  background?: ReactNode
  icon?: ReactNode
  cta?: ReactNode
}

export function BentoGrid({ children, className }: BentoGridProps) {
  return <div className={cn('grid gap-6 md:grid-cols-2', className)}>{children}</div>
}

export function BentoCard({
  name,
  description,
  className,
  background,
  icon,
  cta,
}: BentoCardProps) {
  return (
    <article
      className={cn(
        'liquid-glass group relative overflow-hidden rounded-[2rem] border border-white/10 bg-white/[0.03] p-0',
        className,
      )}
    >
      {background}
      <div className="relative z-10 flex h-full flex-col justify-end gap-4 p-6 md:p-8">
        {icon ? <div className="text-white/75">{icon}</div> : null}
        <div className="space-y-3">
          <h3 className="text-2xl font-medium tracking-tight text-white">{name}</h3>
          <p className="max-w-md text-sm leading-6 text-white/60">{description}</p>
        </div>
        {cta ? <div className="pt-2">{cta}</div> : null}
      </div>
    </article>
  )
}
