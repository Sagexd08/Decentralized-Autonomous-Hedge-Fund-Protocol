"use client";

import Image from "next/image";

export function TestimonialsSection() {
  return (
    <section id="about" className="bg-transparent">
      {/* Large Text Statement */}
      <div className="px-6 py-24 md:px-12 md:py-32 lg:px-20 lg:py-40">
        <p className="mx-auto max-w-5xl text-2xl leading-relaxed text-foreground md:text-3xl lg:text-[2.5rem] lg:leading-snug text-balance">
          IRIS Protocol represents a paradigm shift in capital management: a decentralized system where 
          AI agents compete for allocation under transparent performance metrics, capital custody 
          remains under protocol control, and governance evolves the system through collective intelligence.
        </p>
      </div>

      {/* About Image */}
      <div className="relative aspect-[16/9] w-full">
        <Image
          src="/images/iris-hero.jpg"
          alt="IRIS Protocol Infrastructure"
          fill
          className="object-cover"
        />
        {/* Fade gradient overlay */}
        <div className="absolute inset-0 bg-gradient-to-t from-background via-background/60 to-transparent" />
        
        {/* Overlay Content */}
        <div className="absolute inset-0 flex items-end pb-12 md:pb-20 lg:pb-28">
          <div className="px-6 md:px-12 lg:px-20 w-full">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-5xl">
              <div className="glass-subtle p-6 rounded-2xl">
                <p className="text-xs font-mono uppercase tracking-[0.2em] text-primary mb-2">
                  Capital Custody
                </p>
                <p className="text-sm text-muted-foreground">
                  Investor funds remain in protocol-controlled vaults, never delegated to external custody.
                </p>
              </div>
              <div className="glass-subtle p-6 rounded-2xl">
                <p className="text-xs font-mono uppercase tracking-[0.2em] text-primary mb-2">
                  Agent Competition
                </p>
                <p className="text-sm text-muted-foreground">
                  Autonomous strategies earn allocation through measurable performance, not promises.
                </p>
              </div>
              <div className="glass-subtle p-6 rounded-2xl">
                <p className="text-xs font-mono uppercase tracking-[0.2em] text-primary mb-2">
                  Governance Control
                </p>
                <p className="text-sm text-muted-foreground">
                  Protocol parameters evolve through collective decision-making and transparent voting.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
