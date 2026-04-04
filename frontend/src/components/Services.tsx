import React from 'react';
import { motion } from 'framer-motion';
import { useInViewAnimation } from '../hooks/useInViewAnimation';

export const Services = () => {
  const { ref, isInView } = useInViewAnimation("-50px");

  const cards = [
    {
      title: "Autonomous Trading",
      desc: "Algorithmic strategies executed at machine speed, completely detached from human cognitive bias.",
      video: "https://videos.pexels.com/video-files/854400/854400-hd_1920_1080_25fps.mp4"
    },
    {
      title: "AI Agents",
      desc: "Deploy, train, and manage specialized neural networks designed for exact asset classes and micro-markets.",
      video: "https://videos.pexels.com/video-files/3129977/3129977-hd_1920_1080_25fps.mp4"
    }
  ];

  const container = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: { staggerChildren: 0.2 }
    }
  };

  const item = {
    hidden: { opacity: 0, y: 30 },
    show: { opacity: 1, y: 0, transition: { duration: 0.8, ease: [0.16, 1, 0.3, 1] } }
  };

  return (
    <section className="bg-black py-24 px-6 border-t border-white/5" ref={ref}>
      <div className="max-w-7xl mx-auto flex flex-col gap-12">
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 20 }}
          transition={{ duration: 0.8 }}
        >
          <p className="text-white/40 tracking-[0.2em] text-xs font-semibold uppercase mb-4 drop-shadow-lg">Capabilities</p>
          <h2 className="text-3xl md:text-5xl font-medium tracking-tight text-white">
            System Services
          </h2>
        </motion.div>

        <motion.div 
          className="grid grid-cols-1 md:grid-cols-2 gap-8"
          variants={container}
          initial="hidden"
          animate={isInView ? "show" : "hidden"}
        >
          {cards.map((card, idx) => (
            <motion.div 
              key={idx}
              variants={item}
              className="relative aspect-square md:aspect-auto md:h-[500px] rounded-[2rem] overflow-hidden group cursor-pointer"
            >
              <div className="absolute inset-0 bg-gradient-to-t from-black via-black/40 to-transparent z-10" />
              <video
                src={card.video}
                autoPlay
                muted
                loop
                playsInline
                preload="auto"
                className="absolute inset-0 w-full h-full object-cover scale-105 group-hover:scale-110 transition-transform duration-1000 ease-out opacity-80 group-hover:opacity-100"
              />
              
              <div className="absolute inset-0 z-20 flex flex-col justify-end p-8 md:p-12">
                <div className="liquid-glass p-6 md:p-8 rounded-2xl transform translate-y-4 group-hover:translate-y-0 transition-transform duration-500 ease-out backdrop-blur-2xl">
                  <h3 className="text-2xl md:text-3xl font-medium text-white mb-4">{card.title}</h3>
                  <p className="text-sm md:text-base text-white/60 font-light leading-relaxed">{card.desc}</p>
                </div>
              </div>
            </motion.div>
          ))}
        </motion.div>

      </div>
    </section>
  );
};
