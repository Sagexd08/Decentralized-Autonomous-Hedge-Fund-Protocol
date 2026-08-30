"use client";

import { FadeImage } from "@/components/fade-image";

const features = [
  {
    title: "Risk Pools",
    description: "Capital Tiers",
    body: "Conservative, Balanced, and Aggressive pools with enforced volatility budgets and visible capacity.",
    image: "/images/iris-risk-pools.jpg",
  },
  {
    title: "Agent Marketplace",
    description: "Strategy Competition",
    body: "Autonomous strategies compete for stake, trust, and delegated capital allocation.",
    image: "/images/iris-marketplace.jpg",
  },
  {
    title: "Allocation Engine",
    description: "Capital Rotation",
    body: "Capital rotates toward the strongest agents using measurable, regret-aware reweighting logic.",
    image: "/images/iris-allocation.jpg",
  },
  {
    title: "Governance DAO",
    description: "Collective Control",
    body: "Parameter changes, slashing thresholds, and learning behavior evolve through collective control.",
    image: "/images/iris-governance.jpg",
  },
  {
    title: "Risk Enforcement",
    description: "Slashing Engine",
    body: "Underperforming or rogue agents are penalized through automated drawdown limits and stake slashing.",
    image: "/images/iris-slashing.jpg",
  },
  {
    title: "World Intelligence",
    description: "Macro Signals",
    body: "Global market regimes, geopolitical events, and liquidity conditions feed into agent decision models.",
    image: "/images/iris-world-intel.jpg",
  },
];

export function FeaturedProductsSection() {
  return (
    <section id="modules" className="bg-transparent">
      {/* Section Title */}
      <div className="px-6 py-20 text-center md:px-12 md:py-28 lg:px-20 lg:py-32 lg:pb-20">
        <p className="text-xs font-mono uppercase tracking-[0.3em] text-primary mb-6">
          Protocol Modules
        </p>
        <h2 className="text-3xl font-medium tracking-tight text-foreground md:text-4xl lg:text-5xl text-balance">
          The building blocks of
          <br />
          autonomous capital allocation.
        </h2>
      </div>

      {/* Features Grid */}
      <div className="grid grid-cols-1 gap-4 px-6 pb-20 md:grid-cols-2 lg:grid-cols-3 md:px-12 lg:px-20">
        {features.map((feature) => (
          <div key={feature.title} className="group">
            {/* Image */}
            <div className="relative aspect-[4/3] overflow-hidden rounded-2xl">
              <FadeImage
                src={feature.image || "/placeholder.svg"}
                alt={feature.title}
                fill
                className="object-cover group-hover:scale-105"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-background via-background/20 to-transparent" />
            </div>

            {/* Content */}
            <div className="py-6">
              <p className="mb-2 text-xs font-mono uppercase tracking-[0.2em] text-primary">
                {feature.description}
              </p>
              <h3 className="text-foreground text-xl font-semibold mb-2">
                {feature.title}
              </h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                {feature.body}
              </p>
            </div>
          </div>
        ))}
      </div>

      {/* CTA Link */}
      <div className="flex justify-center px-6 pb-28 md:px-12 lg:px-20">
        
      </div>
    </section>
  );
}
