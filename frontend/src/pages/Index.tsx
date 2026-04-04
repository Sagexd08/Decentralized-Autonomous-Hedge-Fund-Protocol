import { useEffect, useRef } from 'react';
import { Globe, ArrowRight, Instagram, Twitter } from 'lucide-react';
import AboutSection from '../components/AboutSection';
import FeaturedVideoSection from '../components/FeaturedVideoSection';
import PhilosophySection from '../components/PhilosophySection';
import ServicesSection from '../components/ServicesSection';

export default function Index() {
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    let animationFrameId: number;
    let fadeStartTime: number;
    let fadingIn = false;
    let fadingOut = false;

    const smoothFade = (timestamp: number) => {
      if (!fadeStartTime) fadeStartTime = timestamp;
      const elapsed = timestamp - fadeStartTime;
      
      if (fadingIn) {
        const opacity = Math.min(elapsed / 500, 1);
        if (video) video.style.opacity = opacity.toString();
        if (elapsed < 500) {
          animationFrameId = requestAnimationFrame(smoothFade);
        } else {
          fadingIn = false;
        }
      } else if (fadingOut) {
        const opacity = Math.max(1 - (elapsed / 500), 0);
        if (video) video.style.opacity = opacity.toString();
        if (elapsed < 500) {
          animationFrameId = requestAnimationFrame(smoothFade);
        } else {
          fadingOut = false;
        }
      }
    };

    const handleCanPlay = () => {
      if (!fadingIn && !fadingOut && video.style.opacity === "0" || video.style.opacity === "") {
        fadingIn = true;
        fadingOut = false;
        fadeStartTime = 0;
        cancelAnimationFrame(animationFrameId);
        animationFrameId = requestAnimationFrame(smoothFade);
      }
    };

    const handleTimeUpdate = () => {
      if (!video) return;
      if (!fadingOut && !fadingIn && video.duration && video.duration - video.currentTime <= 0.55) {
        fadingOut = true;
        fadeStartTime = 0;
        cancelAnimationFrame(animationFrameId);
        animationFrameId = requestAnimationFrame(smoothFade);
      }
    };

    const handleEnded = () => {
      if (!video) return;
      video.currentTime = 0;
      video.play().catch(e => console.error(e));
      fadingIn = true;
      fadingOut = false;
      fadeStartTime = 0;
      cancelAnimationFrame(animationFrameId);
      animationFrameId = requestAnimationFrame(smoothFade);
    };

    video.addEventListener('canplay', handleCanPlay);
    video.addEventListener('timeupdate', handleTimeUpdate);
    video.addEventListener('ended', handleEnded);

    return () => {
      video.removeEventListener('canplay', handleCanPlay);
      video.removeEventListener('timeupdate', handleTimeUpdate);
      video.removeEventListener('ended', handleEnded);
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return (
    <div className="bg-black min-h-screen font-sans">
      {/* SECTION 1: HERO */}
      <section className="min-h-screen bg-black flex flex-col relative overflow-hidden">
        <video
          ref={videoRef}
          src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260404_050931_6b868bbb-85a4-498d-921e-e815d5a55906.mp4"
          muted
          autoPlay
          playsInline
          preload="auto"
          className="absolute inset-0 w-full h-full object-cover translate-y-[calc(17%+100px)]"
          style={{ opacity: 0 }}
        />
        
        {/* Navbar */}
        <div className="relative z-20 w-full max-w-5xl mx-auto px-6 py-4 md:py-6 mt-4">
          <div className="liquid-glass rounded-full px-6 py-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Globe size={24} className="text-white" />
              <span className="text-white font-semibold text-lg">Asme</span>
            </div>
            
            <div className="hidden md:flex items-center gap-8">
              <a href="#" className="text-white/80 text-sm font-medium hover:text-white transition-colors">Features</a>
              <a href="#" className="text-white/80 text-sm font-medium hover:text-white transition-colors">Pricing</a>
              <a href="#" className="text-white/80 text-sm font-medium hover:text-white transition-colors">About</a>
            </div>
            
            <div className="flex items-center gap-4">
              <button className="text-white text-sm font-medium hidden sm:block">Sign Up</button>
              <button className="liquid-glass rounded-full px-6 py-2 text-white text-sm font-medium">
                Login
              </button>
            </div>
          </div>
        </div>

        {/* Hero content */}
        <div className="relative z-10 flex-1 flex flex-col items-center justify-center -translate-y-[20%] text-center px-4">
          <h1 
            className="text-5xl md:text-6xl lg:text-7xl text-white tracking-tight whitespace-nowrap mb-8"
            style={{ fontFamily: "'Instrument Serif', serif" }}
          >
            Built for the curious
          </h1>
          
          <div className="liquid-glass rounded-full pl-6 pr-2 py-2 flex flex-row items-center w-full max-w-[340px] sm:max-w-md mb-6">
            <input 
              type="email" 
              placeholder="Enter your email" 
              className="bg-transparent border-none outline-none text-white placeholder-white/40 flex-1 text-sm min-w-0"
            />
            <button className="bg-white rounded-full w-9 h-9 sm:w-10 sm:h-10 flex items-center justify-center shrink-0">
              <ArrowRight size={20} className="text-black" />
            </button>
          </div>
          
          <p className="text-white text-sm leading-relaxed px-4 max-w-md mb-8">
            Stay updated with the latest news and insights. Subscribe to our newsletter today and never miss out on exciting updates.
          </p>
          
          <button className="liquid-glass rounded-full px-8 py-3 text-white text-sm font-medium hover:bg-white/5 transition-colors">
            Manifesto
          </button>
        </div>

        {/* Social icons */}
        <div className="relative z-10 w-full flex justify-center gap-4 pb-10 mt-auto">
          <button className="liquid-glass rounded-full p-4 text-white/80 hover:text-white hover:bg-white/5 transition-colors">
            <Instagram size={20} />
          </button>
          <button className="liquid-glass rounded-full p-4 text-white/80 hover:text-white hover:bg-white/5 transition-colors">
            <Twitter size={20} />
          </button>
          <button className="liquid-glass rounded-full p-4 text-white/80 hover:text-white hover:bg-white/5 transition-colors">
            <Globe size={20} />
          </button>
        </div>
      </section>

      <AboutSection />
      <FeaturedVideoSection />
      <PhilosophySection />
      <ServicesSection />
    </div>
  );
}
