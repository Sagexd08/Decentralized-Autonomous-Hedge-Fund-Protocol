import { Bell, Wallet, ChevronDown } from 'lucide-react'
import { useProtocolStore } from '../../store/protocolStore'

declare global {
  interface Window {
    ethereum?: {
      request: (args: { method: string; params?: unknown[] }) => Promise<unknown>
      on: (event: string, handler: (...args: unknown[]) => void) => void
      removeListener: (event: string, handler: (...args: unknown[]) => void) => void
    }
  }
}

export default function Topbar() {
  const { walletAddress, isConnected, connect, disconnect } = useProtocolStore()

  const handleWalletClick = async () => {
    if (isConnected) {
      disconnect()
      return
    }
    if (!window.ethereum) {
      alert('MetaMask not detected. Please install the MetaMask extension.')
      return
    }
    try {
      const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' }) as string[]
      if (accounts.length > 0) {
        connect(accounts[0])

        window.ethereum.on('accountsChanged', (accs: unknown) => {
          const updated = accs as string[]
          if (updated.length === 0) disconnect()
          else connect(updated[0])
        })
      }
    } catch (err) {
      console.error('Wallet connection rejected', err)
    }
  }

  const displayAddress = walletAddress
    ? `${walletAddress.slice(0, 6)}...${walletAddress.slice(-4)}`
    : 'Connect Wallet'

  return (
    <header className="h-14 glass border-b border-border flex items-center justify-between px-6 shrink-0">
      <div className="flex items-center gap-3">
        <div className="w-2 h-2 rounded-full bg-green animate-pulse" />
        <span className="text-xs font-mono text-slate-400">ETH: $3,847.22</span>
        <span className="text-slate-700">|</span>
        <span className="text-xs font-mono text-slate-400">Gas: 18 gwei</span>
        <span className="text-slate-700">|</span>
        <span className="text-xs font-mono text-cyan">TVL: $25.3M</span>
      </div>
      <div className="flex items-center gap-3">
        <button className="relative p-2 rounded-lg hover:bg-white/5 transition-colors">
          <Bell size={16} className="text-slate-400" />
          <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full bg-cyan" />
        </button>
        <button className="btn-primary flex items-center gap-2" onClick={handleWalletClick}>
          <Wallet size={14} />
          <span className="font-mono text-xs">{displayAddress}</span>
          {isConnected && <ChevronDown size={12} />}
        </button>
      </div>
    </header>
  )
}
