<<<<<<< HEAD
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { motion, useInView } from 'framer-motion'
import {
  ArrowRight,
  ChevronRight,
  Instagram,
  Linkedin,
  Play,
  Twitter,
} from 'lucide-react'

import AnimatedListDemo from '../registry/example/animated-list-demo'
import { BentoCard, BentoGrid } from '../registry/magicui/bento-grid'
import { Marquee } from '../registry/magicui/marquee'
import { cn } from '../utils/cn'

const accentStyle = {
  fontFamily: '"Instrument Serif", serif',
  fontStyle: 'italic' as const,
}

const heroVideos = [
  'https://videos.pexels.com/video-files/856988/856988-hd_1920_1080_25fps.mp4',
  'https://videos.pexels.com/video-files/857195/857195-hd_1920_1080_25fps.mp4',
]

const sections = {
  featured: 'https://videos.pexels.com/video-files/3130284/3130284-hd_1920_1080_25fps.mp4',
  philosophy: 'https://videos.pexels.com/video-files/3129595/3129595-hd_1920_1080_25fps.mp4',
  services: [
    'https://videos.pexels.com/video-files/854400/854400-hd_1920_1080_25fps.mp4',
    'https://videos.pexels.com/video-files/3129977/3129977-hd_1920_1080_25fps.mp4',
  ],
}

function SectionReveal({
  children,
  className,
  id,
}: {
  children: ReactNode
  className?: string
  id?: string
}) {
  const ref = useRef<HTMLElement | null>(null)
  const isInView = useInView(ref, { once: true, margin: '-100px' })

  return (
    <motion.section
      id={id}
      ref={ref}
      initial={{ opacity: 0, y: 48 }}
      animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 48 }}
      transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
      className={className}
    >
      {children}
    </motion.section>
  )
}

function LiquidButton({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <button
      className={cn(
        'liquid-glass inline-flex items-center gap-2 rounded-full px-5 py-3 text-sm text-white/85 transition hover:text-white',
        className,
      )}
    >
      {children}
    </button>
  )
}

export default function Landing() {
  const videoRefs = useRef<Array<HTMLVideoElement | null>>([])
  const [activeVideo, setActiveVideo] = useState(0)
  const [heroReady, setHeroReady] = useState(false)

  const safePlay = (video: HTMLVideoElement | null) => {
    if (!video) return
    try {
      const result = video.play()
      if (result && typeof result.catch === 'function') {
        result.catch(() => undefined)
      }
    } catch {
      // jsdom does not implement media playback; swallow in tests.
    }
  }

  useEffect(() => {
    safePlay(videoRefs.current[0])
  }, [])

  const handleVideoEnd = (index: number) => {
    if (index !== activeVideo) return

    const nextIndex = (index + 1) % heroVideos.length
    const currentVideo = videoRefs.current[index]
    const nextVideo = videoRefs.current[nextIndex]

    if (!nextVideo) return

    nextVideo.currentTime = 0
    safePlay(nextVideo)
    setActiveVideo(nextIndex)

    window.setTimeout(() => {
      currentVideo?.pause()
    }, 500)
  }

  return (
    <main className="bg-black text-white selection:bg-white/10">
      <section className="relative flex min-h-screen flex-col overflow-hidden bg-black">
        <div className="pointer-events-none absolute inset-0">
          {heroVideos.map((src, index) => (
            <video
              key={src}
              ref={(node) => {
                videoRefs.current[index] = node
              }}
              src={src}
              muted
              playsInline
              autoPlay={index === 0}
              preload="auto"
              onCanPlay={() => setHeroReady(true)}
              onEnded={() => handleVideoEnd(index)}
              className={cn(
                'absolute inset-x-0 top-0 h-[120%] w-full object-cover transition-all duration-500',
                'translate-y-[calc(17%+100px)]',
                activeVideo === index ? 'opacity-100' : 'opacity-0',
                heroReady ? 'duration-500' : 'opacity-0',
              )}
            />
          ))}
          <div className="absolute inset-0 bg-gradient-to-b from-black/55 via-black/25 to-black" />
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(255,255,255,0.12),transparent_32%)]" />
        </div>

        <div className="relative z-10 mx-auto flex min-h-screen w-full max-w-7xl flex-col px-4 pb-10 pt-5 sm:px-6 lg:px-8">
          <header className="liquid-glass flex items-center justify-between rounded-full px-3 py-2">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/5 text-sm tracking-[0.3em] text-white/75">
                A
              </div>
              <div>
                <p className="text-sm uppercase tracking-[0.32em] text-white/45">Asme</p>
              </div>
            </div>
            <nav className="hidden items-center gap-8 text-sm text-white/60 md:flex">
              <a href="#about" className="transition hover:text-white">About</a>
              <a href="#featured-video" className="transition hover:text-white">Video</a>
              <a href="#philosophy" className="transition hover:text-white">Philosophy</a>
              <a href="#services" className="transition hover:text-white">Services</a>
            </nav>
            <div className="flex items-center gap-2">
              <LiquidButton className="px-4 py-2 text-xs">Sign Up</LiquidButton>
              <LiquidButton className="px-4 py-2 text-xs">Login</LiquidButton>
            </div>
          </header>

          <div className="flex flex-1 items-center">
            <div className="grid w-full gap-14 pt-20 lg:grid-cols-[1.2fr_0.8fr] lg:pt-28">
              <motion.div
                initial={{ opacity: 0, y: 36 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.8, delay: 0.05 }}
                className="max-w-3xl"
              >
                <p className="mb-5 text-xs uppercase tracking-[0.38em] text-white/40">Asme Studio</p>
                <h1 className="instrument-serif text-6xl leading-[0.96] text-white sm:text-7xl lg:text-[7rem]">
                  Built for the curious
                </h1>
                <p className="mt-8 max-w-xl text-base leading-7 text-white/60 sm:text-lg">
                  A quiet brand system for people who observe closely, think deeply, and build with intent.
                </p>

                <div className="mt-10 flex max-w-xl flex-col gap-4 sm:flex-row">
                  <div className="liquid-glass flex flex-1 items-center rounded-full px-5 py-2">
                    <input
                      type="email"
                      aria-label="Email address"
                      placeholder="Enter your email"
                      className="w-full bg-transparent text-sm text-white placeholder:text-white/35 focus:outline-none"
                    />
                    <button className="flex h-11 w-11 items-center justify-center rounded-full border border-white/10 bg-white/5 text-white/80 transition hover:bg-white/10 hover:text-white">
                      <ArrowRight size={16} />
                    </button>
                  </div>
                  <LiquidButton className="justify-center whitespace-nowrap px-6">
                    Manifesto
                    <ChevronRight size={16} />
                  </LiquidButton>
                </div>

                <div className="mt-10 flex flex-wrap items-center gap-3">
                  {[Twitter, Instagram, Linkedin].map((Icon, index) => (
                    <a
                      key={index}
                      href="#"
                      className="liquid-glass flex h-11 w-11 items-center justify-center rounded-full text-white/65 transition hover:text-white"
                      aria-label={`social-${index}`}
                    >
                      <Icon size={16} />
                    </a>
                  ))}
                </div>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 44 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.8, delay: 0.2 }}
                className="flex items-end lg:justify-end"
              >
                <div className="liquid-glass max-w-md rounded-[2rem] p-5">
                  <p className="text-xs uppercase tracking-[0.28em] text-white/40">Asme Notes</p>
                  <p className="mt-4 text-xl leading-8 text-white/78">
                    Minimal structure. Intentional motion. A surface designed to feel calm before it feels clever.
                  </p>
                </div>
              </motion.div>
            </div>
          </div>

          <Marquee className="mt-8 border-t border-white/10 pt-6">
            {['Quiet systems', 'Clear thinking', 'Curated motion', 'Crafted interfaces', 'Measured presence'].map((item) => (
              <div
                key={item}
                className="liquid-glass rounded-full px-4 py-2 text-xs uppercase tracking-[0.28em] text-white/45"
              >
                {item}
              </div>
            ))}
          </Marquee>
        </div>
      </section>

      <SectionReveal id="about" className="border-t border-white/5 bg-black px-4 py-28 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl">
          <p className="mb-6 text-xs uppercase tracking-[0.35em] text-white/35">About Us</p>
          <div className="grid gap-12 lg:grid-cols-[1.3fr_0.7fr]">
            <div>
              <h2 className="max-w-5xl text-4xl font-medium leading-tight text-white sm:text-5xl lg:text-6xl">
                Pioneering{' '}
                <span style={accentStyle}>ideas</span> for minds that{' '}
                <span style={accentStyle}>create</span>, build, and inspire.
              </h2>
            </div>
            <div className="space-y-5 text-sm leading-7 text-white/58">
              <p>
                Asme is a brand environment shaped for founders, researchers, and studios who value restraint as much as expression.
              </p>
              <p>
                We design experiences that feel cinematic without becoming loud, modern without losing warmth, and minimal without becoming empty.
              </p>
            </div>
          </div>
        </div>
      </SectionReveal>

      <SectionReveal id="featured-video" className="bg-black px-4 py-12 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl">
          <div className="relative overflow-hidden rounded-[2.5rem] border border-white/10 bg-white/[0.03]">
            <div className="absolute inset-0 z-10 bg-gradient-to-t from-black via-black/20 to-transparent" />
            <video
              src={sections.featured}
              autoPlay
              muted
              loop
              playsInline
              className="h-[36rem] w-full object-cover"
            />
            <div className="absolute inset-0 z-20 flex items-end justify-between gap-6 p-6 sm:p-8 lg:p-10">
              <div className="liquid-glass max-w-md rounded-[2rem] p-5 sm:p-6">
                <p className="text-xs uppercase tracking-[0.35em] text-white/40">Our Approach</p>
                <h3 className="mt-4 text-3xl font-medium tracking-tight text-white">
                  We let silence, pacing, and proportion do the persuasive work.
                </h3>
                <button className="mt-6 inline-flex items-center gap-2 text-sm text-white/75 transition hover:text-white">
                  Explore more
                  <ArrowRight size={16} />
                </button>
              </div>
              <div className="hidden h-14 w-14 items-center justify-center rounded-full border border-white/10 bg-black/40 text-white/70 backdrop-blur md:flex">
                <Play size={20} />
              </div>
            </div>
          </div>
        </div>
      </SectionReveal>

      <SectionReveal id="philosophy" className="border-t border-white/5 bg-black px-4 py-28 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl">
          <div className="mb-14 flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="mb-4 text-xs uppercase tracking-[0.35em] text-white/35">Philosophy</p>
              <h2 className="text-4xl font-medium text-white sm:text-5xl lg:text-6xl">
                Innovation <span style={accentStyle}>x</span> Vision
              </h2>
            </div>
            <p className="max-w-xl text-sm leading-7 text-white/58">
              We build systems that feel precise on first glance and richer the longer you stay with them.
            </p>
          </div>

          <div className="grid gap-8 lg:grid-cols-[1.05fr_0.95fr]">
            <div className="overflow-hidden rounded-[2.25rem] border border-white/10">
              <video
                src={sections.philosophy}
                autoPlay
                muted
                loop
                playsInline
                className="h-full min-h-[28rem] w-full object-cover transition duration-700 hover:scale-[1.02]"
              />
            </div>

            <div className="space-y-6">
              <div className="liquid-glass rounded-[2rem] p-6">
                <p className="text-xs uppercase tracking-[0.34em] text-white/35">Clarity</p>
                <p className="mt-4 text-lg leading-8 text-white/76">
                  Every interaction should feel inevitable, not ornamental. Minimalism becomes useful when it removes hesitation.
                </p>
              </div>
              <div className="liquid-glass rounded-[2rem] p-6">
                <p className="text-xs uppercase tracking-[0.34em] text-white/35">Depth</p>
                <p className="mt-4 text-lg leading-8 text-white/76">
                  Motion is employed to reveal hierarchy and rhythm, not to distract. Presence grows out of restraint.
                </p>
              </div>
              <AnimatedListDemo
                items={[
                  { label: 'Observe', value: 'Start with what matters' },
                  { label: 'Refine', value: 'Remove what feels loud' },
                  { label: 'Release', value: 'Ship with confidence' },
                ]}
              />
            </div>
          </div>
        </div>
      </SectionReveal>

      <SectionReveal id="services" className="border-t border-white/5 bg-black px-4 py-28 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl">
          <div className="mb-12 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="mb-4 text-xs uppercase tracking-[0.35em] text-white/35">What we do</p>
              <h2 className="text-4xl font-medium text-white sm:text-5xl">Services</h2>
            </div>
            <Marquee className="max-w-xl">
              {['Brand systems', 'Creative direction', 'Product surfaces', 'Editorial campaigns'].map((item) => (
                <span key={item} className="text-sm text-white/40">
                  {item}
                </span>
              ))}
            </Marquee>
          </div>

          <BentoGrid>
            {[
              {
                tag: 'Direction',
                title: 'Narratives for products that need quiet confidence.',
                description: 'Identity systems, launch pages, and motion language tailored to brands that prefer precision over noise.',
                video: sections.services[0],
              },
              {
                tag: 'Experience',
                title: 'Interfaces that feel calm, cinematic, and fully intentional.',
                description: 'From landing pages to editorial layouts, we turn complexity into a paced, memorable visual experience.',
                video: sections.services[1],
              },
            ].map((service) => (
              <BentoCard
                key={service.tag}
                name={service.title}
                description={service.description}
                cta={
                  <button className="inline-flex items-center gap-2 text-sm text-white/75 transition hover:text-white">
                    View service
                    <ArrowRight size={16} />
                  </button>
                }
                background={
                  <div className="absolute inset-0 overflow-hidden">
                    <video
                      src={service.video}
                      autoPlay
                      muted
                      loop
                      playsInline
                      className="h-full w-full object-cover transition duration-700 group-hover:scale-105"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-black via-black/25 to-black/10" />
                    <div className="absolute left-6 top-6 z-20 rounded-full border border-white/10 bg-black/35 px-3 py-1 text-[11px] uppercase tracking-[0.28em] text-white/50 backdrop-blur">
                      {service.tag}
                    </div>
                    <div className="absolute right-6 top-6 z-20 flex h-11 w-11 items-center justify-center rounded-full border border-white/10 bg-black/35 text-white/70 backdrop-blur">
                      <Play size={16} />
                    </div>
                  </div>
                }
                className="min-h-[31rem]"
              />
            ))}
          </BentoGrid>
        </div>
      </SectionReveal>
    </main>
=======
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, Shield, Cpu, TrendingUp, Lock, Zap, BarChart2 } from 'lucide-react'

const features = [
  { icon: Cpu, title: 'Autonomous Capital Brain', desc: 'A visible multi-stage intelligence loop reallocates capital using MWU, regime detection, and signed agent decisions.' },
  { icon: Shield, title: 'Cryptoeconomic Enforcement', desc: 'Staking, slashing, drawdown ceilings, and rogue-agent detection create economic accountability.' },
  { icon: TrendingUp, title: 'Stateful Agent Competition', desc: 'Agents are persistent financial entities with trust scores, confidence, and evolving capital allocations.' },
  { icon: Lock, title: 'Programmable Trust Layer', desc: 'Capital stays in the vault while intelligence competes off-chain and enforcement remains on-chain.' },
  { icon: BarChart2, title: 'Risk & World Intelligence', desc: 'VaR, anomaly detection, macro regime sensing, and news-aware signals shape every allocation cycle.' },
  { icon: Zap, title: 'Hackathon Demo Flow', desc: 'Show judges live orchestration, slashing watchlists, contract prompts, and a self-evolving financial organism.' },
]

export default function Landing() {
  const navigate = useNavigate()

  return (
    <div className="min-h-screen bg-bg overflow-hidden">
      {/* Grid background */}
      <div className="fixed inset-0 bg-grid bg-grid opacity-40 pointer-events-none" />
      <div className="fixed inset-0 bg-glow-cyan opacity-30 pointer-events-none" />

      {/* Nav */}
      <nav className="relative z-10 flex items-center justify-between px-8 py-5 border-b border-border glass">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'linear-gradient(135deg,#00f5ff,#a855f7)' }}>
            <Zap size={16} className="text-bg" />
          </div>
          <span className="font-bold tracking-wider gradient-text text-lg">DACAP</span>
        </div>
        <div className="flex items-center gap-6 text-sm text-slate-400">
          <a href="#features" className="hover:text-white transition-colors">Protocol</a>
          <a href="#math" className="hover:text-white transition-colors">Mathematics</a>
          <a href="#contracts" className="hover:text-white transition-colors">Contracts</a>
          <button onClick={() => navigate('/dashboard')} className="btn-primary">
            Launch App
          </button>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative z-10 flex flex-col items-center justify-center text-center px-6 pt-28 pb-20">
        <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8 }}>
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-cyan/30 bg-cyan/5 text-cyan text-xs font-mono mb-8">
            <span className="w-1.5 h-1.5 rounded-full bg-cyan animate-pulse" />
            Autonomous Financial Intelligence Network · Ethereum Mainnet · $25.3M TVL
          </div>

          <h1 className="text-5xl md:text-7xl font-extrabold leading-tight mb-6">
            <span className="gradient-text text-glow-cyan">Autonomous Financial</span>
            <br />
            <span className="text-white">Intelligence Network</span>
          </h1>

          <p className="text-slate-400 text-lg max-w-2xl mx-auto mb-10 leading-relaxed">
            DACAP turns hedge-fund logic into an autonomous on-chain organism: AI agents compete for capital,
            risk controls stay visible, and governance adapts the system in real time.
          </p>

          <div className="flex items-center justify-center gap-4">
            <motion.button
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
              onClick={() => navigate('/dashboard')}
              className="flex items-center gap-2 px-8 py-3.5 rounded-xl font-semibold text-bg transition-all"
              style={{ background: 'linear-gradient(135deg,#00f5ff,#a855f7)' }}
            >
              Enter App <ArrowRight size={16} />
            </motion.button>
            <button onClick={() => navigate('/intelligence')} className="px-8 py-3.5 rounded-xl font-semibold text-slate-300 border border-border hover:border-slate-500 transition-all">
              View Intelligence Loop
            </button>
          </div>
        </motion.div>

        {/* Animated stats */}
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4, duration: 0.8 }}
          className="grid grid-cols-4 gap-6 mt-20 w-full max-w-3xl"
        >
          {[
            { label: 'Total Value Locked', value: '$25.3M' },
            { label: 'Active Agents', value: '47' },
            { label: 'Avg. Sharpe Ratio', value: '2.14' },
            { label: 'Protocol Uptime', value: '99.97%' },
          ].map(s => (
            <div key={s.label} className="card text-center">
              <div className="text-2xl font-bold gradient-text">{s.value}</div>
              <div className="text-xs text-slate-500 mt-1">{s.label}</div>
            </div>
          ))}
        </motion.div>
      </section>

      {/* Features */}
      <section id="features" className="relative z-10 px-8 py-20 max-w-6xl mx-auto">
        <h2 className="text-3xl font-bold text-center mb-3 text-white">Autonomous System Surface</h2>
        <p className="text-slate-500 text-center mb-12 text-sm">From capital brain to slashing engine, every layer is visible and demoable</p>
        <div className="grid grid-cols-3 gap-5">
          {features.map((f, i) => (
            <motion.div
              key={f.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1 }}
              className="card hover:border-cyan/20 transition-all group"
            >
              <div className="w-10 h-10 rounded-lg flex items-center justify-center mb-4 bg-cyan/10 group-hover:bg-cyan/20 transition-colors">
                <f.icon size={18} className="text-cyan" />
              </div>
              <h3 className="font-semibold text-white mb-2 text-sm">{f.title}</h3>
              <p className="text-slate-500 text-xs leading-relaxed">{f.desc}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Math section */}
      <section id="math" className="relative z-10 px-8 py-20 max-w-4xl mx-auto text-center">
        <h2 className="text-3xl font-bold mb-3 text-white">Mathematical Foundation</h2>
        <p className="text-slate-500 mb-10 text-sm">Regret-minimizing online learning fused with regime-aware autonomous execution</p>
        <div className="card glow-purple">
          <p className="text-slate-400 text-sm mb-4">Multiplicative Weights Update Rule</p>
          <div className="font-mono text-xl text-purple bg-purple/5 rounded-lg p-4 border border-purple/20">
            w<sub>i</sub>(t+1) = w<sub>i</sub>(t) · exp(η · R<sub>i</sub>(t))
          </div>
          <p className="text-slate-500 text-xs mt-4">
            Normalized across all agents. The protocol rotates capital toward the strongest intelligence while preserving cryptographic trust.
          </p>
        </div>
      </section>

      <footer className="relative z-10 border-t border-border px-8 py-6 text-center text-slate-600 text-xs">
        DACAP Protocol · Decentralized Autonomous Capital Allocation · Research-Grade DeFi Infrastructure
      </footer>
    </div>
>>>>>>> D!
  )
}
