import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { useInViewAnimation } from '../hooks/useInViewAnimation'

const TICKERS = [
  { sym: 'BTC', price: 69_241.80, chg: +2.34 },
  { sym: 'ETH', price:  3_712.55, chg: +1.87 },
  { sym: 'SOL', price:   182.40,  chg: -0.62 },
  { sym: 'BNB', price:   601.12,  chg: +0.44 },
  { sym: 'ARB', price:     1.28,  chg: -1.15 },
  { sym: 'AAVE', price:  106.75,  chg: +3.20 },
]

const NEWS = [
  { time: '14:32', title: 'Fed signals further rate pause — risk assets rally', tag: 'MACRO' },
  { time: '13:18', title: 'Ethereum L2 TVL crosses $40B milestone', tag: 'CHAIN' },
  { time: '12:05', title: 'DACAP Agent_07 rebalanced into ARB liquidity pool', tag: 'AGENT' },
  { time: '11:47', title: 'VIX drops to 12.4 — lowest since Jan 2024', tag: 'RISK' },
  { time: '10:30', title: 'On-chain lending rates tighten ahead of expiry', tag: 'DEFI' },
]

const SENTIMENT = [
  { label: 'Market Sentiment', value: 73, color: 'bg-white' },
  { label: 'Agent Confidence',  value: 88, color: 'bg-white/80' },
  { label: 'Risk Appetite',     value: 61, color: 'bg-white/60' },
]

const TAG_STYLES: Record<string, string> = {
  MACRO:  'text-white/60 border-white/20',
  CHAIN:  'text-white/60 border-white/20',
  AGENT:  'text-white/90 border-white/40',
  RISK:   'text-white/60 border-white/20',
  DEFI:   'text-white/60 border-white/20',
}

function TickerStrip() {
  const ref = useRef<HTMLDivElement>(null)

  const items = [...TICKERS, ...TICKERS]

  return (
    <div className="relative overflow-hidden border-y border-white/8 py-3">
      <div
        ref={ref}
        className="flex gap-12 animate-[marquee_28s_linear_infinite] whitespace-nowrap"
        style={{ width: 'max-content' }}
      >
        {items.map((t, i) => (
          <span key={i} className="flex items-center gap-2 text-xs font-['Space_Grotesk',sans-serif] tracking-wide">
            <span className="text-white/50">{t.sym}</span>
            <span className="text-white">${t.price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
            <span className={t.chg >= 0 ? 'text-white/70' : 'text-white/40'}>
              {t.chg >= 0 ? '+' : ''}{t.chg.toFixed(2)}%
            </span>
          </span>
        ))}
      </div>
    </div>
  )
}

export default function LandingIntelligenceHub() {
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
          className="mb-12"
        >
          <p className="mb-3 text-[10px] uppercase tracking-[0.38em] text-white/35">
            Global Intelligence Hub
          </p>
          <h2 className="text-4xl font-medium tracking-tight text-white sm:text-5xl">
            Market Consciousness
          </h2>
        </motion.div>

        <TickerStrip />

        <div className="mt-10 grid gap-6 lg:grid-cols-[1fr_320px]">
          {}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={isInView ? { opacity: 1, x: 0 } : { opacity: 0, x: -20 }}
            transition={{ duration: 0.8, delay: 0.15 }}
            className="flex flex-col gap-0 divide-y divide-white/5 border border-white/8"
          >
            {NEWS.map((item, i) => (
              <div
                key={i}
                className="flex items-start gap-5 px-6 py-4 transition hover:bg-white/[0.02]"
              >
                <span className="mt-0.5 shrink-0 font-['Space_Grotesk',sans-serif] text-xs text-white/25">
                  {item.time}
                </span>
                <p className="flex-1 text-sm leading-6 text-white/70">
                  {item.title}
                </p>
                <span
                  className={`shrink-0 self-start border px-2 py-0.5 font-['Space_Grotesk',sans-serif] text-[10px] tracking-widest ${TAG_STYLES[item.tag] ?? 'text-white/40 border-white/15'}`}
                >
                  {item.tag}
                </span>
              </div>
            ))}
          </motion.div>

          {}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={isInView ? { opacity: 1, x: 0 } : { opacity: 0, x: 20 }}
            transition={{ duration: 0.8, delay: 0.25 }}
            className="flex flex-col gap-5 border border-white/8 p-6"
          >
            <p className="text-[10px] uppercase tracking-[0.32em] text-white/35">
              System Sentiment
            </p>

            {SENTIMENT.map((s) => (
              <div key={s.label} className="flex flex-col gap-2">
                <div className="flex items-center justify-between">
                  <span className="font-['Space_Grotesk',sans-serif] text-xs text-white/60">
                    {s.label}
                  </span>
                  <span className="font-['Space_Grotesk',sans-serif] text-xs text-white/90">
                    {s.value}
                  </span>
                </div>
                <div className="h-px w-full bg-white/8">
                  <motion.div
                    className={`h-full ${s.color}`}
                    initial={{ width: 0 }}
                    animate={isInView ? { width: `${s.value}%` } : { width: 0 }}
                    transition={{ duration: 1.2, delay: 0.4, ease: [0.16, 1, 0.3, 1] }}
                  />
                </div>
              </div>
            ))}

            <div className="mt-4 border-t border-white/8 pt-5">
              <p className="text-[10px] uppercase tracking-[0.32em] text-white/35 mb-4">Live Signals</p>
              {[
                { label: 'Agents Active', value: '12 / 12' },
                { label: 'Open Positions', value: '47' },
                { label: 'Pending Rebalances', value: '3' },
              ].map((row) => (
                <div key={row.label} className="flex items-center justify-between py-2">
                  <span className="text-xs text-white/40">{row.label}</span>
                  <span className="font-['Space_Grotesk',sans-serif] text-xs text-white">{row.value}</span>
                </div>
              ))}
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  )
}
