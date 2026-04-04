"use client";

import Image from "next/image";
import { useEffect, useRef, useState, useCallback } from "react";

export function PhilosophySection() {
  const sectionRef = useRef<HTMLDivElement>(null);
  const [onchainTranslateX, setOnchainTranslateX] = useState(-100);
  const [offchainTranslateX, setOffchainTranslateX] = useState(100);
  const [titleOpacity, setTitleOpacity] = useState(1);
  const rafRef = useRef<number | null>(null);

  const updateTransforms = useCallback(() => {
    if (!sectionRef.current) return;
    
    const rect = sectionRef.current.getBoundingClientRect();
    const windowHeight = window.innerHeight;
    const sectionHeight = sectionRef.current.offsetHeight;
    
    // Calculate progress based on scroll position
    const scrollableRange = sectionHeight - windowHeight;
    const scrolled = -rect.top;
    const progress = Math.max(0, Math.min(1, scrolled / scrollableRange));
    
    // Onchain comes from left (-100% to 0%)
    setOnchainTranslateX((1 - progress) * -100);
    
    // Offchain comes from right (100% to 0%)
    setOffchainTranslateX((1 - progress) * 100);
    
    // Title fades out as blocks come together
    setTitleOpacity(1 - progress);
  }, []);

  useEffect(() => {
    const handleScroll = () => {
      // Cancel any pending animation frame
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
      }
      
      // Use requestAnimationFrame for smooth updates
      rafRef.current = requestAnimationFrame(updateTransforms);
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    updateTransforms();
    
    return () => {
      window.removeEventListener("scroll", handleScroll);
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
      }
    };
  }, [updateTransforms]);

  return (
    <section id="protocol" className="bg-transparent">
      {/* Scroll-Animated Split Architecture */}
      <div ref={sectionRef} className="relative" style={{ height: "200vh" }}>
        <div className="sticky top-0 h-screen flex items-center justify-center">
          <div className="relative w-full">
            {/* Title - positioned behind the blocks */}
            <div 
              className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none z-0 px-6"
              style={{ opacity: titleOpacity }}
            >
              <p className="text-xs font-mono uppercase tracking-[0.3em] text-primary mb-6">
                Protocol Architecture
              </p>
              <h2 className="text-[10vw] font-medium leading-[0.95] tracking-tighter text-foreground md:text-[8vw] lg:text-[6vw] text-center text-balance">
                On-chain discipline
                <br />
                <span className="text-muted-foreground">x</span> off-chain intelligence
              </h2>
            </div>

            {/* Architecture Grid */}
            <div className="relative z-10 grid grid-cols-1 gap-4 px-6 md:grid-cols-2 md:px-12 lg:px-20">
              {/* On-chain - comes from left */}
              <div 
                className="relative aspect-[4/3] overflow-hidden rounded-2xl group"
                style={{
                  transform: `translate3d(${onchainTranslateX}%, 0, 0)`,
                  WebkitTransform: `translate3d(${onchainTranslateX}%, 0, 0)`,
                  backfaceVisibility: 'hidden',
                  WebkitBackfaceVisibility: 'hidden',
                }}
              >
                <Image
                  src="/images/dacap-onchain.jpg"
                  alt="On-chain custody and enforcement"
                  fill
                  className="object-cover"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-background via-background/40 to-transparent" />
                <div className="absolute bottom-6 left-6 right-6">
                  <span className="glass-accent px-4 py-2 text-xs font-mono uppercase tracking-wider rounded-full text-primary inline-block mb-3">
                    Custody & Enforcement
                  </span>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    Smart contracts control vaults, allocations, and risk boundaries so capital never depends on blind trust.
                  </p>
                </div>
              </div>

              {/* Off-chain - comes from right */}
              <div 
                className="relative aspect-[4/3] overflow-hidden rounded-2xl group"
                style={{
                  transform: `translate3d(${offchainTranslateX}%, 0, 0)`,
                  WebkitTransform: `translate3d(${offchainTranslateX}%, 0, 0)`,
                  backfaceVisibility: 'hidden',
                  WebkitBackfaceVisibility: 'hidden',
                }}
              >
                <Image
                  src="/images/dacap-offchain.jpg"
                  alt="Off-chain adaptive intelligence"
                  fill
                  className="object-cover"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-background via-background/40 to-transparent" />
                <div className="absolute bottom-6 left-6 right-6">
                  <span className="glass-accent px-4 py-2 text-xs font-mono uppercase tracking-wider rounded-full text-primary inline-block mb-3">
                    Adaptive Intelligence
                  </span>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    Agents process market regimes, produce signed decisions, and compete for capital under transparent performance signals.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Description */}
      <div className="px-6 py-20 md:px-12 md:py-28 lg:px-20 lg:py-36 lg:pb-14">
        <div className="text-center">
          <p className="text-xs font-mono uppercase tracking-[0.3em] text-primary">
            Protocol Thesis
          </p>
          <p className="mt-8 leading-relaxed text-muted-foreground text-2xl md:text-3xl text-center max-w-4xl mx-auto text-balance">
            DACAP is a decentralized capital allocation system where investor funds remain under protocol control, 
            autonomous agents compete through measurable performance, and governance steers the rules of adaptation 
            without breaking custody assumptions.
          </p>
        </div>
      </div>
    </section>
  );
}
