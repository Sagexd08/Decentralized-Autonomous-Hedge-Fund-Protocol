import { motion } from 'framer-motion'

import { cn } from '../../utils/cn'

type AnimatedListDemoProps = {
  className?: string
  items: Array<{ label: string; value: string }>
}

export default function AnimatedListDemo({ className, items }: AnimatedListDemoProps) {
  return (
    <div className={cn('space-y-3', className)}>
      {items.map((item, index) => (
        <motion.div
          key={item.label}
          initial={{ opacity: 0, y: 18 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-100px' }}
          transition={{ duration: 0.45, delay: index * 0.08 }}
          className="liquid-glass flex items-center justify-between rounded-[1.5rem] px-4 py-3"
        >
          <span className="text-xs uppercase tracking-[0.28em] text-white/40">{item.label}</span>
          <span className="text-sm text-white/80">{item.value}</span>
        </motion.div>
      ))}
    </div>
  )
}
