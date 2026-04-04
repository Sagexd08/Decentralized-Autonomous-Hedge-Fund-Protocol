import React from 'react';
import { motion } from 'framer-motion';
import { useInViewAnimation } from '../hooks/useInViewAnimation';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, ResponsiveContainer, Tooltip } from 'recharts';

const data = [
  { name: '10:00', risk: 8 },
  { name: '10:15', risk: 12 },
  { name: '10:30', risk: 11 },
  { name: '10:45', risk: 15 },
  { name: '11:00', risk: 9 },
  { name: '11:15', risk: 10 },
  { name: '11:30', risk: 7 },
  { name: '11:45', risk: 14 },
  { name: '12:00', risk: 16 }
];

export const Risk = () => {
  const { ref, isInView } = useInViewAnimation("-50px");

  return (
    <section className="bg-black py-24 px-6 border-t border-white/5" ref={ref}>
      <div className="max-w-7xl mx-auto flex flex-col lg:flex-row gap-16 items-center">

        <motion.div
          initial={{ opacity: 0, x: -30 }}
          animate={isInView ? { opacity: 1, x: 0 } : { opacity: 0, x: -30 }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          className="lg:w-1/3 w-full"
        >
          <p className="text-white/40 tracking-[0.2em] text-xs font-semibold uppercase mb-4 drop-shadow-lg">Risk & Analytics</p>
          <h2 className="text-4xl md:text-5xl font-medium tracking-tight text-white mb-6 leading-tight">
            Monte Carlo <br/><span className="font-['Instrument_Serif'] italic font-normal text-white/50">Simulations</span>
          </h2>
          <p className="text-white/60 mb-8 font-light leading-relaxed">
            Continuously running millions of probabilistic pathways to hedge tail-risk and ensure capital preservation across highly volatile decentralized environments.
          </p>

          <div className="flex flex-col gap-4">
            {['Volatility Index: Low', 'Exposure: Delta Neutral', 'Confidence: 99.9%'].map((stat, i) => (
              <div key={i} className="flex flex-col gap-2">
                <div className="text-sm font-['JetBrains_Mono'] text-white/80">{stat}</div>
                <div className="h-1 w-full bg-white/10 rounded-full overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={isInView ? { width: '80%' } : { width: 0 }}
                    transition={{ duration: 1.5, delay: 0.5 + i * 0.2 }}
                    className="h-full bg-white"
                  />
                </div>
              </div>
            ))}
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={isInView ? { opacity: 1, scale: 1 } : { opacity: 0, scale: 0.95 }}
          transition={{ duration: 1, ease: [0.16, 1, 0.3, 1], delay: 0.2 }}
          className="lg:w-2/3 w-full liquid-glass p-8 h-[400px]"
        >
          <div className="flex justify-between items-center mb-8">
            <h3 className="text-lg font-medium text-white">Risk Heatmap</h3>
            <span className="text-xs font-['JetBrains_Mono'] text-white/40 px-2 py-1 border border-white/10 rounded">LIVE</span>
          </div>

          <div className="w-full h-64 -ml-4">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data} margin={{ top: 10, right: 0, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorRisk" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#fff" stopOpacity={0.2}/>
                    <stop offset="95%" stopColor="#fff" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <XAxis dataKey="name" stroke="rgba(255,255,255,0.2)" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis stroke="rgba(255,255,255,0.2)" fontSize={12} tickLine={false} axisLine={false} />
                <Tooltip
                  contentStyle={{ backgroundColor: 'rgba(0,0,0,0.8)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }}
                  itemStyle={{ color: '#fff' }}
                />
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                <Area type="monotone" dataKey="risk" stroke="#fff" fillOpacity={1} fill="url(#colorRisk)" animationDuration={2000} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </motion.div>

      </div>
    </section>
  );
};
