import { NavLink } from 'react-router-dom'
import { LayoutDashboard, Bot, Layers, Cpu, Vote, BarChart3, FileCode2, Zap, Globe, MessageSquare, TrendingUp } from 'lucide-react'
import { motion } from 'framer-motion'

const nav = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Capital Brain' },
  { to: '/agents', icon: Bot, label: 'Agents' },
  { to: '/pools', icon: Layers, label: 'Risk Pools' },
  { to: '/allocation', icon: Cpu, label: 'Allocation Engine' },
  { to: '/intelligence', icon: Zap, label: 'Intelligence' },
  { to: '/analytics', icon: BarChart3, label: 'Analytics' },
  { to: '/pnl-history', icon: TrendingUp, label: 'PnL History' },
  { to: '/world', icon: Globe, label: 'World Monitor' },
  { to: '/social', icon: MessageSquare, label: 'Agent Social' },
  { to: '/governance', icon: Vote, label: 'Governance' },
  { to: '/contracts', icon: FileCode2, label: 'Contracts' },
]

export default function Sidebar() {
  return (
    <aside className="w-56 flex flex-col glass border-r border-border shrink-0">
      <div className="p-5 border-b border-border">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: 'linear-gradient(135deg,#00f5ff,#a855f7)' }}>
            <Zap size={14} className="text-bg" />
          </div>
          <span className="font-bold text-sm tracking-wider gradient-text">DACAP</span>
        </div>
        <p className="text-xs text-slate-500 mt-1 font-mono">v2.1.0 · autonomous finance</p>
      </div>

      <nav className="flex-1 p-3 space-y-0.5">
        {nav.map(({ to, icon: Icon, label }) => (
          <NavLink key={to} to={to} className={({ isActive }) =>
            `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-150 ${
              isActive
                ? 'bg-cyan/10 text-cyan border border-cyan/20'
                : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
            }`
          }>
            {({ isActive }) => (
              <>
                <Icon size={15} className={isActive ? 'text-cyan' : ''} />
                <span className="font-medium">{label}</span>
                {isActive && (
                  <motion.div layoutId="nav-indicator" className="ml-auto w-1.5 h-1.5 rounded-full bg-cyan" />
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="p-4 border-t border-border">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-green animate-pulse" />
          <span className="text-xs text-slate-400">Financial Organism Active</span>
        </div>
        <p className="text-xs text-slate-600 mt-1 font-mono">Block #21,847,293</p>
      </div>
    </aside>
  )
}
