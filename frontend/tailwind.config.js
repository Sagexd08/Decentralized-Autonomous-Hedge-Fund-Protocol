/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/app/**/*.{js,ts,jsx,tsx,mdx}', './src/components/**/*.{js,ts,jsx,tsx,mdx}', './src/pages/**/*.{js,ts,jsx,tsx,mdx}', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#050810',
        surface: '#0d1117',
        card: '#111827',
        border: '#1f2937',
        cyan: { DEFAULT: '#00f5ff', dim: '#00c4cc' },
        purple: { DEFAULT: '#a855f7', dim: '#7c3aed' },
        blue: { DEFAULT: '#3b82f6', dim: '#1d4ed8' },
        green: { DEFAULT: '#10b981', dim: '#059669' },
        red: { DEFAULT: '#ef4444', dim: '#dc2626' },
        gold: { DEFAULT: '#f59e0b', dim: '#d97706' },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      backgroundImage: {
        'glow-cyan': 'radial-gradient(ellipse at center, rgba(0,245,255,0.15) 0%, transparent 70%)',
        'glow-purple': 'radial-gradient(ellipse at center, rgba(168,85,247,0.15) 0%, transparent 70%)',
        'grid': 'linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px)',
      },
      backgroundSize: {
        'grid': '40px 40px',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'float': 'float 6s ease-in-out infinite',
        'glow': 'glow 2s ease-in-out infinite alternate',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-10px)' },
        },
        glow: {
          from: { boxShadow: '0 0 10px rgba(0,245,255,0.3)' },
          to: { boxShadow: '0 0 30px rgba(0,245,255,0.7)' },
        }
      }
    },
  },
  plugins: [],
}
