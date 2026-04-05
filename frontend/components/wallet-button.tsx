"use client"

import { usePrivy, useWallets } from "@privy-io/react-auth"
import { Wallet, LogOut, ChevronDown, Copy, Check } from "lucide-react"
import { useState } from "react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Button } from "@/components/ui/button"

function shortAddr(addr: string) {
  return `${addr.slice(0, 6)}…${addr.slice(-4)}`
}

export function WalletButton() {
  const { ready, authenticated, login, logout } = usePrivy()
  const { wallets } = useWallets()
  const [copied, setCopied] = useState(false)

  const wallet = wallets[0]
  const address = wallet?.address ?? null

  const copyAddress = async () => {
    if (!address) return
    await navigator.clipboard.writeText(address)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  if (!ready) {
    return (
      <Button variant="outline" size="sm" disabled className="font-mono text-xs border-amber-500/20 text-amber-500/40">
        <Wallet className="w-3.5 h-3.5 mr-1.5" />
        Loading…
      </Button>
    )
  }

  if (!authenticated || !address) {
    return (
      <Button
        variant="outline"
        size="sm"
        onClick={login}
        className="font-mono text-xs border-amber-500/40 text-amber-400 hover:bg-amber-500/10 hover:border-amber-500/70 hover:text-amber-300 transition-all"
      >
        <Wallet className="w-3.5 h-3.5 mr-1.5" />
        Connect Wallet
      </Button>
    )
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="font-mono text-xs border-amber-500/50 bg-amber-500/10 text-amber-400 hover:bg-amber-500/15 hover:border-amber-500/80 transition-all gap-1.5"
        >
          <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
          {shortAddr(address)}
          <ChevronDown className="w-3 h-3 opacity-60" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="end"
        className="border-border/60 bg-card/95 backdrop-blur-xl font-mono text-xs min-w-[200px]"
      >
        <div className="px-3 py-2 text-[10px] text-muted-foreground tracking-widest uppercase">
          Connected Wallet
        </div>
        <div className="px-3 pb-2 text-amber-400 text-[11px] break-all">
          {address}
        </div>
        <DropdownMenuSeparator className="bg-border/40" />
        <DropdownMenuItem
          onClick={copyAddress}
          className="gap-2 cursor-pointer text-muted-foreground hover:text-foreground"
        >
          {copied ? <Check className="w-3.5 h-3.5 text-green-400" /> : <Copy className="w-3.5 h-3.5" />}
          {copied ? "Copied!" : "Copy address"}
        </DropdownMenuItem>
        <DropdownMenuItem
          onClick={logout}
          className="gap-2 cursor-pointer text-destructive hover:text-destructive focus:text-destructive"
        >
          <LogOut className="w-3.5 h-3.5" />
          Disconnect
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
