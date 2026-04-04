import { motion, useInView } from 'framer-motion'
import { useRef } from 'react'
import { ArrowUpRight } from 'lucide-react'

const cards = [
  {
    tag: 'STRATEGY',
    title: 'Research & Insight',
    description:
      'We dig deep into data, culture, and human behavior to surface the insights that drive meaningful, lasting change.',
    video:
      'https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260314_131748_f2ca2a28-fed7-44c8-b9a9-bd9acdd5ec31.mp4',
  },
  {
    tag: 'CRAFT',
    title: 'Design & Execution',
    description:
      'From concept to launch, we obsess over every detail to deliver experiences that feel effortless and look extraordinary.',
    video:
      'https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260324_151826_c7218672-6e92-402c-9e45-f1e0f454bdc4.mp4',
  },
]

export default function ServicesSection() {
  const ref = useRef<HTMLElement | null>(null)
  const isInView = useInView(ref, { once: true, margin: '-100px' })

  return (
    <section
      ref={ref}
      className="relative bg-black py-28 px-6 md:py-40"
      id="services"
    >
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,_rgba(255,255,255,0.02)_0%,_transparent_60%)]" />

      <div className="relative mx-auto max-w-6xl">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 30 }}
          transition={{ duration: 0.7 }}
          className="mb-16 flex items-baseline justify-between"
        >
          <h2 className="text-3xl md:text-5xl text-white tracking-tight">What we do</h2>
          <p className="hidden md:block text-white/40 text-sm">Our services</p>
        </motion.div>

        <div className="grid gap-6 md:grid-cols-2 md:gap-8">
          {cards.map((card, i) => (
            <motion.article
              key={card.title}
              initial={{ opacity: 0, y: 50 }}
              animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 50 }}
              transition={{ duration: 0.8, delay: i * 0.15 }}
              className="group liquid-glass rounded-3xl overflow-hidden"
            >
              <div className="relative aspect-video overflow-hidden">
                <video
                  src={card.video}
                  muted
                  autoPlay
                  loop
                  playsInline
                  preload="auto"
                  className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/40 to-transparent" />
              </div>

              <div className="p-6 md:p-8">
                <div className="mb-5 flex items-center justify-between">
                  <p className="text-white/40 text-xs tracking-widest uppercase">{card.tag}</p>
                  <span className="liquid-glass rounded-full p-2 text-white/60 transition-colors group-hover:text-white">
                    <ArrowUpRight size={16} />
                  </span>
                </div>

                <h3 className="mb-3 text-white text-xl md:text-2xl tracking-tight">{card.title}</h3>
                <p className="text-white/50 text-sm leading-relaxed">{card.description}</p>
              </div>
            </motion.article>
          ))}
        </div>
      </div>
    </section>
  )
}
