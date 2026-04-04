import React from 'react';
import { motion } from 'framer-motion';
import { useInViewAnimation } from '../hooks/useInViewAnimation';

export const VideoSection = () => {
  const { ref, isInView } = useInViewAnimation("-100px");

  return (
    <section className="bg-black py-24 px-4 sm:px-6" ref={ref}>
      <div className="max-w-7xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 40, scale: 0.98 }}
          animate={isInView ? { opacity: 1, y: 0, scale: 1 } : { opacity: 0, y: 40, scale: 0.98 }}
          transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1] }}
          className="relative w-full aspect-video rounded-[2rem] overflow-hidden group"
        >
          {}
          <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent z-10" />
          <div className="absolute inset-0 bg-black/30 z-10 group-hover:bg-black/10 transition-colors duration-700" />

          <video
            src="https://videos.pexels.com/video-files/3130284/3130284-hd_1920_1080_25fps.mp4"
            autoPlay
            muted
            loop
            playsInline
            preload="auto"
            className="absolute inset-0 w-full h-full object-cover scale-105 group-hover:scale-100 transition-transform duration-1000 ease-out"
          />

          {}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 20 }}
            transition={{ duration: 0.8, delay: 0.5 }}
            className="absolute bottom-8 left-8 md:bottom-12 md:left-12 z-20 liquid-glass p-8 max-w-sm rounded-2xl backdrop-blur-2xl"
          >
            <div className="flex items-center gap-3 mb-4">
              <span className="relative flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-white opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-white"></span>
              </span>
              <span className="text-xs font-semibold tracking-widest text-white uppercase">Live System</span>
            </div>

            <h3 className="text-2xl md:text-3xl font-medium text-white mb-2 leading-tight">
              Agents trading in real-time
            </h3>
            <p className="text-sm text-white/60 mb-6 font-light">
              Monitoring global liquidity pools and executing delta-neutral strategies instantly.
            </p>

            <button className="flex items-center gap-2 text-sm font-medium text-white group/btn">
              View Live Feed
              <span className="group-hover/btn:translate-x-1 transition-transform">→</span>
            </button>
          </motion.div>
        </motion.div>
      </div>
    </section>
  );
};
