import React from 'react';
import { motion } from 'framer-motion';
import { useInViewAnimation } from '../hooks/useInViewAnimation';

const MOCK_NEWS = [
  "SEC approves new regulatory framework for AI-managed ETFs",
  "Global liquidity shifts to decentralized agent networks",
  "DACAP terminal processing 100k TPS on intelligence layer",
  "Traditional hedge funds integrating autonomous allocation",
  "Zero-knowledge proofs securing multi-chain state transitions",
  "Algorithmic yields outperforming human managed funds by 400%"
];

export const Intelligence = () => {
  const { ref, isInView } = useInViewAnimation("-50px");

  return (
    <section className="bg-black py-24 border-t border-white/5 overflow-hidden" ref={ref}>
      <motion.div
        initial={{ opacity: 0 }}
        animate={isInView ? { opacity: 1 } : { opacity: 0 }}
        transition={{ duration: 1 }}
        className="flex flex-col gap-8"
      >
        <div className="px-6 max-w-7xl mx-auto w-full">
          <p className="text-white/40 tracking-[0.2em] text-xs font-semibold uppercase mb-4 drop-shadow-lg">Global Intelligence</p>
          <h2 className="text-3xl md:text-4xl font-medium tracking-tight text-white mb-8">
            Real-time Macro Signals
          </h2>
        </div>

        {}
        <div className="relative flex overflow-x-hidden w-full group">
          <div className="absolute inset-y-0 left-0 w-32 bg-gradient-to-r from-black to-transparent z-10" />
          <div className="absolute inset-y-0 right-0 w-32 bg-gradient-to-l from-black to-transparent z-10" />

          <div className="animate-marquee whitespace-nowrap flex items-center group-hover:[animation-play-state:paused]">
            {[...MOCK_NEWS, ...MOCK_NEWS].map((news, idx) => (
              <div key={idx} className="flex items-center mx-4">
                <span className="w-2 h-2 rounded-full bg-white/20 mr-4" />
                <span className="text-xl md:text-2xl text-white/80 font-light">{news}</span>
              </div>
            ))}
          </div>
        </div>

        {}
        <div className="relative flex overflow-x-hidden w-full group">
          <div className="animate-marquee2 whitespace-nowrap flex items-center group-hover:[animation-play-state:paused]">
            {[...MOCK_NEWS, ...MOCK_NEWS].reverse().map((news, idx) => (
              <div key={idx} className="flex items-center mx-4">
                <span className="text-white/30 px-3 py-1 text-xs border border-white/10 rounded-full mr-4 leading-none">SIGNAL</span>
                <span className="text-xl md:text-2xl text-white/50 font-['Instrument_Serif'] italic">{news}</span>
              </div>
            ))}
          </div>
        </div>

      </motion.div>
    </section>
  );
};
