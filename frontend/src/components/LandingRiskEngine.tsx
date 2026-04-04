import { motion } from 'framer-motion'
import { useInViewAnimation } from '../hooks/useInViewAnimation'
import { ShieldCheck, Zap, Scale } from 'lucide-react'

const PILLARS = [
  {
    icon: <ShieldCheck size={20} className="text-white/70" />,
    title: 'Continuous Risk Monitoring',
    desc: 'Every position is assessed against VaR, CVaR, and drawdown thresholds — 24 × 7 with zero latency.',
  },
  {
    icon: <Zap size={20} className="text-white/70" />,
    title: 'Monte Carlo Simulation',
    desc: 'Thousands of portfolio path simulations executed per minute to stress-test against tail events.',
  },
  {
    icon: <Scale size={20} className="text-white/70" />,
    title: 'Auto-Rebalancing',
    desc: 'Agents trigger collateral adjustments the instant risk parameters breach pre-defined thresholds.',
  },
]

const GAUGE_DATA = [
  { label: 'Portfolio VaR (1d 95%)', value: '−2.1%', bar: 42 },
  { label: 'Max Drawdown (30d)',      value: '−4.7%', bar: 58 },
  { label: 'Leverage Ratio',          value: '1.38×', bar: 34 },
  { label: 'Liquidation Buffer',      value: '+187%', bar: 82 },
]

export default function LandingRiskEngine() {
  const { ref, isInView } = useInViewAnimation('-60px')

  return (
    <section
      className="border-t border-white/5 bg-black py-24 px-4 sm:px-6 lg:px-8"
      ref={ref}
    >
      <div className="mx-auto max-w-7xl">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 24 }}
          transition={{ duration: 0.8 }}
          className="mb-14 grid gap-8 lg:grid-cols-[1fr_1fr]"
        >
          <div>
            <p className="mb-3 text-[10px] uppercase tracking-[0.38em] text-white/35">
              Risk Engine
            </p>
            <h2 className="text-4xl font-medium tracking-tight text-white sm:text-5xl">
              Precision{' '}
              <span className="font-['Instrument_Serif'] italic font-normal">
                Risk Management
              </span>
            </h2>
          </div>
          <p className="self-end text-sm leading-7 text-white/55 lg:pt-8">
            DACAP's proprietary risk layer continuously monitors exposure across every deployed agent and protocol,
            ensuring the portfolio stays within defined risk parameters at all times.
          </p>
        </motion.div>

        <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
          {/* Pillars */}
          <div className="flex flex-col gap-4">
            {PILLARS.map((p, i) => (
              <motion.div
                key={p.title}
                initial={{ opacity: 0, x: -20 }}
                animate={isInView ? { opacity: 1, x: 0 } : { opacity: 0, x: -20 }}
                transition={{ duration: 0.7, delay: i * 0.12 }}
                className="flex gap-5 border border-white/8 p-6"
              >
                <div className="mt-1 h-10 w-10 shrink-0 border border-white/10 flex items-center justify-center">
                  {p.icon}
                </div>
                <div>
                  <h3 className="mb-2 text-sm font-medium text-white">{p.title}</h3>
                  <p className="text-sm leading-6 text-white/45">{p.desc}</p>
                </div>
              </motion.div>
            ))}
          </div>

          {/* Gauge Panel */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={isInView ? { opacity: 1, x: 0 } : { opacity: 0, x: 20 }}
            transition={{ duration: 0.8, delay: 0.2 }}
            className="border border-white/8 p-6"
          >
            <p className="mb-6 text-[10px] uppercase tracking-[0.32em] text-white/35">
              Live Risk Metrics
            </p>
            <div className="flex flex-col gap-6">
              {GAUGE_DATA.map((g) => (
                <div key={g.label} className="flex flex-col gap-2">
                  <div className="flex items-center justify-between">
                    <span className="font-['Space_Grotesk',sans-serif] text-xs text-white/55">
                      {g.label}
                    </span>
                    <span className="font-['Space_Grotesk',sans-serif] text-sm text-white">
                      {g.value}
                    </span>
                  </div>
                  <div className="h-px w-full bg-white/8">
                    <motion.div
                      className="h-full bg-white/50"
                      initial={{ width: 0 }}
                      animate={isInView ? { width: `${g.bar}%` } : { width: 0 }}
                      transition={{ duration: 1.2, delay: 0.5, ease: [0.16, 1, 0.3, 1] }}
                    />
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-8 border-t border-white/8 pt-6">
              <div className="flex items-center gap-2">
                <span className="relative flex h-2 w-2">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-white opacity-60"></span>
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-white"></span>
                </span>
                <span className="font-['Space_Grotesk',sans-serif] text-xs tracking-widest text-white/40 uppercase">
                  Risk Engine Online
                </span>
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  )
}
