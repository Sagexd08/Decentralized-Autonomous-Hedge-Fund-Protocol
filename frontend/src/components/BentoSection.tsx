import React from 'react';
import { motion } from 'framer-motion';
import { useInViewAnimation } from '../hooks/useInViewAnimation';
import { Network, Activity, ShieldAlert, Cpu } from 'lucide-react';

export const BentoSection = () => {
  const { ref, isInView } = useInViewAnimation("-50px");

  const container = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: { staggerChildren: 0.15 }
    }
  };

  const item = {
    hidden: { opacity: 0, y: 20 },
    show: { opacity: 1, y: 0, transition: { duration: 0.7, ease: [0.16, 1, 0.3, 1] } }
  };

  const bentoItems = [
    {
      title: "AI Agents",
      desc: "Distributed swarm of predictive modeling components.",
      icon: <Cpu className="w-5 h-5 text-white/70" />,
      className: "md:col-span-2 md:row-span-2 min-h-[300px]",
      content: (
        <div className="absolute inset-0 pt-24 px-8 overflow-hidden">
          {}
          <div className="w-full h-full flex flex-col gap-4 opacity-30">
             <div className="h-1 w-full bg-gradient-to-r from-transparent via-white to-transparent transform -translate-x-full animate-[pulse_3s_infinite]" />
             <div className="h-px w-full bg-white/20" />
             <div className="flex justify-between">
                <div className="w-8 h-8 rounded-full border border-white/20 flex items-center justify-center"><div className="w-1 h-1 bg-white rounded-full" /></div>
                <div className="w-8 h-8 rounded-full border border-white/20 flex items-center justify-center"><div className="w-1 h-1 bg-white rounded-full animate-ping" /></div>
                <div className="w-8 h-8 rounded-full border border-white/20 flex items-center justify-center"><div className="w-1 h-1 bg-white rounded-full" /></div>
             </div>
          </div>
        </div>
      )
    },
    {
      title: "Signal Flow",
      desc: "Real-time parsing of on-chain activity.",
      icon: <Network className="w-5 h-5 text-white/70" />,
      className: "md:col-span-1 min-h-[200px]",
      content: (
        <div className="absolute bottom-0 left-0 w-full p-6 pt-0">
          <div className="h-12 w-full flex items-end gap-1 opacity-50">
            {[40, 70, 30, 90, 50, 80, 20, 60].map((h, i) => (
              <motion.div
                key={i}
                className="flex-1 bg-white/40 rounded-t-sm"
                animate={{ height: [`${h}%`, `${Math.random() * 100}%`, `${h}%`] }}
                transition={{ duration: 2 + i * 0.1, repeat: Infinity, ease: "linear" }}
              />
            ))}
          </div>
        </div>
      )
    },
    {
      title: "Trading Events",
      desc: "High-frequency delta adjustments.",
      icon: <Activity className="w-5 h-5 text-white/70" />,
      className: "md:col-span-1 min-h-[200px]",
      content: (
        <div className="absolute right-0 top-1/2 -translate-y-1/2 w-48 overflow-hidden p-6 opacity-40">
           {}
           <div className="flex flex-col gap-3">
             {[1, 2, 3].map(i => (
                <div key={i} className="w-full h-8 bg-white/5 rounded-md flex items-center px-3 border border-white/5">
                  <div className="w-2 h-2 rounded-full bg-white/50 mr-2" />
                  <div className="h-2 bg-white/20 rounded-full w-1/2" />
                </div>
             ))}
           </div>
        </div>
      )
    },
    {
      title: "System Logs",
      desc: "Immutable execution records.",
      icon: <ShieldAlert className="w-5 h-5 text-white/70" />,
      className: "md:col-span-2 min-h-[200px]",
      content: (
        <div className="absolute bottom-6 left-6 right-6 font-['JetBrains_Mono'] text-xs text-white/30 overflow-hidden h-20">
          <div className="animate-[slideup_10s_linear_infinite] flex flex-col gap-1">
            <p>&gt; initializing core parameters...</p>
            <p>&gt; connecting to liquidity pools: successful</p>
            <p className="text-white/70">&gt; evaluating arb opportunities via zero-knowledge proofs</p>
            <p>&gt; execution context verified. proceeding.</p>
            <p>&gt; agent 7x9 deployed.</p>
          </div>
        </div>
      )
    }
  ];

  return (
    <section className="bg-black py-24 px-6 border-t border-white/5" ref={ref}>
      <div className="max-w-7xl mx-auto flex flex-col gap-16">

        <motion.div
          className="w-full text-center"
          variants={container}
          initial="hidden"
          animate={isInView ? "show" : "hidden"}
        >
          <motion.p variants={item} className="text-white/40 tracking-[0.2em] text-xs font-semibold uppercase mb-4 drop-shadow-lg">
            Agent Intelligence
          </motion.p>
          <motion.h2 variants={item} className="text-3xl md:text-5xl font-medium tracking-tight text-white leading-[1.1]">
            Distributed Architecture
          </motion.h2>
        </motion.div>

        <motion.div
          className="grid grid-cols-1 md:grid-cols-4 gap-4"
          variants={container}
          initial="hidden"
          animate={isInView ? "show" : "hidden"}
        >
          {bentoItems.map((bento, idx) => (
            <motion.div
              key={idx}
              variants={item}
              className={`liquid-glass p-8 group hover:-translate-y-1 transition-transform ${bento.className}`}
            >
              <div className="relative z-20 flex flex-col items-start gap-4 h-full pointer-events-none">
                <div className="w-10 h-10 rounded-full bg-white/5 flex items-center justify-center border border-white/10 group-hover:scale-110 transition-transform">
                  {bento.icon}
                </div>
                <div>
                  <h3 className="text-lg font-medium text-white mb-2">{bento.title}</h3>
                  <p className="text-sm text-white/50">{bento.desc}</p>
                </div>
              </div>
              {bento.content}
            </motion.div>
          ))}
        </motion.div>

      </div>
    </section>
  );
};
