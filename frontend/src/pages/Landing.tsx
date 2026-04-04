import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, Globe, Instagram, Twitter } from 'lucide-react'
import AboutSection from '../components/landing/AboutSection'
import FeaturedVideoSection from '../components/landing/FeaturedVideoSection'
import PhilosophySection from '../components/landing/PhilosophySection'
import ServicesSection from '../components/landing/ServicesSection'

function Hero() {
  const navigate = useNavigate()
  const videoRef = useRef<HTMLVideoElement>(null)
  const [videoOpacity, setVideoOpacity] = useState(0)
  const [ready, setReady] = useState(false)
  const rafRef = useRef<number | null>(null)
  const fadingOutRef = useRef(false)
  const accentStyle = {
    fontFamily: "'Instrument Serif', serif",
    fontStyle: 'italic' as const,
  }

  useEffect(() => {
    const video = videoRef.current
    if (!video) return

    const animateOpacity = (from: number, to: number, durationMs: number) => {
      const start = performance.now()
      if (rafRef.current) cancelAnimationFrame(rafRef.current)

      const tick = (now: number) => {
        const progress = Math.min((now - start) / durationMs, 1)
        const value = from + (to - from) * progress
        setVideoOpacity(value)
        if (progress < 1) {
          rafRef.current = requestAnimationFrame(tick)
        }
      }

      rafRef.current = requestAnimationFrame(tick)
    }

    const onCanPlay = () => {
      setReady(true)
      animateOpacity(0, 1, 500)
    }

    const onTimeUpdate = () => {
      if (!video.duration || !ready || fadingOutRef.current) return
      const remaining = video.duration - video.currentTime
      if (remaining <= 0.55) {
        fadingOutRef.current = true
        animateOpacity(videoOpacity, 0, 500)
      }
    }

    const onEnded = () => {
      video.currentTime = 0
      const play = video.play()
      if (play && 'catch' in play) {
        play.catch(() => undefined)
      }
      fadingOutRef.current = false
      animateOpacity(0, 1, 500)
    }

    video.addEventListener('canplay', onCanPlay)
    video.addEventListener('timeupdate', onTimeUpdate)
    video.addEventListener('ended', onEnded)

    const play = video.play()
    if (play && 'catch' in play) {
      play.catch(() => undefined)
    }

    return () => {
      video.removeEventListener('canplay', onCanPlay)
      video.removeEventListener('timeupdate', onTimeUpdate)
      video.removeEventListener('ended', onEnded)
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
  }, [])

  return (
    <section className="relative min-h-screen bg-black flex flex-col overflow-hidden">
      <div className="absolute inset-0 pointer-events-none">
        <video
          ref={videoRef}
          src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260404_050931_6b868bbb-85a4-498d-921e-e815d5a55906.mp4"
          muted
          autoPlay
          playsInline
          preload="auto"
          style={{ opacity: videoOpacity }}
          className="absolute inset-0 w-full h-full object-cover translate-y-[calc(17%+100px)] transition-opacity duration-500"
        />
        <div className="absolute inset-0 bg-gradient-to-b from-black/55 via-black/35 to-black" />
      </div>

      <div className="relative z-20 w-full px-6 pt-6">
        <div className="mx-auto max-w-5xl liquid-glass rounded-full px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Globe size={24} className="text-white" />
            <span className="text-white font-semibold text-lg">Asme</span>
            <div className="hidden md:flex items-center gap-6 ml-8">
              <a href="#features" className="text-white/80 text-sm font-medium hover:text-white transition">Features</a>
              <a href="#services" className="text-white/80 text-sm font-medium hover:text-white transition">Pricing</a>
              <a href="#about" className="text-white/80 text-sm font-medium hover:text-white transition">About</a>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <button className="text-white text-sm font-medium">Sign Up</button>
            <button className="liquid-glass rounded-full px-6 py-2 text-white text-sm font-medium">Login</button>
          </div>
        </div>
      </div>

      <div className="relative z-10 flex-1 flex items-center justify-center -translate-y-[20%] text-center px-6">
        <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7 }}>
          <h1
            style={{ fontFamily: "'Instrument Serif', serif" }}
            className="text-5xl md:text-6xl lg:text-7xl text-white tracking-tight whitespace-nowrap mb-8"
          >
            Built for the curious
          </h1>

          <div className="mx-auto max-w-xl liquid-glass rounded-full pl-6 pr-2 py-2 flex items-center gap-3">
            <input
              type="email"
              placeholder="Enter your email"
              className="flex-1 bg-transparent text-white placeholder:text-white/40 focus:outline-none"
            />
            <button className="h-11 w-11 rounded-full bg-white flex items-center justify-center">
              <ArrowRight size={20} className="text-black" />
            </button>
          </div>

          <p className="mt-5 px-4 text-white text-sm leading-relaxed">
            Stay updated with the latest news and insights. Subscribe to our newsletter today and never miss out on exciting updates.
          </p>

          <button className="mt-6 liquid-glass rounded-full px-8 py-3 text-white text-sm font-medium hover:bg-white/5 transition">
            Manifesto
          </button>
        </motion.div>
      </div>

      <div className="relative z-10 pb-8 px-6">
        <div className="mx-auto max-w-5xl flex items-center justify-center gap-4">
          {[Instagram, Twitter, Globe].map((Icon, idx) => (
            <button key={idx} className="liquid-glass rounded-full p-4 text-white/80 hover:text-white hover:bg-white/5 transition">
              <Icon size={18} />
            </button>
          ))}
        </div>
      </div>
    </section>
  )
}

export default function Landing() {
  return (
    <main className="bg-black text-white">
      <Hero />
      <AboutSection />
      <FeaturedVideoSection />
      <PhilosophySection />
      <ServicesSection />
    </main>
  )
}
