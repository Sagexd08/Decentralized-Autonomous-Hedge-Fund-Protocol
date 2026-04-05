"use client"

import { use, useState } from "react"
import Link from "next/link"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Progress } from "@/components/ui/progress"
import { MetricCard } from "@/components/iris/metric-card"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import {
  ArrowLeft,
  TrendingUp,
  TrendingDown,
  Activity,
  Shield,
  Zap,
  AlertTriangle,
  Play,
  Pause,
  DollarSign,
  Target,
  Loader2,
  CheckCircle2,
} from "lucide-react"
import { useAgent } from "@/hooks/use-agents"
import { useTradingFeed } from "@/hooks/use-trading-feed"
import { agentsApi } from "@/lib/api"
import { CandleChart } from "@/components/iris/candle-chart"
import { usePrivy, useWallets } from "@privy-io/react-auth"
import { useFreighter } from "@/hooks/use-freighter"
import { useAlgorand } from "@/hooks/use-algorand"

type Chain = "stellar" | "solana" | "algorand"

const CHAIN_LABELS: Record<Chain, string> = {
  stellar: "Stellar / Soroban",
  solana: "Solana",
  algorand: "Algorand",
}

const CHAIN_COLORS: Record<Chain, string> = {
  stellar: "border-amber-500/60 bg-amber-500/10 text-amber-400",
  solana: "border-violet-500/60 bg-violet-500/10 text-violet-400",
  algorand: "border-blue-500/60 bg-blue-500/10 text-blue-400",
}

const riskColors: Record<string, string> = {
  Conservative: "bg-chart-3/20 text-chart-3 border-chart-3/30",
  Balanced: "bg-primary/20 text-primary border-primary/30",
  Aggressive: "bg-destructive/20 text-destructive border-destructive/30",
}

/** Submit a Stellar payment to CAPITAL_VAULT_ADDRESS (XLM micro-payment as proof of intent) */
async function submitStellarStake(amount: number, memo: string): Promise<string> {
  const { requestTransaction, getAddress } = await import("@stellar/freighter-api")
  const addrResult = await getAddress()
  if (addrResult.error) throw new Error(addrResult.error)

  const CAPITAL_VAULT = process.env.NEXT_PUBLIC_STELLAR_CAPITAL_VAULT
    ?? "CB263OPPTMRE7R37CMIPSYWLDVVAR4UYWXQS7C6FY3AS6VBUEPHYX3H6"

  // Build XDR on a small backend helper (or build here with minimal stellar-base)
  // We call our own API to build + submit; Freighter just signs
  const res = await fetch("/api/stake/stellar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ from: addrResult.address, to: CAPITAL_VAULT, amount, memo }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err?.detail ?? "Stellar stake API failed")
  }
  const { xdr } = await res.json()

  const signedResult = await requestTransaction({ xdr, network: "TESTNET" })
  if (signedResult.error) throw new Error(signedResult.error)

  // Submit signed XDR
  const submitRes = await fetch("/api/stake/stellar/submit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ xdr: signedResult.signedTxXdr }),
  })
  if (!submitRes.ok) throw new Error("Transaction submission failed")
  const { txid } = await submitRes.json()
  return txid
}

/** Submit an Algorand payment to the Capital Vault app (Pera signs) */
async function submitAlgorandStake(
  address: string,
  amount: number,
  agentId: string,
  peraConnect: () => Promise<void>
): Promise<string> {
  const { PeraWalletConnect } = await import("@perawallet/connect")
  const pera = new PeraWalletConnect()
  // reconnect if session exists
  try { await pera.reconnectSession() } catch {}

  const APP_ID = parseInt(process.env.NEXT_PUBLIC_ALGORAND_CAPITAL_VAULT_APP_ID ?? "758312952")
  const microAlgos = Math.round(amount * 1_000_000)

  // Build unsigned txn via our backend
  const res = await fetch("/api/agents/stake/algorand/build", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ from_address: address, app_id: APP_ID, amount: microAlgos, agent_id: agentId }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err?.detail ?? "Algorand stake API failed")
  }
  const { txn_b64 } = await res.json()

  // Pera signs the base64 encoded unsigned txn
  const signedTxns = await pera.signTransaction([[{ txn: txn_b64 }]])

  // Submit
  const submitRes = await fetch("/api/agents/stake/algorand/submit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ signed_txn: Buffer.from(signedTxns[0]).toString("base64") }),
  })
  if (!submitRes.ok) throw new Error("Algorand transaction submission failed")
  const { txid } = await submitRes.json()
  return txid
}

export default function AgentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const { agent, loading, refetch } = useAgent(id)
  const { events } = useTradingFeed()
  const [actionLoading, setActionLoading] = useState(false)

  // Stake dialog state
  const [stakeOpen, setStakeOpen] = useState(false)
  const [stakeChain, setStakeChain] = useState<Chain>("stellar")
  const [stakeAmount, setStakeAmount] = useState("")
  const [stakeLoading, setStakeLoading] = useState(false)
  const [stakeError, setStakeError] = useState<string | null>(null)
  const [stakeTxId, setStakeTxId] = useState<string | null>(null)

  // Wallets
  const { authenticated, login } = usePrivy()
  const { wallets } = useWallets()
  const freighter = useFreighter()
  const algorand = useAlgorand()

  const evmAddress = wallets[0]?.address ?? null
  const isAnyConnected = authenticated || freighter.connected || algorand.connected

  // Derive the address for the selected chain
  const selectedAddress = (): string => {
    if (stakeChain === "stellar") return freighter.address ?? ""
    if (stakeChain === "solana") return evmAddress ?? ""
    if (stakeChain === "algorand") return algorand.address ?? ""
    return ""
  }

  // Filter trade events for this agent
  const agentTrades = events
    .filter((e) => agent?.address && e.agent.toLowerCase() === agent.address.toLowerCase())
    .slice(0, 10)

  const handleToggleTrading = async () => {
    if (!agent) return
    setActionLoading(true)
    try {
      if (agent.status === "active") {
        await agentsApi.stopTrading(agent.id)
      } else {
        await agentsApi.startTrading(agent.id)
      }
      refetch()
    } catch (e) {
      console.error("Trading toggle failed", e)
    } finally {
      setActionLoading(false)
    }
  }

  const handleStake = async () => {
    if (!agent || !stakeAmount) return
    const addr = selectedAddress()
    if (!addr) {
      setStakeError("No wallet connected for the selected chain.")
      return
    }

    setStakeLoading(true)
    setStakeError(null)
    setStakeTxId(null)

    try {
      let txid: string | null = null

      if (stakeChain === "stellar") {
        txid = await submitStellarStake(parseFloat(stakeAmount), agent.id)
      } else if (stakeChain === "algorand") {
        txid = await submitAlgorandStake(addr, parseFloat(stakeAmount), agent.id, algorand.connect)
      }
      // Solana: record off-chain for now (Privy embedded wallet doesn't expose raw signing)

      // Record stake in our backend
      await agentsApi.stake({
        agent_id: agent.id,
        amount: parseFloat(stakeAmount),
        address: addr,
        chain: stakeChain,
        txid: txid ?? undefined,
      })

      // Kick off the trading engine
      await agentsApi.startTrading(agent.id)

      setStakeTxId(txid ?? "off-chain")
      refetch()
    } catch (e: unknown) {
      setStakeError(e instanceof Error ? e.message : "Stake failed")
    } finally {
      setStakeLoading(false)
    }
  }

  const openStakeDialog = () => {
    if (!isAnyConnected) {
      login()
      return
    }
    // Pre-select chain based on which wallet is connected
    if (freighter.connected) setStakeChain("stellar")
    else if (algorand.connected) setStakeChain("algorand")
    else setStakeChain("solana")
    setStakeAmount("")
    setStakeError(null)
    setStakeTxId(null)
    setStakeOpen(true)
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-10 h-10 animate-spin text-primary" />
      </div>
    )
  }

  if (!agent) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4">
        <p className="text-muted-foreground">Agent not found.</p>
        <Button asChild variant="outline">
          <Link href="/agents">Back to Agents</Link>
        </Button>
      </div>
    )
  }

  const isActive = agent.status === "active"
  const riskColor = riskColors[agent.risk] ?? riskColors["Balanced"]

  return (
    <div className="min-h-screen bg-transparent">
      {/* ── Stake Dialog ───────────────────────────────────────────────────── */}
      <Dialog open={stakeOpen} onOpenChange={(v) => { if (!stakeLoading) setStakeOpen(v) }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Delegate Capital to {agent?.name}</DialogTitle>
          </DialogHeader>

          {stakeTxId ? (
            // ── Success state ──
            <div className="py-6 flex flex-col items-center gap-4 text-center">
              <CheckCircle2 className="w-12 h-12 text-green-400" />
              <p className="font-semibold text-foreground">Stake submitted successfully!</p>
              {stakeTxId !== "off-chain" && (
                <p className="text-xs font-mono text-muted-foreground break-all">{stakeTxId}</p>
              )}
              <Button className="glow-cyan w-full" onClick={() => setStakeOpen(false)}>Done</Button>
            </div>
          ) : (
            <div className="space-y-5 py-2">
              {/* Chain selector */}
              <div>
                <label className="text-sm text-muted-foreground mb-2 block">Select Chain</label>
                <div className="grid grid-cols-3 gap-2">
                  {(["stellar", "solana", "algorand"] as Chain[]).map((chain) => {
                    const addr =
                      chain === "stellar" ? freighter.address
                      : chain === "solana" ? evmAddress
                      : algorand.address
                    const isConnectedForChain = !!addr
                    return (
                      <button
                        key={chain}
                        onClick={() => setStakeChain(chain)}
                        className={`rounded-lg px-2 py-2.5 border text-xs font-mono transition-all text-center ${
                          stakeChain === chain
                            ? CHAIN_COLORS[chain]
                            : "border-border/40 text-muted-foreground hover:border-border/80"
                        } ${!isConnectedForChain ? "opacity-50" : ""}`}
                      >
                        <div className="font-semibold mb-0.5">{CHAIN_LABELS[chain].split(" / ")[0]}</div>
                        {isConnectedForChain ? (
                          <div className="text-[9px] text-muted-foreground truncate">
                            {addr!.slice(0, 6)}…
                          </div>
                        ) : (
                          <div className="text-[9px] text-muted-foreground">not connected</div>
                        )}
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* Wallet address (read-only) */}
              <div>
                <label className="text-sm text-muted-foreground mb-1 block">
                  Wallet Address
                  <span className="ml-1 text-[10px] font-mono opacity-60">
                    ({CHAIN_LABELS[stakeChain]})
                  </span>
                </label>
                <Input
                  readOnly
                  value={selectedAddress()}
                  placeholder="Connect wallet above"
                  className="font-mono text-xs text-muted-foreground bg-muted/20"
                />
              </div>

              {/* Amount */}
              <div>
                <label className="text-sm text-muted-foreground mb-1 block">Amount (USD equivalent)</label>
                <Input
                  type="number"
                  min="1"
                  placeholder="e.g. 1000"
                  value={stakeAmount}
                  onChange={(e) => setStakeAmount(e.target.value)}
                />
              </div>

              {stakeError && (
                <p className="text-sm text-destructive flex items-center gap-1.5">
                  <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                  {stakeError}
                </p>
              )}

              {stakeChain === "stellar" && !freighter.connected && (
                <p className="text-xs text-amber-400">
                  Install Freighter browser extension and connect it above to stake via Stellar.
                </p>
              )}
              {stakeChain === "algorand" && !algorand.connected && (
                <p className="text-xs text-blue-400">
                  Connect Pera Wallet above to stake via Algorand.
                </p>
              )}

              <DialogFooter>
                <Button variant="outline" onClick={() => setStakeOpen(false)}>Cancel</Button>
                <Button
                  className="glow-cyan"
                  disabled={stakeLoading || !stakeAmount || !selectedAddress()}
                  onClick={handleStake}
                >
                  {stakeLoading ? (
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  ) : (
                    <DollarSign className="w-4 h-4 mr-2" />
                  )}
                  {stakeLoading ? "Signing…" : "Stake & Start Agent"}
                </Button>
              </DialogFooter>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Header */}
      <div className="border-b border-border/30 bg-muted/10">
        <div className="max-w-[1800px] mx-auto px-4 md:px-6 py-8">
          <Link
            href="/agents"
            className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground mb-4"
          >
            <ArrowLeft className="w-4 h-4 mr-1" />
            Back to Agents
          </Link>

          <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-6">
            <div className="flex items-start gap-4">
              <div className="w-16 h-16 rounded-xl bg-primary/10 flex items-center justify-center">
                <Zap className="w-8 h-8 text-primary" />
              </div>
              <div>
                <div className="flex items-center gap-3 mb-2">
                  <h1 className="text-2xl md:text-3xl font-bold text-foreground">{agent.name}</h1>
                  {isActive && (
                    <span className="w-3 h-3 rounded-full bg-accent animate-pulse" />
                  )}
                </div>
                <p className="text-muted-foreground mb-3">{agent.strategy}</p>
                <div className="flex flex-wrap gap-2">
                  <Badge variant="outline" className={riskColor}>
                    {agent.risk}
                  </Badge>
                  <Badge variant="outline" className="text-muted-foreground">
                    Score: {agent.score}
                  </Badge>
                </div>
              </div>
            </div>

            <div className="flex gap-3">
              <Button variant="outline" onClick={openStakeDialog}>
                <DollarSign className="w-4 h-4 mr-2" />
                Delegate Capital
              </Button>
              <Button
                disabled={actionLoading}
                className={isActive ? "bg-destructive hover:bg-destructive/90" : "glow-cyan"}
                onClick={handleToggleTrading}
              >
                {actionLoading ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : isActive ? (
                  <Pause className="w-4 h-4 mr-2" />
                ) : (
                  <Play className="w-4 h-4 mr-2" />
                )}
                {isActive ? "Stop AI" : "Start AI"}
              </Button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-[1800px] mx-auto px-4 md:px-6 py-8">
        {/* Description */}
        <div className="glass rounded-xl p-6 border border-border/30 mb-8">
          <h3 className="font-semibold text-foreground mb-3">Strategy Description</h3>
          <p className="text-muted-foreground text-sm leading-relaxed">{agent.description}</p>
          {agent.model && (
            <div className="mt-4 pt-4 border-t border-border/30 flex items-center gap-4">
              <div>
                <span className="text-xs text-muted-foreground">Model Family</span>
                <p className="font-mono text-sm text-foreground">{agent.model}</p>
              </div>
            </div>
          )}
        </div>

        {/* Score Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <MetricCard
            title="Trust Score"
            value={`${agent.trust_score ?? agent.score}/100`}
            icon={<Shield className="w-4 h-4" />}
            variant="cyan"
          />
          <MetricCard
            title="Confidence"
            value={`${Math.round((agent.confidence_score ?? 0.5) * 100)}/100`}
            icon={<Target className="w-4 h-4" />}
            variant="emerald"
          />
          <MetricCard
            title="Anomaly Score"
            value={`${Math.round((agent.anomaly_score ?? 0.1) * 100)}/100`}
            icon={<AlertTriangle className="w-4 h-4" />}
            variant={(agent.anomaly_score ?? 0) > 0.5 ? "amber" : "default"}
          />
          <MetricCard
            title="Overall Score"
            value={`${agent.score}/100`}
            icon={<Activity className="w-4 h-4" />}
            variant="blue"
          />
        </div>

        <div className="grid lg:grid-cols-3 gap-6 mb-8">
          {/* Performance Metrics */}
          <div className="glass rounded-xl p-6 border border-border/30">
            <h3 className="font-semibold text-foreground mb-6">Performance Metrics</h3>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Sharpe Ratio</span>
                <span className="font-mono font-semibold text-foreground">
                  {agent.sharpe.toFixed(2)}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Volatility</span>
                <span className="font-mono font-semibold text-foreground">
                  {agent.volatility.toFixed(2)}%
                </span>
              </div>
              <div className="pt-4 border-t border-border/30">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Total PnL</span>
                  <span
                    className={`font-mono font-semibold flex items-center gap-1 ${
                      agent.pnl >= 0 ? "text-accent" : "text-destructive"
                    }`}
                  >
                    {agent.pnl >= 0 ? (
                      <TrendingUp className="w-4 h-4" />
                    ) : (
                      <TrendingDown className="w-4 h-4" />
                    )}
                    ${agent.pnl.toLocaleString()}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Risk Metrics */}
          <div className="glass rounded-xl p-6 border border-border/30">
            <h3 className="font-semibold text-foreground mb-6">Risk Metrics</h3>
            <div className="space-y-4">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-muted-foreground">Drawdown</span>
                  <span className="font-mono font-semibold text-destructive">
                    -{Math.abs(agent.drawdown).toFixed(2)}%
                  </span>
                </div>
                <Progress value={Math.abs(agent.drawdown) * 5} className="h-2" />
              </div>
              <div className="pt-4 border-t border-border/30">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Capital Allocated</span>
                  <span className="font-mono font-semibold text-foreground">
                    {agent.allocation.toFixed(1)}%
                  </span>
                </div>
                <div className="flex items-center justify-between mt-2">
                  <span className="text-muted-foreground">Stake</span>
                  <span className="font-mono font-semibold text-foreground">
                    ${agent.stake.toLocaleString()}
                  </span>
                </div>
              </div>
            </div>

            {Math.abs(agent.drawdown) > 7 && (
              <div className="mt-4 p-3 rounded-lg bg-destructive/10 border border-destructive/30">
                <div className="flex items-center gap-2 text-destructive text-sm">
                  <AlertTriangle className="w-4 h-4" />
                  Slashing Watch — Approaching drawdown limit
                </div>
              </div>
            )}
          </div>

          {/* Live Trade Feed */}
          <div className="glass rounded-xl p-6 border border-border/30">
            <h3 className="font-semibold text-foreground mb-6">Live Trade Feed</h3>
            {agentTrades.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                {isActive ? "Waiting for trades…" : "Start the agent to see live trades."}
              </p>
            ) : (
              <div className="space-y-2">
                {agentTrades.map((trade, i) => (
                  <div key={i} className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <Badge
                        variant="outline"
                        className={
                          trade.type === "swap"
                            ? "text-accent border-accent/30"
                            : "text-destructive border-destructive/30"
                        }
                      >
                        {trade.type.toUpperCase()}
                      </Badge>
                      <span className="text-foreground">{trade.token}</span>
                    </div>
                    <span className="text-xs text-muted-foreground">
                      {new Date(trade.timestamp * 1000).toLocaleTimeString()}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* ── Candle Chart ─────────────────────────────────────────────── */}
        <div className="glass rounded-xl border border-border/30 overflow-hidden mb-8">
          <div className="px-6 pt-5 pb-2 border-b border-border/30 flex items-center justify-between">
            <h3 className="font-semibold text-foreground">Price Chart</h3>
            <span className="text-xs text-muted-foreground font-mono">
              30s candles · live
            </span>
          </div>
          <CandleChart
            tradeEvents={agentTrades}
            defaultSymbol={
              agent.strategy.toLowerCase().includes("sol") ? "SOL"
              : agent.strategy.toLowerCase().includes("arb") ? "ETH"
              : agent.strategy.toLowerCase().includes("link") ? "LINK"
              : "WBTC"
            }
            height={300}
            showSymbolTabs
          />
        </div>

        {/* Trading Status */}
        <div className="glass rounded-xl p-6 border border-border/30">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-foreground">Trading Session Status</h3>
            <Badge
              variant="outline"
              className={isActive ? "text-accent border-accent/30" : "text-muted-foreground"}
            >
              {isActive ? "Active" : "Inactive"}
            </Badge>
          </div>
          <div className="grid md:grid-cols-3 gap-4">
            <div>
              <span className="text-xs text-muted-foreground">Wallet Address</span>
              <p className="font-mono text-xs text-foreground truncate">{agent.address ?? "—"}</p>
            </div>
            <div>
              <span className="text-xs text-muted-foreground">Agent ID</span>
              <p className="font-mono text-foreground">{agent.id}</p>
            </div>
            <div>
              <span className="text-xs text-muted-foreground">Status</span>
              <p className="font-mono text-foreground capitalize">{agent.status}</p>
            </div>
          </div>

          {/* Connected wallets summary */}
          <div className="mt-4 pt-4 border-t border-border/30 flex flex-wrap gap-3">
            {freighter.connected && freighter.address && (
              <span className="text-[11px] font-mono px-2 py-1 rounded border border-amber-500/30 bg-amber-500/5 text-amber-400">
                Stellar {freighter.address.slice(0, 6)}…
              </span>
            )}
            {authenticated && evmAddress && (
              <span className="text-[11px] font-mono px-2 py-1 rounded border border-violet-500/30 bg-violet-500/5 text-violet-400">
                EVM {evmAddress.slice(0, 6)}…
              </span>
            )}
            {algorand.connected && algorand.address && (
              <span className="text-[11px] font-mono px-2 py-1 rounded border border-blue-500/30 bg-blue-500/5 text-blue-400">
                Algorand {algorand.address.slice(0, 6)}…
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
