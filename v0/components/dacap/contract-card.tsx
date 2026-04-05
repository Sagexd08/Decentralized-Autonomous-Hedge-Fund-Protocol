"use client"

import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Shield, ExternalLink, Copy, CheckCircle2, LucideIcon } from "lucide-react"
import { useState } from "react"

export interface ContractData {
  name: string
  address: string
  description: string
  version: string
  audited: boolean
  auditor: string | null
  tvl: string
  category: string
  icon: LucideIcon
  functions: string[]
  lastUpgrade: string
  chain: string
}

interface ContractCardProps {
  contract: ContractData
  className?: string
}

export function ContractCard({ contract, className }: ContractCardProps) {
  const [copied, setCopied] = useState(false)

  const copyAddress = () => {
    navigator.clipboard.writeText(contract.address)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const Icon = contract.icon

  return (
    <div
      className={cn(
        "glass rounded-xl p-5 border border-border/30 hover:border-primary/30 transition-colors",
        className
      )}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
            <Icon className="w-5 h-5 text-primary" />
          </div>
          <div>
            <h3 className="font-semibold text-foreground">{contract.name}</h3>
            <p className="text-xs text-muted-foreground">v{contract.version}</p>
          </div>
        </div>
        <Badge 
          variant="outline" 
          className={cn(
            "text-xs",
            contract.audited 
              ? "text-accent bg-accent/10 border-accent/30" 
              : "text-destructive bg-destructive/10 border-destructive/30"
          )}
        >
          {contract.audited && <CheckCircle2 className="w-3 h-3 mr-1" />}
          {contract.audited ? "Audited" : "Pending Audit"}
        </Badge>
      </div>

      {/* Description */}
      <p className="text-sm text-muted-foreground mb-4 line-clamp-2">{contract.description}</p>

      {/* Address */}
      <div className="mb-4 p-3 rounded-lg bg-muted/30 border border-border/30">
        <div className="text-xs text-muted-foreground mb-1">Contract Address</div>
        <div className="flex items-center gap-2">
          <code className="font-mono text-xs text-foreground truncate flex-1">
            {contract.address}
          </code>
          <button
            onClick={copyAddress}
            className="text-muted-foreground hover:text-foreground transition-colors"
          >
            {copied ? (
              <CheckCircle2 className="w-4 h-4 text-accent" />
            ) : (
              <Copy className="w-4 h-4" />
            )}
          </button>
          <a
            href={`https://etherscan.io/address/${contract.address}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-muted-foreground hover:text-foreground transition-colors"
          >
            <ExternalLink className="w-4 h-4" />
          </a>
        </div>
      </div>

      {/* Info Grid */}
      <div className="grid grid-cols-2 gap-4 mb-4 text-sm">
        <div>
          <div className="text-xs text-muted-foreground mb-1">TVL</div>
          <div className="font-mono text-foreground">{contract.tvl}</div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground mb-1">Chain</div>
          <div className="text-foreground">{contract.chain}</div>
        </div>
        {contract.auditor && (
          <div className="col-span-2">
            <div className="text-xs text-muted-foreground mb-1">Audited By</div>
            <div className="text-foreground">{contract.auditor}</div>
          </div>
        )}
      </div>

      {/* Functions */}
      <div className="pt-4 border-t border-border/30">
        <div className="text-xs text-muted-foreground mb-2">Key Functions</div>
        <div className="flex flex-wrap gap-1">
          {contract.functions.slice(0, 3).map((fn) => (
            <Badge key={fn} variant="secondary" className="text-[10px] font-mono">
              {fn}
            </Badge>
          ))}
          {contract.functions.length > 3 && (
            <Badge variant="secondary" className="text-[10px]">
              +{contract.functions.length - 3}
            </Badge>
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="mt-4 pt-4 border-t border-border/30 flex items-center justify-between text-xs text-muted-foreground">
        <span>Last upgrade: {contract.lastUpgrade}</span>
      </div>
    </div>
  )
}
