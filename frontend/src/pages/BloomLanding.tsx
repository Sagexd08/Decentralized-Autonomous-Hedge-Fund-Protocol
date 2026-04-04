import { BentoDemo } from "@/components/BentoDemo";
import { Sparkles, Download, Wand2, BookOpen, ArrowRight, Twitter, Linkedin, Instagram, Menu } from "lucide-react";
import React from "react";

export default function BloomLanding() {
  return (
    <div className="relative min-h-screen bg-black overflow-hidden font-sans text-white selection:bg-white/20">
      {/* Background Video */}
      <video
        autoPlay
        loop
        muted
        playsInline
        className="absolute inset-0 w-full h-full object-cover z-0 opacity-50"
      >
        <source src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260315_073750_51473149-4350-4920-ae24-c8214286f323.mp4" type="video/mp4" />
      </video>

      {/* Main Content Layout */}
      <div className="relative z-10 flex flex-col lg:flex-row min-h-screen p-4 lg:p-6 gap-6 max-w-screen-2xl mx-auto">
        
        {/* Left Panel */}
        <div className="relative flex flex-col flex-1 lg:w-[52%] min-h-[calc(100vh-2rem)] rounded-3xl overflow-hidden p-8 liquid-glass-strong">
          
          {/* Top Nav */}
          <header className="flex items-center justify-between z-20">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center backdrop-blur-md">
                <span className="text-xl">❋</span>
              </div>
              <span className="font-semibold text-2xl tracking-tighter">bloom</span>
            </div>
            <button className="flex items-center justify-center w-12 h-12 rounded-full liquid-glass hover:scale-105 active:scale-95 transition-transform">
              <Menu size={20} className="text-white" />
            </button>
          </header>

          {/* Hero Content */}
          <main className="flex-1 flex flex-col items-center justify-center mt-12 mb-12 text-center z-20">
            <div className="w-20 h-20 rounded-full bg-white/10 flex items-center justify-center backdrop-blur-md mb-8">
              <span className="text-4xl text-white">❋</span>
            </div>
            
            <h1 className="text-5xl md:text-6xl lg:text-7xl font-medium tracking-tight mb-10 max-w-2xl leading-[1.1]">
              Innovating the <br/>
              <span className="font-serif italic text-white/80">spirit of bloom</span> AI
            </h1>

            <button className="flex items-center gap-3 pl-6 pr-2 py-2 rounded-full liquid-glass-strong hover:scale-105 active:scale-95 transition-transform group">
              <span className="text-sm font-medium tracking-wide">Explore Now</span>
              <div className="w-10 h-10 rounded-full bg-white/15 flex items-center justify-center">
                <Download size={16} className="text-white group-hover:translate-y-0.5 transition-transform" />
              </div>
            </button>

            <div className="flex flex-wrap justify-center gap-3 mt-12">
              {['Artistic Gallery', 'AI Generation', '3D Structures'].map((label) => (
                <div key={label} className="px-5 py-2.5 rounded-full liquid-glass text-xs font-medium text-white/80 hover:text-white transition-colors cursor-pointer">
                  {label}
                </div>
              ))}
            </div>
          </main>

          {/* Bottom Quote */}
          <footer className="mt-auto flex flex-col items-center text-center z-20 pb-4">
            <p className="text-[10px] tracking-[0.2em] font-semibold text-white/50 mb-3">VISIONARY DESIGN</p>
            <p className="text-lg md:text-xl font-medium text-white/90 mb-4 max-w-md">
              "<span className="font-serif italic">We imagined</span> a realm with <span className="font-serif italic">no ending</span>."
            </p>
            <div className="flex items-center gap-4 text-white/40">
              <div className="w-8 h-[1px] bg-white/20"></div>
              <p className="text-[10px] tracking-widest uppercase">MARCUS AURELIO</p>
              <div className="w-8 h-[1px] bg-white/20"></div>
            </div>
          </footer>
        </div>

        {/* Right Panel (Desktop Only) */}
        <div className="hidden lg:flex lg:w-[48%] flex-col gap-6">
          
          {/* Top Bar */}
          <div className="flex justify-between items-center z-10 w-full pl-4 pr-12 mt-2">
            <div className="flex items-center gap-2 px-6 py-3 rounded-full liquid-glass">
              <a href="#" className="text-white/70 hover:text-white transition-colors"><Twitter size={16} /></a>
              <div className="w-[1px] h-4 bg-white/20 mx-2"></div>
              <a href="#" className="text-white/70 hover:text-white transition-colors"><Linkedin size={16} /></a>
              <div className="w-[1px] h-4 bg-white/20 mx-2"></div>
              <a href="#" className="text-white/70 hover:text-white transition-colors"><Instagram size={16} /></a>
              <div className="w-[1px] h-4 bg-white/20 mx-2"></div>
              <a href="#" className="text-white/70 hover:text-white flex items-center transition-colors">
                <ArrowRight size={16} />
              </a>
            </div>

            <button className="flex items-center gap-3 pl-4 pr-2 py-2 rounded-full liquid-glass hover:scale-105 transition-transform">
              <span className="text-sm font-medium">Account</span>
              <div className="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center">
                <Sparkles size={14} className="text-white" />
              </div>
            </button>
          </div>

          {/* Right Content Area */}
          <div className="flex flex-col flex-1 justify-between z-10">
            {/* Enter Ecosystem snippet */}
            <div className="w-64 p-6 rounded-3xl liquid-glass self-end mr-4 hover:scale-[1.02] transition-transform cursor-pointer">
              <h3 className="font-semibold text-lg mb-2">Enter our <br/><span className="font-serif italic">ecosystem</span></h3>
              <p className="text-xs text-white/60 leading-relaxed">
                Experience generative botany through our neural pathways and discover new floral structures.
              </p>
            </div>

            {/* Bottom Widget Area */}
            <div className="relative mt-8 p-4 liquid-glass rounded-[3rem]">
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div className="p-6 rounded-3xl liquid-glass-strong group hover:bg-white/[0.05] transition-all cursor-pointer">
                  <div className="w-10 h-10 rounded-full bg-white/10 flex items-center justify-center mb-6">
                    <Wand2 size={18} className="text-white group-hover:rotate-12 transition-transform" />
                  </div>
                  <h4 className="font-medium mb-1">Processing</h4>
                  <p className="text-xs text-white/50">Active neural rendering</p>
                </div>
                <div className="p-6 rounded-3xl liquid-glass-strong group hover:bg-white/[0.05] transition-all cursor-pointer">
                  <div className="w-10 h-10 rounded-full bg-white/10 flex items-center justify-center mb-6">
                    <BookOpen size={18} className="text-white group-hover:-rotate-12 transition-transform" />
                  </div>
                  <h4 className="font-medium mb-1">Growth Archive</h4>
                  <p className="text-xs text-white/50">Browse past generations</p>
                </div>
              </div>
              
              <div className="p-4 rounded-3xl liquid-glass-strong flex items-center gap-4 group cursor-pointer hover:bg-white/[0.05] transition-all">
                <div className="w-24 h-16 rounded-xl overflow-hidden relative">
                  {/* Placeholder for flower thumbnail */}
                  <img src="https://images.unsplash.com/photo-1546842931-886c185b4c8c?auto=format&fit=crop&q=80&w=200&h=150" alt="Flower render" className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-700" />
                </div>
                <div className="flex-1">
                  <h4 className="font-medium text-sm">Advanced Plant Sculpting</h4>
                  <p className="text-xs text-white/50">Next-gen taxonomy generation</p>
                </div>
                <button className="w-10 h-10 rounded-full liquid-glass flex items-center justify-center mr-2 hover:bg-white/20 transition-colors">
                  <span className="text-xl font-light">+</span>
                </button>
              </div>
            </div>
            
            <div className="mt-8 scale-90 origin-bottom-right opacity-80 pointer-events-none">
              {/* Optional: Add a subtle glow behind bento demo if needed */}
              <div className="absolute inset-0 bg-white/5 blur-[100px] rounded-full z-[-1]" />
            </div>

          </div>
        </div>
      </div>
      
      {/* Include CSS styles in the global CSS or as style tag here */}
      <style dangerouslySetInnerHTML={{__html: `
        :root {
          --radius: 1rem;
        }
        @layer components {
          .liquid-glass {
            background: rgba(255,255,255,0.01);
            background-blend-mode: luminosity;
            backdrop-filter: blur(4px);
            border: none;
            box-shadow: inset 0 1px 1px rgba(255,255,255,0.1);
            position: relative;
            overflow: hidden;
          }
          .liquid-glass::before {
            content: '';
            position: absolute;
            inset: 0;
            border-radius: inherit;
            padding: 1.4px;
            background: linear-gradient(180deg, rgba(255,255,255,0.45) 0%, rgba(255,255,255,0.15) 20%, transparent 40%, transparent 60%, rgba(255,255,255,0.15) 80%, rgba(255,255,255,0.45) 100%);
            -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
            -webkit-mask-composite: xor;
            mask-composite: exclude;
            pointer-events: none;
          }
          .liquid-glass-strong {
            background: rgba(255,255,255,0.02);
            background-blend-mode: luminosity;
            backdrop-filter: blur(50px);
            border: none;
            box-shadow: 4px 4px 4px rgba(0,0,0,0.05), inset 0 1px 1px rgba(255,255,255,0.15);
            position: relative;
            overflow: hidden;
          }
          .liquid-glass-strong::before {
            content: '';
            position: absolute;
            inset: 0;
            border-radius: inherit;
            padding: 1.4px;
            background: linear-gradient(180deg, rgba(255,255,255,0.5) 0%, rgba(255,255,255,0.2) 20%, transparent 40%, transparent 60%, rgba(255,255,255,0.2) 80%, rgba(255,255,255,0.5) 100%);
            -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
            -webkit-mask-composite: xor;
            mask-composite: exclude;
            pointer-events: none;
          }
        }
      `}} />
    </div>
  );
}
