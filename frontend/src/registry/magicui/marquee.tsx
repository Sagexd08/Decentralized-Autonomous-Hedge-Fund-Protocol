import type { ReactNode } from 'react'

import { cn } from '../../utils/cn'

type MarqueeProps = {
  children: ReactNode
  className?: string
  reverse?: boolean
}

export function Marquee({ children, className, reverse = false }: MarqueeProps) {
  return (
    <div className={cn('relative overflow-hidden', className)}>
      <div
        className={cn(
          'flex min-w-max items-center gap-4 whitespace-nowrap will-change-transform',
          reverse ? 'animate-[marquee-reverse_20s_linear_infinite]' : 'animate-[marquee_20s_linear_infinite]',
        )}
      >
        {children}
        {children}
      </div>
    </div>
  )
}
