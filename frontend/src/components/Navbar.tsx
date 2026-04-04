import React from 'react';
import { motion } from 'framer-motion';

export const Navbar = () => {
  return (
    <motion.nav 
      initial={{ y: -50, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
      className="fixed top-6 left-1/2 -translate-x-1/2 z-50 flex items-center justify-between px-6 py-3 w-[90%] max-w-5xl rounded-full liquid-glass"
    >
      <div className="flex items-center gap-8">
        <a href="#" className="text-xl font-bold tracking-widest text-white">DACAP</a>
        <div className="hidden md:flex items-center gap-6">
          <a href="#dashboard" className="text-sm text-white/70 hover:text-white transition-colors">Dashboard</a>
          <a href="#agents" className="text-sm text-white/70 hover:text-white transition-colors">Agents</a>
          <a href="#intelligence" className="text-sm text-white/70 hover:text-white transition-colors">Intelligence</a>
          <a href="#governance" className="text-sm text-white/70 hover:text-white transition-colors">Governance</a>
        </div>
      </div>
      <div className="flex items-center gap-4">
        <button className="hidden md:block text-sm text-white/70 hover:text-white transition-colors">Login</button>
        <button className="px-5 py-2 text-sm font-medium text-black bg-white rounded-full hover:bg-white/90 transition-colors">
          Enter System
        </button>
      </div>
    </motion.nav>
  );
};
