import React from 'react';
import { Navbar } from '../components/Navbar';
import { Hero } from '../components/Hero';
import { Globe } from '../components/Globe';
import { About } from '../components/About';
import { VideoSection } from '../components/VideoSection';
import { BentoSection } from '../components/BentoSection';
import { Intelligence } from '../components/Intelligence';
import { Risk } from '../components/Risk';
import { Philosophy } from '../components/Philosophy';
import { Services } from '../components/Services';

export default function Landing() {
  return (
    <div className="bg-black min-h-screen text-white font-sans overflow-x-hidden selection:bg-white/30">
      <Navbar />
      <Hero />
      <Globe />
      <About />
      <VideoSection />
      <BentoSection />
      <Intelligence />
      <Risk />
      <Philosophy />
      <Services />
    </div>
  );
}
