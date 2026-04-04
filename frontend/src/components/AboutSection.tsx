import { useRef } from 'react';
import { motion, useInView } from 'framer-motion';

export default function AboutSection() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-100px" });

  return (
    <section className="bg-black pt-32 md:pt-44 pb-10 md:pb-14 px-6 relative" ref={ref}>
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_rgba(255,255,255,0.03)_0%,_transparent_70%)] pointer-events-none" />
      <div className="max-w-6xl mx-auto relative z-10">
        <div className="mb-16">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 20 }}
            transition={{ duration: 0.6 }}
            className="text-white/40 text-sm tracking-widest uppercase"
          >
            ABOUT US
          </motion.div>
        </div>

        <motion.h2
          initial={{ opacity: 0, y: 40 }}
          animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 40 }}
          transition={{ duration: 0.8, delay: 0.1 }}
          className="text-white text-4xl md:text-6xl lg:text-7xl leading-[1.1] tracking-tight"
        >
          Pioneering <span className="not-italic text-white/60" style={{ fontFamily: "'Instrument Serif', serif", fontStyle: "italic" }}>ideas</span> for <br className="hidden md:block" />
          minds that <span className="not-italic text-white/60" style={{ fontFamily: "'Instrument Serif', serif", fontStyle: "italic" }}>create,</span> <span className="not-italic text-white/60" style={{ fontFamily: "'Instrument Serif', serif", fontStyle: "italic" }}>build,</span> and <span className="not-italic text-white/60" style={{ fontFamily: "'Instrument Serif', serif", fontStyle: "italic" }}>inspire.</span>
        </motion.h2>
      </div>
    </section>
  );
}
