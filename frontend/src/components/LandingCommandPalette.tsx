import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Search, X } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

const COMMANDS = [
  { key: 'dashboard',    label: 'Open Dashboard',         shortcut: '⌘D', path: '/dashboard' },
  { key: 'agents',       label: 'View AI Agents',          shortcut: '⌘A', path: '/agents' },
  { key: 'intelligence', label: 'Intelligence Hub',        shortcut: '⌘I', path: '/intelligence' },
  { key: 'governance',   label: 'Governance',              shortcut: '⌘G', path: '/governance' },
  { key: 'pools',        label: 'Risk Pools',              shortcut: '⌘R', path: '/pools' },
]

export default function LandingCommandPalette({
  open,
  onClose,
}: {
  open: boolean
  onClose: () => void
}) {
  const [query, setQuery] = useState('')
  const navigate = useNavigate()

  const filtered = COMMANDS.filter((c) =>
    c.label.toLowerCase().includes(query.toLowerCase()),
  )

  useEffect(() => {
    if (!open) { setQuery(''); return }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  const go = (path: string) => { onClose(); navigate(path) }

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-[100] bg-black/70 backdrop-blur-sm"
            onClick={onClose}
          />
          <motion.div
            key="palette"
            initial={{ opacity: 0, scale: 0.97, y: -12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.97, y: -12 }}
            transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
            className="fixed left-1/2 top-1/3 z-[101] w-full max-w-xl -translate-x-1/2 -translate-y-1/2 overflow-hidden rounded-none border border-white/10 bg-[#0a0a0a] shadow-[0_40px_120px_rgba(0,0,0,0.8)]"
          >
            {}
            <div className="flex items-center gap-3 border-b border-white/8 px-5 py-4">
              <Search size={16} className="shrink-0 text-white/30" />
              <input
                autoFocus
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search commands…"
                className="flex-1 bg-transparent font-['Space_Grotesk',sans-serif] text-sm text-white placeholder:text-white/30 focus:outline-none"
              />
              <button
                onClick={onClose}
                className="flex h-6 w-6 items-center justify-center text-white/30 hover:text-white/60"
              >
                <X size={14} />
              </button>
            </div>

            {}
            <div className="py-2">
              {filtered.length === 0 && (
                <p className="px-5 py-4 text-xs text-white/30">No commands found.</p>
              )}
              {filtered.map((cmd) => (
                <button
                  key={cmd.key}
                  onClick={() => go(cmd.path)}
                  className="flex w-full items-center justify-between px-5 py-3 text-left text-sm text-white/70 transition hover:bg-white/5 hover:text-white"
                >
                  <span className="font-['Space_Grotesk',sans-serif] tracking-wide">
                    {cmd.label}
                  </span>
                  <span className="font-['Space_Grotesk',sans-serif] text-xs text-white/25">
                    {cmd.shortcut}
                  </span>
                </button>
              ))}
            </div>

            <div className="border-t border-white/8 px-5 py-3 text-[10px] tracking-widest text-white/20">
              ESC TO CLOSE · ENTER TO SELECT
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
