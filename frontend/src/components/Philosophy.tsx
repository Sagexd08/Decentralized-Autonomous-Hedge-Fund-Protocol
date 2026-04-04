import React from 'react';
import { motion } from 'framer-motion';
import { useInViewAnimation } from '../hooks/useInViewAnimation';

export const Philosophy = () => {
  const { ref, isInView } = useInViewAnimation("-100px");

  return (
    <section className="relative w-full min-h-[80vh] bg-black flex items-center justify-center overflow-hidden border-t border-white/5" ref={ref}>
      {}
      <div className="absolute inset-0 z-0">
        <div className="absolute inset-0 bg-black/60 z-10" />
        <video
          src="https://videos.pexels.com/video-files/3129595/3129595-hd_1920_1080_25fps.mp4"
          autoPlay
          muted
          loop
          playsInline
          preload="auto"
          className="absolute inset-0 w-full h-full object-cover scale-105 opacity-50"
        />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 30 }}
        transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1] }}
        className="relative z-20 text-center max-w-4xl px-6"
      >
        <p className="text-white/40 tracking-[0.2em] text-xs font-semibold uppercase mb-8 drop-shadow-lg">Core Philosophy</p>
        <h2 className="text-5xl md:text-7xl font-medium tracking-tight text-white mb-12 flex flex-col gap-4">
          <span>Code.</span>
          <span className="font-['Instrument_Serif'] italic text-white/50">&times; Intelligence.</span>
          <span>Capital.</span>
        </h2>

        <p className="text-lg md:text-xl text-white/70 max-w-2xl mx-auto font-light leading-relaxed">
          We believe the future of finance is not human. It is mathematical, deterministic, and autonomous. DACAP strips away human emotion to present an immutable layer of truth in capital allocation.
        </p>
      </motion.div>
    </section>
  );
};
