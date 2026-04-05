"use client";

import { FadeImage } from "@/components/fade-image";

const capabilities = [
  {
    id: 1,
    name: "Multi-Chain Vault Custody",
    description: "Protocol-controlled vaults across EVM chains with unified risk management",
    status: "Live",
    image: "/images/dacap-vault.jpg",
  },
  {
    id: 2,
    name: "Agent Performance Oracle",
    description: "On-chain attestation of off-chain agent performance metrics",
    status: "Live",
    image: "/images/dacap-agents.jpg",
  },
  {
    id: 3,
    name: "Multiplicative Weights Engine",
    description: "Regret-minimizing allocation updates with configurable learning rate",
    status: "Live",
    image: "/images/dacap-allocation.jpg",
  },
  {
    id: 4,
    name: "Volatility Budget Enforcement",
    description: "Real-time VaR and drawdown limit monitoring with automatic rebalancing",
    status: "Beta",
    image: "/images/dacap-slashing.jpg",
  },
  {
    id: 5,
    name: "Governance Parameter DAO",
    description: "Token-weighted voting on learning rates, risk thresholds, and agent caps",
    status: "Live",
    image: "/images/dacap-governance.jpg",
  },
  {
    id: 6,
    name: "World Event Integration",
    description: "Macro regime detection and geopolitical risk signal aggregation",
    status: "Beta",
    image: "/images/dacap-world-intel.jpg",
  },
];

export function CollectionSection() {
  return (
    <section id="capabilities" className="bg-transparent">
      {/* Section Title */}
      <div className="px-6 py-20 md:px-12 lg:px-20 md:py-10">
        <p className="text-xs font-mono uppercase tracking-[0.3em] text-primary mb-4">
          Infrastructure
        </p>
        <h2 className="text-3xl font-medium tracking-tight text-foreground md:text-4xl">
          Protocol Capabilities
        </h2>
      </div>

      {/* Capabilities Grid/Carousel */}
      <div className="pb-24">
        {/* Mobile: Horizontal Carousel */}
        <div className="flex gap-6 overflow-x-auto px-6 pb-4 md:hidden snap-x snap-mandatory scrollbar-hide">
          {capabilities.map((capability) => (
            <div key={capability.id} className="group flex-shrink-0 w-[75vw] snap-center">
              {/* Image */}
              <div className="relative aspect-[2/3] overflow-hidden rounded-2xl bg-secondary">
                <FadeImage
                  src={capability.image || "/placeholder.svg"}
                  alt={capability.name}
                  fill
                  className="object-cover group-hover:scale-105"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-background via-background/30 to-transparent" />
              </div>

              {/* Content */}
              <div className="py-6">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <h3 className="text-lg font-medium leading-snug text-foreground">
                      {capability.name}
                    </h3>
                    <p className="mt-2 text-sm text-muted-foreground">
                      {capability.description}
                    </p>
                  </div>
                  <span className={`text-xs font-mono uppercase tracking-wider px-3 py-1 rounded-full ${capability.status === 'Live' ? 'glass-accent text-primary' : 'glass text-amber-400'}`}>
                    {capability.status}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Desktop: Grid */}
        <div className="hidden md:grid md:grid-cols-3 gap-8 md:px-12 lg:px-20">
          {capabilities.map((capability) => (
            <div key={capability.id} className="group">
              {/* Image */}
              <div className="relative aspect-[2/3] overflow-hidden rounded-2xl bg-secondary">
                <FadeImage
                  src={capability.image || "/placeholder.svg"}
                  alt={capability.name}
                  fill
                  className="object-cover group-hover:scale-105"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-background via-background/30 to-transparent" />
              </div>

              {/* Content */}
              <div className="py-6">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <h3 className="text-lg font-medium leading-snug text-foreground">
                      {capability.name}
                    </h3>
                    <p className="mt-2 text-sm text-muted-foreground">
                      {capability.description}
                    </p>
                  </div>
                  <span className={`text-xs font-mono uppercase tracking-wider px-3 py-1 rounded-full flex-shrink-0 ${capability.status === 'Live' ? 'glass-accent text-primary' : 'glass text-amber-400'}`}>
                    {capability.status}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
