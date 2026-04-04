import { motion } from 'framer-motion'
import { useInViewAnimation } from '../hooks/useInViewAnimation'
import { useNavigate } from 'react-router-dom'

export default function LandingCTA() {
  const { ref, isInView } = useInViewAnimation('-40px')
  const navigate = useNavigate()

  return (
    <section
      className="relative overflow-hidden border-t border-white/5 bg-black py-32 px-4 sm:px-6 lg:px-8"
      ref={ref}
    >
      {}
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_60%_50%_at_50%_60%,rgba(255,255,255,0.05)_0%,transparent_100%)]" />

      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 30 }}
        transition={{ duration: 1, ease: [0.16, 1, 0.3, 1] }}
        className="relative z-10 mx-auto max-w-4xl text-center"
      >
        <p className="mb-5 text-[10px] uppercase tracking-[0.38em] text-white/35">
          Begin Allocation
        </p>
        <h2 className="mb-6 font-['Instrument_Serif'] text-5xl italic font-normal leading-[1.08] text-white sm:text-7xl">
          Let Capital Work<br />While You Sleep.
        </h2>
        <p className="mx-auto mb-12 max-w-xl text-base leading-7 text-white/45">
          DACAP agents operate continuously across DeFi protocols, equity bridges, and liquidity pools — optimising returns, managing risk, and executing with machine precision.
        </p>

        <div className="flex flex-col items-center justify-center gap-4 sm:flex-row">
          <button
            onClick={() => navigate('/dashboard')}
            className="h-12 w-48 bg-white text-black text-sm font-medium tracking-wide transition hover:bg-white/90"
          >
            Launch Terminal
          </button>
          <button
            onClick={() => navigate('/dashboard')}
            className="h-12 w-48 border border-white/20 text-sm font-medium tracking-wide text-white/70 transition hover:border-white/40 hover:text-white"
          >
            Read Whitepaper
          </button>
        </div>
      </motion.div>
    </section>
  )
}
