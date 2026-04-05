"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Menu, X } from "lucide-react";

export function Header() {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isScrolled, setIsScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 50);
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <header 
      className={`fixed top-4 left-1/2 -translate-x-1/2 z-50 w-[90%] max-w-3xl transition-all duration-300 ${isScrolled ? "glass rounded-full" : "bg-transparent"}`}
    >
      <div className="flex items-center justify-between transition-all duration-300 px-2 pl-5 py-2">
        {/* Logo */}
        <Link href="#" className="flex items-center gap-2">
          <span className={`text-lg font-semibold tracking-tight transition-colors duration-300 ${isScrolled ? "text-foreground" : "text-white"}`}>
            DACAP
          </span>
          <span className={`text-[10px] font-mono uppercase tracking-widest transition-colors duration-300 hidden sm:inline ${isScrolled ? "text-primary" : "text-primary"}`}>
            Protocol
          </span>
        </Link>

        {/* Desktop Navigation */}
        <nav className="hidden items-center gap-8 md:flex">
          <Link
            href="#protocol"
            className={`text-sm transition-colors ${isScrolled ? "text-muted-foreground hover:text-foreground" : "text-white/70 hover:text-white"}`}
          >
            Protocol
          </Link>
          <Link
            href="#architecture"
            className={`text-sm transition-colors ${isScrolled ? "text-muted-foreground hover:text-foreground" : "text-white/70 hover:text-white"}`}
          >
            Architecture
          </Link>
          <Link
            href="#intelligence"
            className={`text-sm transition-colors ${isScrolled ? "text-muted-foreground hover:text-foreground" : "text-white/70 hover:text-white"}`}
          >
            Intelligence
          </Link>
          <Link
            href="#modules"
            className={`text-sm transition-colors ${isScrolled ? "text-muted-foreground hover:text-foreground" : "text-white/70 hover:text-white"}`}
          >
            Modules
          </Link>
        </nav>

        {/* CTA */}
        <div className="hidden items-center gap-6 md:flex">
          <Link
            href="#enter"
            className="px-4 py-2 text-sm font-medium transition-all rounded-full bg-primary text-primary-foreground hover:opacity-90"
          >
            Enter Command Center
          </Link>
        </div>

        {/* Mobile Menu Button */}
        <button
          type="button"
          onClick={() => setIsMenuOpen(!isMenuOpen)}
          className={`transition-colors md:hidden ${isScrolled ? "text-foreground" : "text-white"}`}
          aria-label="Toggle menu"
        >
          {isMenuOpen ? <X size={24} /> : <Menu size={24} />}
        </button>
      </div>

      {/* Mobile Menu */}
      {isMenuOpen && (
        <div className="border-t border-border glass px-6 py-8 md:hidden rounded-b-2xl">
          <nav className="flex flex-col gap-6">
            <Link
              href="#protocol"
              className="text-lg text-foreground"
              onClick={() => setIsMenuOpen(false)}
            >
              Protocol
            </Link>
            <Link
              href="#architecture"
              className="text-lg text-foreground"
              onClick={() => setIsMenuOpen(false)}
            >
              Architecture
            </Link>
            <Link
              href="#intelligence"
              className="text-lg text-foreground"
              onClick={() => setIsMenuOpen(false)}
            >
              Intelligence
            </Link>
            <Link
              href="#modules"
              className="text-lg text-foreground"
              onClick={() => setIsMenuOpen(false)}
            >
              Modules
            </Link>
            <Link
              href="#enter"
              className="mt-4 bg-primary px-5 py-3 text-center text-sm font-medium text-primary-foreground rounded-full"
              onClick={() => setIsMenuOpen(false)}
            >
              Enter Command Center
            </Link>
          </nav>
        </div>
      )}
    </header>
  );
}
