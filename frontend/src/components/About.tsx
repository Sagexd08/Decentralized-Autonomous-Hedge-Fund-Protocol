import React from 'react';
import { motion } from 'framer-motion';
import { useInViewAnimation } from '../hooks/useInViewAnimation';

export const About = () => {
  const { ref, isInView } = useInViewAnimation("-100px");

  const container = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: { staggerChildren: 0.2 }
    }
  };

  const item = {
    hidden: { opacity: 0, y: 20 },
    show: { opacity: 1, y: 0, transition: { duration: 0.8, ease: [0.16, 1, 0.3, 1] } }
  };

  return (
    <section className="bg-black py-32 px-6 border-t border-white/5" ref={ref}>
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-start justify-between gap-16">

        <motion.div
          className="md:w-1/2 w-full"
          variants={container}
          initial="hidden"
          animate={isInView ? "show" : "hidden"}
        >
          <motion.p variants={item} className="text-white/40 tracking-[0.2em] text-xs font-semibold uppercase mb-6 drop-shadow-lg">
            System Overview
          </motion.p>
          <motion.h2 variants={item} className="text-4xl md:text-5xl lg:text-6xl font-medium tracking-tight text-white leading-[1.1] mb-12">
            A decentralized <br/>
            <span className="font-['Instrument_Serif'] italic font-normal text-white/90">intelligence layer</span><br/>
            for capital allocation.
          </motion.h2>
        </motion.div>

        <motion.div
          className="md:w-1/2 w-full flex flex-col gap-6"
          variants={container}
          initial="hidden"
          animate={isInView ? "show" : "hidden"}
        >
          {[
            { title: "AI Agents", desc: "Autonomous actors making high-frequency allocation decisions based on predictive real-time multi-dimensional datasets." },
            { title: "On-chain Execution", desc: "Settlement guarantees enforced via cryptographic consensus, eliminating intermediary friction and latency." },
            { title: "Adaptive Learning", desc: "Systematic performance optimizations driven by reinforcement learning, evolving dynamically to market anomalies." }
          ].map((block, idx) => (
            <motion.div key={idx} variants={item} className="liquid-glass p-8 flex flex-col gap-3 group cursor-default">
              <h3 className="text-xl font-medium text-white group-hover:text-white transition-colors">{block.title}</h3>
              <p className="text-base text-white/50 leading-relaxed font-light">{block.desc}</p>
            </motion.div>
          ))}
        </motion.div>

      </div>
    </section>
  );
};
