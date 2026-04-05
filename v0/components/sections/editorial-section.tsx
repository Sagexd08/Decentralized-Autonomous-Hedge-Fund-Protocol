"use client";

import Image from "next/image";

const specs = [
  { label: "Chains", value: "Multi" },
  { label: "Agents", value: "100+" },
  { label: "Risk Pools", value: "3" },
  { label: "Uptime", value: "99.9%" },
];

export function EditorialSection() {
  return (
    <section className="bg-transparent">
      {/* Specs Grid */}
      <div className="grid grid-cols-2 border-t border-border md:grid-cols-4">
        {specs.map((spec) => (
          <div
            key={spec.label}
            className="border-b border-r border-border p-8 text-center last:border-r-0 md:border-b-0"
          >
            <p className="mb-2 text-xs font-mono uppercase tracking-[0.2em] text-primary">
              {spec.label}
            </p>
            <p className="font-medium text-foreground text-4xl">
              {spec.value}
            </p>
          </div>
        ))}
      </div>

      {/* Full-width Visual */}
      <div className="relative aspect-[16/9] w-full md:aspect-[21/9]">
        <Image
          src="/images/dacap-organism.jpg"
          alt="DACAP Protocol Visualization"
          fill
          className="object-cover"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-background via-background/30 to-transparent" />
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="text-center px-6">
            <p className="text-xs font-mono uppercase tracking-[0.3em] text-primary mb-4">
              Autonomous Capital Brain
            </p>
            <h2 className="text-3xl md:text-5xl lg:text-6xl font-medium text-white tracking-tight text-balance">
              Capital that allocates,
              <br />
              learns, and defends itself.
            </h2>
          </div>
        </div>
      </div>
    </section>
  );
}
