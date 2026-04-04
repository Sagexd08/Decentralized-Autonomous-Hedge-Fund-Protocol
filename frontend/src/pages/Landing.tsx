import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { Command } from 'lucide-react'

import { Navbar } from '../components/Navbar'
import { VideoSection } from '../components/VideoSection'
import { BentoSection } from '../components/BentoSection'
import { Philosophy } from '../components/Philosophy'
import { Services } from '../components/Services'
import LandingStats from '../components/LandingStats'
import LandingIntelligenceHub from '../components/LandingIntelligenceHub'
import LandingRiskEngine from '../components/LandingRiskEngine'
import LandingCTA from '../components/LandingCTA'
import LandingCommandPalette from '../components/LandingCommandPalette'

function Hero() {
  const navigate = useNavigate()
  const videoRef = useRef<HTMLVideoElement>(null)
  const [paletteOpen, setPaletteOpen] = useState(false)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setPaletteOpen((v) => !v)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  useEffect(() => {
    const v = videoRef.current
    if (!v) return
    const play = v.play()
    if (play && 'catch' in play) play.catch(() => undefined)
  }, [])

  return (
    <>
      <section className="relative flex min-h-screen flex-col overflow-hidden bg-black">
        {}
        <div className="pointer-events-none absolute inset-0">
          <video
            ref={videoRef}
            src="https://videos.pexels.com/video-files/856988/856988-hd_1920_1080_25fps.mp4"
            muted
            loop
            playsInline
            autoPlay
            preload="auto"
            className="absolute inset-0 h-full w-full object-cover opacity-25 scale-105"
          />
          <div className="absolute inset-0 bg-gradient-to-b from-black/70 via-black/40 to-black" />
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_50%_at_50%_-10%,rgba(255,255,255,0.07),transparent)]" />
        </div>

        {}
        <div className="relative z-20">
          <Navbar />
        </div>

        {}
        <div className="relative z-10 mx-auto flex flex-1 w-full max-w-7xl flex-col justify-center px-4 pb-24 pt-8 sm:px-6 lg:px-8">
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 1, ease: [0.16, 1, 0.3, 1] }}
            className="max-w-4xl"
          >
            {}
            <div className="mb-8 flex items-center gap-3">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-white opacity-50" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-white" />
              </span>
              <span className="font-['Space_Grotesk',sans-serif] text-[10px] uppercase tracking-[0.4em] text-white/40">
                Autonomous Protocol · Live
              </span>
            </div>

            <h1 className="font-['Instrument_Serif'] text-6xl italic font-normal leading-[1.04] text-white sm:text-7xl lg:text-[7.5rem]">
              Decentralised<br />
              <span className="not-italic font-medium font-['Space_Grotesk',sans-serif] text-5xl sm:text-6xl lg:text-7xl tracking-tight">
                Autonomous
              </span>
              <br />
              Capital.
            </h1>

            <p className="mt-8 max-w-xl font-['Space_Grotesk',sans-serif] text-base leading-7 text-white/45 sm:text-lg">
              AI agents deployed on-chain, executing DeFi strategies across protocols — continuously, without human intervention.
            </p>

            <div className="mt-10 flex flex-col gap-4 sm:flex-row">
              <button
                onClick={() => navigate('/dashboard')}
                className="h-12 w-48 bg-white text-black font-['Space_Grotesk',sans-serif] text-sm font-medium tracking-wide transition hover:bg-white/90"
              >
                Launch Dashboard
              </button>

              <button
                onClick={() => setPaletteOpen(true)}
                className="flex h-12 items-center gap-3 border border-white/15 px-5 font-['Space_Grotesk',sans-serif] text-sm text-white/50 transition hover:border-white/30 hover:text-white/80"
              >
                <Command size={14} />
                <span>Command Palette</span>
                <span className="ml-1 rounded border border-white/15 px-1.5 py-0.5 text-[10px] text-white/30">
                  ⌘K
                </span>
              </button>
            </div>
          </motion.div>

          {}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 1, delay: 0.6 }}
            className="mt-20 flex flex-wrap items-center gap-x-8 gap-y-3 border-t border-white/8 pt-6"
          >
            {[
              { label: 'AUM', value: '$847M' },
              { label: 'Agents', value: '12' },
              { label: 'Protocols', value: '40+' },
              { label: '30d Return', value: '+31.7%' },
            ].map((m) => (
              <div key={m.label} className="flex items-baseline gap-2">
                <span className="font-['Space_Grotesk',sans-serif] text-[10px] uppercase tracking-[0.3em] text-white/30">
                  {m.label}
                </span>
                <span className="font-['Instrument_Serif'] text-2xl italic text-white">
                  {m.value}
                </span>
              </div>
            ))}
          </motion.div>
        </div>
      </section>

      {}
      <LandingCommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </>
  )
}

function Footer() {
  return (
    <footer className="border-t border-white/5 bg-black px-4 py-12 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl">
        <div className="flex flex-col items-start justify-between gap-8 sm:flex-row sm:items-center">
          <div>
            <p className="font-['Space_Grotesk',sans-serif] text-[10px] uppercase tracking-[0.4em] text-white/30">
              DACAP
            </p>
            <p className="mt-1 text-xs text-white/20">
              Decentralised Autonomous Capital Allocation Protocol
            </p>
          </div>
          <div className="flex gap-8">
            {['Docs', 'GitHub', 'Governance', 'Discord'].map((link) => (
              <a
                key={link}
                href="#"
                className="font-['Space_Grotesk',sans-serif] text-xs text-white/30 transition hover:text-white/60"
              >
                {link}
              </a>
            ))}
          </div>
          <p className="font-['Space_Grotesk',sans-serif] text-[10px] text-white/20">
            © 2024 DACAP. All rights reserved.
          </p>
        </div>
      </div>
    </footer>
  )
}

export default function Landing() {
  return (
    <main className="bg-black text-white selection:bg-white/10">
      <Hero />
      <LandingStats />
      <VideoSection />
      <LandingIntelligenceHub />
      <BentoSection />
      <LandingRiskEngine />
      <Philosophy />
      <Services />
      <LandingCTA />
      <Footer />
    </main>
  )
}
