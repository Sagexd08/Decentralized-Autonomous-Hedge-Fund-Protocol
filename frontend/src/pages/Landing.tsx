import { Menu, Sparkles, Download, Wand2, BookOpen, ArrowRight, Twitter, Linkedin, Instagram } from "lucide-react";
import { Globe3DDemo } from "@/components/ui/3d-globe";

export default function Landing() {
  return (
    <div className="relative min-h-screen w-full bg-black overflow-hidden font-poppins selection:bg-white/20">
      {/* Background Video */}
      <video
        autoPlay
        loop
        muted
        playsInline
        className="absolute inset-0 w-full h-full object-cover z-0 opacity-40"
        src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260315_073750_51473149-4350-4920-ae24-c8214286f323.mp4"
      />

      <div className="relative z-10 flex flex-col lg:flex-row min-h-screen p-4 lg:p-6 gap-4">
        {/* Left Panel */}
        <div className="relative w-full lg:w-[52%] flex flex-col rounded-3xl liquid-glass-strong p-6 lg:p-10 shrink-0">
          
          {/* Nav */}
          <nav className="flex items-center justify-between w-full">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center backdrop-blur-md">
                <Sparkles size={16} className="text-white" />
              </div>
              <span className="font-semibold text-2xl tracking-tighter text-white">bloom</span>
            </div>
            <button className="liquid-glass rounded-full px-4 py-2 flex items-center gap-2 hover:scale-105 active:scale-95 transition-transform">
              <span className="text-sm font-medium text-white">Menu</span>
              <Menu size={16} className="text-white" />
            </button>
          </nav>

          {/* Hero Content */}
          <div className="flex-1 flex flex-col justify-center items-center text-center mt-12 mb-12">
            <div className="w-20 h-20 rounded-2xl bg-white/10 flex items-center justify-center backdrop-blur-xl mb-8 border border-white/20 shadow-xl">
               <Sparkles size={32} className="text-white" />
            </div>
            
            <h1 className="text-5xl lg:text-7xl font-medium tracking-tight text-white leading-[1.1] mb-10 max-w-2xl">
              Innovating the <br />
              <span className="font-serif italic text-white/80 font-normal">spirit of bloom</span> AI
            </h1>

            <button className="liquid-glass-strong rounded-full pl-6 pr-2 py-2 flex items-center gap-4 hover:scale-105 active:scale-95 transition-transform mb-12 group">
              <span className="text-base font-semibold text-white">Explore Now</span>
              <div className="w-8 h-8 rounded-full bg-white/15 flex items-center justify-center transition-colors group-hover:bg-white/25">
                <Download size={14} className="text-white" />
              </div>
            </button>

            <div className="flex flex-wrap justify-center gap-3">
              {["Artistic Gallery", "AI Generation", "3D Structures"].map((text) => (
                <div key={text} className="liquid-glass rounded-full px-4 py-2 text-xs font-medium text-white/80 hover:text-white transition-colors cursor-default">
                  {text}
                </div>
              ))}
            </div>
          </div>

          {/* Bottom Quote */}
          <div className="mt-auto text-center">
            <p className="text-[10px] sm:text-xs tracking-[0.2em] font-medium text-white/40 uppercase mb-4">
              Visionary Design
            </p>
            <p className="text-lg lg:text-xl text-white/90 mb-4 font-light">
              <span className="font-serif italic">"We imagined a realm </span>
              with no ending."
            </p>
            <div className="flex items-center justify-center gap-4 opacity-70">
              <div className="h-px bg-white/20 w-8" />
              <span className="text-[10px] tracking-widest text-white/60 font-medium uppercase">Marcus Aurelio</span>
              <div className="h-px bg-white/20 w-8" />
            </div>
          </div>
        </div>

        {/* Right Panel (Desktop only) */}
        <div className="hidden lg:flex w-[48%] flex-col gap-4">
          
          {/* Top Bar */}
          <div className="flex items-center justify-between">
            <div className="liquid-glass rounded-full px-4 py-2 flex items-center gap-4">
              <a href="#" className="w-8 h-8 rounded-full bg-white/5 flex items-center justify-center text-white/70 hover:text-white hover:bg-white/10 transition-all hover:scale-105">
                <Twitter size={14} />
              </a>
              <a href="#" className="w-8 h-8 rounded-full bg-white/5 flex items-center justify-center text-white/70 hover:text-white hover:bg-white/10 transition-all hover:scale-105">
                <Linkedin size={14} />
              </a>
              <a href="#" className="w-8 h-8 rounded-full bg-white/5 flex items-center justify-center text-white/70 hover:text-white hover:bg-white/10 transition-all hover:scale-105">
                <Instagram size={14} />
              </a>
              <div className="w-px h-4 bg-white/20 mx-1" />
              <button className="text-white hover:translate-x-1 transition-transform p-1">
                <ArrowRight size={16} />
              </button>
            </div>
            
             <button className="liquid-glass rounded-full px-5 py-2.5 flex items-center gap-2 hover:scale-105 active:scale-95 transition-transform">
              <Sparkles size={14} className="text-white" />
              <span className="text-sm font-medium text-white">Account</span>
            </button>
          </div>

          {/* Community Card */}
          <div className="liquid-glass rounded-3xl p-5 w-64 mt-4 self-end hover:scale-[1.02] transition-transform">
             <div className="w-10 h-10 rounded-full bg-white/10 flex items-center justify-center mb-3 border border-white/10">
                <Globe3DDemo />
             </div>
             <h3 className="text-white font-medium text-sm mb-1">Enter our ecosystem</h3>
             <p className="text-white/50 text-xs">Join thousands of creators shaping the future of digital flora.</p>
          </div>

          {/* Bottom Features Container */}
          <div className="liquid-glass rounded-[2.5rem] p-4 mt-auto flex flex-col gap-4">
             <div className="flex gap-4">
                <div className="flex-1 liquid-glass rounded-3xl p-5 flex items-center gap-4 hover:scale-[1.02] transition-transform cursor-pointer">
                   <div className="w-12 h-12 rounded-full bg-white/10 flex items-center justify-center shrink-0">
                      <Wand2 size={20} className="text-white" />
                   </div>
                   <div>
                     <h4 className="text-white font-medium text-sm">Processing</h4>
                     <p className="text-white/50 text-xs mt-0.5">Real-time render</p>
                   </div>
                </div>
                <div className="flex-1 liquid-glass rounded-3xl p-5 flex items-center gap-4 hover:scale-[1.02] transition-transform cursor-pointer">
                   <div className="w-12 h-12 rounded-full bg-white/10 flex items-center justify-center shrink-0">
                      <BookOpen size={20} className="text-white" />
                   </div>
                   <div>
                     <h4 className="text-white font-medium text-sm">Growth Archive</h4>
                     <p className="text-white/50 text-xs mt-0.5">Saved states</p>
                   </div>
                </div>
             </div>

             <div className="liquid-glass rounded-3xl p-4 flex items-center gap-4 group cursor-pointer overflow-hidden relative">
                {/* Globe embedded inside bottom card as visual element */}
                <div className="w-24 h-16 rounded-2xl bg-white/5 shrink-0 overflow-hidden relative">
                    <div className="absolute inset-0 scale-[3] pointer-events-none opacity-50">
                        <Globe3DDemo />
                    </div>
                </div>
                
                <div className="flex-1">
                  <h4 className="text-white font-medium text-sm">Advanced Plant Sculpting</h4>
                  <p className="text-white/50 text-xs mt-1">Procedural generation tools</p>
                </div>

                <div className="w-10 h-10 rounded-full liquid-glass-strong flex items-center justify-center group-hover:scale-110 transition-transform">
                  <span className="text-white text-xl font-light leading-none">+</span>
                </div>
             </div>
          </div>

        </div>
      </div>
    </div>
  );
}
