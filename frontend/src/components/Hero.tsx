import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

const videos = [
  "https://videos.pexels.com/video-files/856988/856988-hd_1920_1080_25fps.mp4",
  "https://videos.pexels.com/video-files/857195/857195-hd_1920_1080_25fps.mp4"
];

export const Hero = () => {
  const [activeVideo, setActiveVideo] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setActiveVideo((prev) => {
        const next = prev === 0 ? 1 : 0;
        const videoElement = document.getElementById(`hero-video-${next}`) as HTMLVideoElement;
        if (videoElement) {
          videoElement.currentTime = 0;
          videoElement.play().catch(e => console.log('Playback error:', e));
        }
        return next;
      });
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <section className="relative w-full h-screen overflow-hidden bg-black flex items-center pt-24 pb-12">
      {}
      <div className="absolute inset-0 z-0 pointer-events-none">
        <div className="absolute inset-0 bg-black/60 z-10" /> {}
        {videos.map((src, idx) => (
          <video
            id={`hero-video-${idx}`}
            key={src}
            src={src}
            autoPlay
            muted
            playsInline
            preload="auto"
            onEnded={(e) => {
              e.currentTarget.pause();
            }}
            className={`absolute inset-0 w-full h-full object-cover transition-all duration-[2000ms] ease-in-out ${
              activeVideo === idx ? 'opacity-100 scale-105 z-0' : 'opacity-0 scale-100 -z-10'
            }`}
          />
        ))}
      </div>

      <div className="relative z-20 w-full max-w-7xl mx-auto px-6 flex flex-col items-center justify-center text-center">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 1, delay: 0.5, ease: [0.16, 1, 0.3, 1] }}
          className="max-w-4xl"
        >
          <h1 className="text-5xl md:text-7xl lg:text-8xl font-medium tracking-tight text-white mb-6 leading-[1.1]">
            <span className="font-['Instrument_Serif'] italic font-normal pr-2">Autonomous</span><br />
            Capital. Intelligent<br />Allocation.
          </h1>

          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 1, delay: 0.8 }}
            className="text-lg md:text-xl text-white/70 mb-12"
          >
            A decentralized intelligence layer for global capital distribution.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 1, delay: 1 }}
            className="flex flex-col sm:flex-row items-center justify-center gap-4 max-w-md mx-auto"
          >
            <div className="relative w-full">
              <input
                type="text"
                placeholder="Email or Wallet Address"
                className="w-full h-12 px-6 bg-white/5 border border-white/10 rounded-full text-white placeholder:text-white/40 focus:outline-none focus:border-white/30 backdrop-blur-md transition-all"
              />
            </div>
            <button className="h-12 px-8 whitespace-nowrap bg-white text-black font-medium rounded-full hover:bg-white/90 transition-colors shadow-[0_0_20px_rgba(255,255,255,0.3)]">
              Launch Terminal
            </button>
          </motion.div>
        </motion.div>
      </div>

      {}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-white/5 rounded-full blur-[120px] pointer-events-none z-10 mix-blend-screen" />
    </section>
  );
};
