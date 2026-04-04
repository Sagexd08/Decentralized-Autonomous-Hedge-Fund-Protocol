"use client";

import Link from "next/link";

const footerLinks = {
  protocol: [
    { label: "Architecture", href: "#architecture" },
    { label: "Modules", href: "#modules" },
    { label: "Intelligence", href: "#intelligence" },
    { label: "Capabilities", href: "#capabilities" },
  ],
  resources: [
    { label: "Documentation", href: "#" },
    { label: "Whitepaper", href: "#" },
    { label: "Audits", href: "#" },
    { label: "GitHub", href: "#" },
  ],
  governance: [
    { label: "DAO Portal", href: "#" },
    { label: "Proposals", href: "#" },
    { label: "Treasury", href: "#" },
    { label: "Delegates", href: "#" },
  ],
};

export function FooterSection() {
  return (
    <footer className="bg-transparent">
      {/* CTA Banner */}
      <div className="px-6 py-20 md:px-12 md:py-28 lg:px-20 border-t border-border">
        <div className="text-center max-w-3xl mx-auto">
          <p className="text-xs font-mono uppercase tracking-[0.3em] text-primary mb-6">
            Join the Protocol
          </p>
          <h2 className="text-3xl md:text-4xl lg:text-5xl font-medium text-foreground tracking-tight mb-8 text-balance">
            Build the financial organism that allocates, learns, and defends itself.
          </h2>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <a 
            href="/dashboard" 
            className="px-8 py-3 text-sm font-medium rounded-full bg-primary text-primary-foreground hover:opacity-90 transition-all glow-cyan"
          >
            Enter Command Center
          </a>
            <a 
              href="#" 
              className="px-8 py-3 text-sm font-medium rounded-full glass text-foreground hover:bg-secondary/80 transition-all"
            >
              Read Documentation
            </a>
          </div>
        </div>
      </div>

      {/* Main Footer Content */}
      <div className="border-t border-border px-6 py-16 md:px-12 md:py-20 lg:px-20">
        <div className="grid grid-cols-2 gap-12 md:grid-cols-4 lg:grid-cols-5">
          {/* Brand */}
          <div className="col-span-2 md:col-span-1 lg:col-span-2">
            <Link href="/" className="flex items-center gap-2">
              <span className="text-lg font-semibold text-foreground">DACAP</span>
              <span className="text-[10px] font-mono uppercase tracking-widest text-primary">Protocol</span>
            </Link>
            <p className="mt-4 max-w-xs text-sm leading-relaxed text-muted-foreground">
              Decentralized Autonomous Capital Allocation Protocol. On-chain custody, off-chain intelligence, governance-controlled adaptation.
            </p>
          </div>

          {/* Protocol */}
          <div>
            <h4 className="mb-4 text-sm font-medium text-foreground">Protocol</h4>
            <ul className="space-y-3">
              {footerLinks.protocol.map((link) => (
                <li key={link.label}>
                  <Link
                    href={link.href}
                    className="text-sm text-muted-foreground transition-colors hover:text-foreground"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Resources */}
          <div>
            <h4 className="mb-4 text-sm font-medium text-foreground">Resources</h4>
            <ul className="space-y-3">
              {footerLinks.resources.map((link) => (
                <li key={link.label}>
                  <Link
                    href={link.href}
                    className="text-sm text-muted-foreground transition-colors hover:text-foreground"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Governance */}
          <div>
            <h4 className="mb-4 text-sm font-medium text-foreground">Governance</h4>
            <ul className="space-y-3">
              {footerLinks.governance.map((link) => (
                <li key={link.label}>
                  <Link
                    href={link.href}
                    className="text-sm text-muted-foreground transition-colors hover:text-foreground"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      {/* Bottom Bar */}
      <div className="border-t border-border px-6 py-6 md:px-12 lg:px-20">
        <div className="flex flex-col items-center justify-between gap-4 md:flex-row">
          <p className="text-xs text-muted-foreground">
            2026 DACAP Protocol. All rights reserved.
          </p>

          {/* Social Links */}
          <div className="flex items-center gap-4">
            <Link
              href="#"
              className="text-xs text-muted-foreground transition-colors hover:text-foreground"
            >
              Twitter
            </Link>
            <Link
              href="#"
              className="text-xs text-muted-foreground transition-colors hover:text-foreground"
            >
              Discord
            </Link>
            <Link
              href="#"
              className="text-xs text-muted-foreground transition-colors hover:text-foreground"
            >
              GitHub
            </Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
