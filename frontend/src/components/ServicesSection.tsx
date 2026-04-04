import { useRef } from 'react';
import { motion, useInView } from 'framer-motion';
import { ArrowUpRight } from 'lucide-react';

export default function ServicesSection() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-100px" });

  const cards = [
    {
      video: "https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260314_131748_f2ca2a28-fed7-44c8-b9a9-bd9acdd5ec31.mp4",
      tag: "STRATEGY",
      title: "Research & Insight",
      description: "We dig deep into data, culture, and human behavior to surface the insights that drive meaningful, lasting change."
    },
    {
      video: "https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260324_151826_c7218672-6e92-402c-9e45-f1e0f454bdc4.mp4",
      tag: "CRAFT",
      title: "Design & Execution",
      description: "From concept to launch, we obsess over every detail to deliver experiences that feel effortless and look extraordinary."
    }
  ];

  return (
    <section className="bg-black py-28 md:py-40 px-6 relative" ref={ref}>
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_rgba(255,255,255,0.02)_0%,_transparent_60%)] pointer-events-none" />
      <div className="max-w-6xl mx-auto relative z-10">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 30 }}
          transition={{ duration: 0.7 }}
          className="flex items-baseline justify-between mb-16"
        >
          <h2 className="text-3xl md:text-5xl text-white tracking-tight">What we do</h2>
          <span className="text-white/40 text-sm hidden md:block">Our services</span>
        </motion.div>

        <div className="grid md:grid-cols-2 gap-6 md:gap-8">
          {cards.map((card, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, y: 50 }}
              animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 50 }}
              transition={{ duration: 0.8, delay: index * 0.15 }}
              className="group liquid-glass rounded-3xl overflow-hidden flex flex-col"
            >
              <div className="relative aspect-video overflow-hidden">
                <video
                  src={card.video}
                  muted
                  autoPlay
                  loop
                  playsInline
                  preload="auto"
                  className="object-cover w-full h-full transition-transform duration-700 group-hover:scale-105"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/40 to-transparent pointer-events-none" />
              </div>
              <div className="p-6 md:p-8 flex flex-col justify-between flex-1">
                <div className="flex justify-between items-center mb-6">
                  <span className="text-white/40 text-xs tracking-widest uppercase">{card.tag}</span>
                  <div className="liquid-glass rounded-full p-2 text-white/60 transition-colors duration-300 group-hover:text-white">
                    <ArrowUpRight size={16} />
                  </div>
                </div>
                <div>
                  <h3 className="text-white text-xl md:text-2xl mb-3 tracking-tight">{card.title}</h3>
                  <p className="text-white/50 text-sm leading-relaxed">{card.description}</p>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
