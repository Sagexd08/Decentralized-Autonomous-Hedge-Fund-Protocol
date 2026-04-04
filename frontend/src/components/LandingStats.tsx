import { motion } from 'framer-motion'
import { useInViewAnimation } from '../hooks/useInViewAnimation'

const STATS = [
  { label: 'Assets Under Management',   value: '$847M',     sub: '+12.4% this month' },
  { label: 'AI Agents Operating',        value: '12',        sub: '100% uptime' },
  { label: 'Annualised Return',          value: '31.7%',     sub: 'vs 8.2% benchmark' },
  { label: 'Sharpe Ratio',              value: '2.84',      sub: 'Risk-adjusted alpha' },
  { label: 'Protocols Connected',       value: '40+',       sub: 'Live integrations' },
  { label: 'Governance Proposals',      value: '128',       sub: 'Community driven' },
]

export default function LandingStats() {
  const { ref, isInView } = useInViewAnimation('-50px')

  return (
    <section
      className="border-t border-white/5 bg-black py-20 px-4 sm:px-6 lg:px-8"
      ref={ref}
    >
      <div className="mx-auto max-w-7xl">
        <div className="grid grid-cols-2 gap-px border border-white/8 bg-white/8 md:grid-cols-3">
          {STATS.map((s, i) => (
            <motion.div
              key={s.label}
              initial={{ opacity: 0, y: 16 }}
              animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 16 }}
              transition={{ duration: 0.7, delay: i * 0.07 }}
              className="flex flex-col justify-between gap-3 bg-black px-6 py-8"
            >
              <p className="text-[10px] uppercase tracking-[0.32em] text-white/35">{s.label}</p>
              <div>
                <p className="font-['Instrument_Serif'] text-4xl italic leading-none text-white sm:text-5xl">
                  {s.value}
                </p>
                <p className="mt-2 font-['Space_Grotesk',sans-serif] text-xs text-white/35">
                  {s.sub}
                </p>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}
