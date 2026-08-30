"use client"

import { usePrivy, useWallets } from "@privy-io/react-auth"
import { PRIVY_ENABLED } from "@/components/privy-provider"
import { Wallet, LogOut, ChevronDown, Copy, Check } from "lucide-react"
import { useState } from "react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Button } from "@/components/ui/button"

function shortAddr(addr: string, len = 4) {
  return `${addr.slice(0, len)}…${addr.slice(-len)}`
}

// ─── EVM wallet button (Privy) ────────────────────────────────────────────────
function EvmWalletSection() {
  const { authenticated, login, logout } = usePrivy()
  const { wallets } = useWallets()
  const [copied, setCopied] = useState(false)
  const address = wallets[0]?.address ?? null

  const copyAddress = async () => {
    if (!address) return
    await navigator.clipboard.writeText(address)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  if (!authenticated || !address) {
    return (
      <DropdownMenuItem onClick={login} className="gap-2 cursor-pointer">
        <Wallet className="w-3.5 h-3.5 text-violet-400" />
        <span>Connect EVM Wallet</span>
        <span className="ml-auto text-[10px] text-muted-foreground font-mono">ETH · SOL</span>
      </DropdownMenuItem>
    )
  }

  return (
    <>
      <div className="px-3 py-1.5 flex items-center gap-2">
        <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse" />
        <span className="text-[10px] font-mono text-violet-400 tracking-wider">EVM</span>
        <span className="font-mono text-[11px] text-foreground ml-1">{shortAddr(address)}</span>
      </div>
      <DropdownMenuItem onClick={copyAddress} className="gap-2 cursor-pointer text-muted-foreground hover:text-foreground pl-6 text-xs">
        {copied ? <Check className="w-3 h-3 text-green-400" /> : <Copy className="w-3 h-3" />}
        {copied ? "Copied!" : "Copy address"}
      </DropdownMenuItem>
      <DropdownMenuItem onClick={logout} className="gap-2 cursor-pointer text-destructive hover:text-destructive pl-6 text-xs">
        <LogOut className="w-3 h-3" />
        Disconnect EVM
      </DropdownMenuItem>
    </>
  )
}

// ─── Main wallet button ───────────────────────────────────────────────────────
export function WalletButton() {
  if (!PRIVY_ENABLED) {
    return <WalletUnavailableButton />
  }

  return <PrivyWalletButton />
}

/** Privy is the only wallet provider; without an app id there is nothing to connect to. */
function WalletUnavailableButton() {
  return (
    <Button
      variant="outline"
      size="sm"
      disabled
      title="Set NEXT_PUBLIC_PRIVY_APP_ID to enable wallet connection"
      className="font-mono text-xs border-border/60 text-muted-foreground"
    >
      <Wallet className="w-3.5 h-3.5 mr-1.5 opacity-40" />
      Wallet unavailable
    </Button>
  )
}

function PrivyWalletButton() {
  const { ready, authenticated } = usePrivy()
  const { wallets } = useWallets()

  const evmAddress = wallets[0]?.address ?? null
  const anyConnected = authenticated && !!evmAddress

  // Don't block rendering on `ready` — show connect button immediately
  // (ready just means Privy has finished checking for an existing session)
  const isConnecting = !ready && !anyConnected

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className={`font-mono text-xs transition-all gap-1.5 ${
            anyConnected
              ? "border-amber-500/50 bg-amber-500/10 text-amber-400 hover:bg-amber-500/15 hover:border-amber-500/80"
              : "border-border/60 text-muted-foreground hover:text-foreground hover:border-border"
          }`}
        >
          {anyConnected ? (
            <>
              <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
              {evmAddress ? shortAddr(evmAddress) : "Wallet"}
            </>
          ) : (
            <>
              <Wallet className={`w-3.5 h-3.5 ${isConnecting ? "opacity-40" : ""}`} />
              Connect Wallet
            </>
          )}
          <ChevronDown className="w-3 h-3 opacity-60" />
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent
        align="end"
        className="border-border/60 bg-card/95 backdrop-blur-xl min-w-[220px]"
      >
        <DropdownMenuLabel className="text-[10px] text-muted-foreground tracking-widest uppercase font-normal">
          EVM / Solana
        </DropdownMenuLabel>
        <EvmWalletSection />
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
