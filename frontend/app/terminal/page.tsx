"use client"

/**
 * IRIS Protocol TERMINAL
 * Design: "Quantitative Noir" — Bloomberg DNA elevated with amber data-glow.
 * Differentiation: information-dense monospaced panels separated by amber
 * hairlines, live candles + news in a fixed-chrome split layout that feels
 * like a professional trading workstation, not a dashboard.
 */

import { useState, useEffect, useRef } from "react"
import { CandleChart } from "@/components/iris/candle-chart"
import { NewsFeed } from "@/components/iris/news-feed"
import { useLivePrices } from "@/hooks/use-live-prices"
import { useTradingFeed } from "@/hooks/use-trading-feed"
import { useNews } from "@/hooks/use-news"
import { useAgents } from "@/hooks/use-agents"
import {
  Activity,
  TrendingUp,
  TrendingDown,
  Radio,
  Wifi,
  WifiOff,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
} from "lucide-react"
import Link from "next/link"

// ─── Price ticker strip ───────────────────────────────────────────────────────
const TICKER_SYMBOLS = ["WBTC", "ETH", "SOL", "LINK", "AAVE", "UNI"] as const

function PriceTicker() {
  const { prices, connected } = useLivePrices()
  const tickerRef = useRef<HTMLDivElement>(null)

  // Simple auto-scroll animation for the ticker
  useEffect(() => {
    const el = tickerRef.current
    if (!el) return
    let frame: number
    let x = 0
    const speed = 0.4

    const animate = () => {
      x -= speed
      if (x < -el.scrollWidth / 2) x = 0
      el.style.transform = `translateX(${x}px)`
      frame = requestAnimationFrame(animate)
    }
    frame = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(frame)
  }, [])

  const items = [...TICKER_SYMBOLS, ...TICKER_SYMBOLS] // duplicate for seamless loop

  return (
    <div
      style={{
        background: "#050505",
        borderBottom: "1px solid #f59e0b33",
        height: 32,
        overflow: "hidden",
        display: "flex",
        alignItems: "center",
        position: "relative",
      }}
    >
      {/* Connection badge */}
      <div
        style={{
          position: "absolute",
          left: 0,
          top: 0,
          bottom: 0,
          background: "#050505",
          zIndex: 10,
          padding: "0 10px",
          display: "flex",
          alignItems: "center",
          gap: 5,
          borderRight: "1px solid #f59e0b22",
        }}
      >
        {connected ? (
          <Wifi size={10} color="#22c55e" />
        ) : (
          <WifiOff size={10} color="#6b7280" />
        )}
          <span style={{ fontSize: 9, fontFamily: "monospace", color: "#f59e0b", letterSpacing: "0.15em" }}>
          IRIS
        </span>
      </div>

      <div style={{ paddingLeft: 90, overflow: "hidden", flex: 1 }}>
        <div ref={tickerRef} style={{ display: "flex", whiteSpace: "nowrap", willChange: "transform" }}>
          {items.map((sym, i) => {
            const p = prices[sym]
            const up = (p?.change_pct ?? 0) >= 0
            return (
              <span
                key={i}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 5,
                  padding: "0 18px",
                  fontFamily: "monospace",
                  fontSize: 11,
                  borderRight: "1px solid #ffffff08",
                }}
              >
                <span style={{ color: "#f59e0b", fontWeight: 600 }}>{sym}</span>
                <span style={{ color: "#e5e5e5" }}>
                  {p ? (p.price >= 1000 ? p.price.toFixed(0) : p.price.toFixed(3)) : "—"}
                </span>
                <span style={{ color: up ? "#22c55e" : "#ef4444", fontSize: 10 }}>
                  {p ? `${up ? "+" : ""}${p.change_pct.toFixed(2)}%` : "—"}
                </span>
              </span>
            )
          })}
        </div>
      </div>
    </div>
  )
}

// ─── Agent activity row ───────────────────────────────────────────────────────
function AgentActivityRow({
  event,
  index,
}: {
  event: { agent: string; token: string; type: string; amountIn: string; timestamp: number }
  index: number
}) {
  const isBuy = event.type === "swap"
  const d = new Date(event.timestamp * 1000)
  const time = `${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}:${d.getSeconds().toString().padStart(2, "0")}`

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "4px 12px",
        borderBottom: "1px solid #ffffff06",
        fontFamily: "monospace",
        fontSize: 11,
        animation: index === 0 ? "tradeFlash 0.6s ease" : undefined,
      }}
    >
      <span style={{ color: "#374151", minWidth: 60 }}>{time}</span>
      <span
        style={{
          minWidth: 28,
          background: isBuy ? "#22c55e18" : "#ef444418",
          border: `1px solid ${isBuy ? "#22c55e33" : "#ef444433"}`,
          color: isBuy ? "#22c55e" : "#ef4444",
          borderRadius: 2,
          padding: "0 4px",
          fontSize: 9,
          fontWeight: 700,
          letterSpacing: "0.05em",
          textAlign: "center" as const,
        }}
      >
        {isBuy ? "BUY" : "SELL"}
      </span>
      <span style={{ color: "#f59e0b" }}>{event.token}</span>
      <span style={{ color: "#6b7280" }}>
        {event.agent.slice(0, 8)}…
      </span>
      <span style={{ color: "#9ca3af", marginLeft: "auto" }}>
        {parseFloat(event.amountIn || "0").toFixed(4)}
      </span>
    </div>
  )
}

// ─── Market overview panel ────────────────────────────────────────────────────
function MarketPanel() {
  const { prices } = useLivePrices()

  const assets = [
    { sym: "WBTC", label: "BTC" },
    { sym: "ETH",  label: "ETH" },
    { sym: "SOL",  label: "SOL" },
    { sym: "LINK", label: "LINK" },
    { sym: "AAVE", label: "AAVE" },
  ]

  return (
    <div>
      <div
        style={{
          padding: "6px 12px",
          borderBottom: "1px solid #f59e0b22",
          fontSize: 10,
          fontFamily: "monospace",
          color: "#f59e0b",
          letterSpacing: "0.1em",
        }}
      >
        MARKET OVERVIEW
      </div>
      {assets.map(({ sym, label }) => {
        const p = prices[sym]
        const up = (p?.change_pct ?? 0) >= 0
        const pctFromInitial = p ? ((p.price - p.initial) / p.initial) * 100 : 0
        return (
          <div
            key={sym}
            style={{
              display: "flex",
              alignItems: "center",
              padding: "6px 12px",
              borderBottom: "1px solid #ffffff06",
              gap: 8,
            }}
          >
            {up ? <ArrowUpRight size={12} color="#22c55e" /> : <ArrowDownRight size={12} color="#ef4444" />}
            <span style={{ fontFamily: "monospace", fontSize: 11, color: "#f59e0b", minWidth: 34 }}>{label}</span>
            <span style={{ fontFamily: "monospace", fontSize: 11, color: "#e5e5e5", flex: 1 }}>
              {p ? (p.price >= 1000 ? p.price.toFixed(0) : p.price.toFixed(3)) : "—"}
            </span>
            <span style={{ fontFamily: "monospace", fontSize: 10, color: up ? "#22c55e" : "#ef4444" }}>
              {up ? "+" : ""}{p?.change_pct.toFixed(2) ?? "—"}%
            </span>
          </div>
        )
      })}
    </div>
  )
}

// ─── Agent scoreboard ─────────────────────────────────────────────────────────
function AgentScoreboard() {
  const { agents } = useAgents()

  const sorted = [...agents].sort((a, b) => b.score - a.score).slice(0, 8)

  return (
    <div>
      <div
        style={{
          padding: "6px 12px",
          borderBottom: "1px solid #f59e0b22",
          fontSize: 10,
          fontFamily: "monospace",
          color: "#f59e0b",
          letterSpacing: "0.1em",
        }}
      >
        AGENT BOARD
      </div>
      {sorted.map((agent, i) => {
        const isActive = agent.status === "active"
        const pnlUp = agent.pnl >= 0
        return (
          <Link href={`/agents/${agent.id}`} key={agent.id} style={{ textDecoration: "none" }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                padding: "5px 12px",
                borderBottom: "1px solid #ffffff05",
                gap: 8,
                cursor: "pointer",
              }}
              className="hover:bg-white/[0.03] transition-colors"
            >
              <span style={{ fontFamily: "monospace", fontSize: 9, color: "#374151", minWidth: 14 }}>
                {String(i + 1).padStart(2, "0")}
              </span>
              <div
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: "50%",
                  background: isActive ? "#22c55e" : "#374151",
                  flexShrink: 0,
                  boxShadow: isActive ? "0 0 4px #22c55e88" : "none",
                }}
              />
              <span style={{ fontFamily: "monospace", fontSize: 11, color: "#d1d5db", flex: 1, overflow: "hidden", whiteSpace: "nowrap", textOverflow: "ellipsis" }}>
                {agent.name}
              </span>
              <span
                style={{
                  fontFamily: "monospace",
                  fontSize: 10,
                  color: pnlUp ? "#22c55e" : "#ef4444",
                  minWidth: 42,
                  textAlign: "right" as const,
                }}
              >
                {pnlUp ? "+" : ""}{agent.pnl.toFixed(1)}%
              </span>
            </div>
          </Link>
        )
      })}
    </div>
  )
}

// ─── Stats strip ──────────────────────────────────────────────────────────────
function StatsStrip({ agents }: { agents: ReturnType<typeof useAgents>["agents"] }) {
  const active = agents.filter((a) => a.status === "active").length
  const avgSharpe = agents.length
    ? (agents.reduce((s, a) => s + a.sharpe, 0) / agents.length).toFixed(2)
    : "—"
  const totalStake = (agents.reduce((s, a) => s + a.stake, 0) / 1_000_000).toFixed(2)

  const stats = [
    { label: "ACTIVE AGENTS", value: `${active}/${agents.length}` },
    { label: "AVG SHARPE",    value: avgSharpe },
    { label: "AUM",           value: `$${totalStake}M` },
    { label: "SESSION",       value: new Date().toLocaleTimeString("en", { hour12: false }) },
  ]

  return (
    <div
      style={{
        display: "flex",
        borderBottom: "1px solid #f59e0b22",
        borderTop: "1px solid #f59e0b22",
        background: "#050505",
      }}
    >
      {stats.map((s) => (
        <div
          key={s.label}
          style={{
            flex: 1,
            padding: "6px 14px",
            borderRight: "1px solid #ffffff08",
            fontFamily: "monospace",
          }}
        >
          <div style={{ fontSize: 9, color: "#4b5563", letterSpacing: "0.1em" }}>{s.label}</div>
          <div style={{ fontSize: 13, color: "#f59e0b", fontWeight: 600, marginTop: 1 }}>{s.value}</div>
        </div>
      ))}
    </div>
  )
}

// ─── Terminal page ────────────────────────────────────────────────────────────
export default function TerminalPage() {
  const { events, connected: wsConnected } = useTradingFeed()
  const { items: newsItems, signals, loading: newsLoading, error: newsError, refresh } = useNews(25)
  const { agents } = useAgents()
  const [clock, setClock] = useState("")

  useEffect(() => {
    const update = () =>
      setClock(new Date().toLocaleTimeString("en", { hour12: false }))
    update()
    const id = setInterval(update, 1000)
    return () => clearInterval(id)
  }, [])

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#070707",
        display: "flex",
        flexDirection: "column",
        paddingTop: 64, // navbar offset
      }}
    >
      {/* ── CSS animations ── */}
      <style>{`
        @keyframes newsFlash {
          0%   { background: #f59e0b18; }
          100% { background: transparent; }
        }
        @keyframes tradeFlash {
          0%   { background: #22c55e18; }
          100% { background: transparent; }
        }
        ::-webkit-scrollbar { width: 4px; height: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #f59e0b22; border-radius: 2px; }
      `}</style>

      {/* ── Ticker strip ── */}
      <PriceTicker />

      {/* ── Terminal header ── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "6px 14px",
          background: "#050505",
          borderBottom: "1px solid #f59e0b33",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ fontFamily: "monospace", fontSize: 13, fontWeight: 700, color: "#f59e0b", letterSpacing: "0.12em" }}>
            IRIS Protocol TERMINAL
          </span>
          <span
            style={{
              fontSize: 9,
              fontFamily: "monospace",
              color: "#22c55e",
              background: "#22c55e18",
              border: "1px solid #22c55e33",
              borderRadius: 2,
              padding: "1px 5px",
              letterSpacing: "0.08em",
            }}
          >
            LIVE
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 14, fontFamily: "monospace", fontSize: 10, color: "#4b5563" }}>
          <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <Radio size={9} color={wsConnected ? "#22c55e" : "#6b7280"} />
            WS {wsConnected ? "CONNECTED" : "RECONNECTING"}
          </span>
          <span style={{ color: "#6b7280" }}>{clock}</span>
        </div>
      </div>

      {/* ── Stats strip ── */}
      <StatsStrip agents={agents} />

      {/* ── Main 3-column body ── */}
      <div
        style={{
          flex: 1,
          display: "grid",
          gridTemplateColumns: "180px 1fr 300px",
          overflow: "hidden",
          minHeight: 0,
        }}
      >
        {/* Left sidebar: market overview + agent board */}
        <div
          style={{
            borderRight: "1px solid #f59e0b1a",
            overflowY: "auto",
            background: "#050505",
          }}
        >
          <MarketPanel />
          <div style={{ height: 1, background: "#f59e0b22", margin: "4px 0" }} />
          <AgentScoreboard />
        </div>

        {/* Center: candle chart + trade feed */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
            borderRight: "1px solid #f59e0b1a",
          }}
        >
          {/* Chart area */}
          <div
            style={{
              flex: "0 0 auto",
              borderBottom: "1px solid #f59e0b22",
              background: "#080808",
            }}
          >
            <CandleChart
              tradeEvents={events.slice(0, 20)}
              height={380}
              showSymbolTabs
            />
          </div>

          {/* Trade activity feed */}
          <div style={{ flex: 1, overflowY: "auto", background: "#060606" }}>
            <div
              style={{
                padding: "6px 12px",
                borderBottom: "1px solid #f59e0b22",
                display: "flex",
                alignItems: "center",
                gap: 6,
                position: "sticky",
                top: 0,
                background: "#060606",
                zIndex: 1,
              }}
            >
              <Activity size={11} color="#f59e0b" />
              <span style={{ fontSize: 10, fontFamily: "monospace", color: "#f59e0b", letterSpacing: "0.1em" }}>
                EXECUTION FEED
              </span>
              <span
                style={{
                  marginLeft: "auto",
                  fontSize: 9,
                  color: "#4b5563",
                  fontFamily: "monospace",
                }}
              >
                {events.length} events
              </span>
            </div>

            {events.length === 0 ? (
              <div
                style={{
                  padding: "20px 14px",
                  textAlign: "center",
                  fontSize: 11,
                  color: "#374151",
                  fontFamily: "monospace",
                }}
              >
                — Waiting for trade events. Start an agent to see execution data. —
              </div>
            ) : (
              events.slice(0, 50).map((evt, i) => (
                <AgentActivityRow key={i} event={evt} index={i} />
              ))
            )}
          </div>
        </div>

        {/* Right: news feed */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
            background: "#060606",
          }}
        >
          <NewsFeed
            items={newsItems}
            signals={signals}
            loading={newsLoading}
            error={newsError}
            refresh={refresh}
            maxHeight={520}
            showSignals
          />
        </div>
      </div>

      {/* ── Status bar ── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 16,
          padding: "4px 14px",
          background: "#050505",
          borderTop: "1px solid #f59e0b22",
          fontFamily: "monospace",
          fontSize: 9,
          color: "#374151",
        }}
      >
        <span>IRIS Protocol v2.2.0</span>
        <span>|</span>
        <span>TESTNET</span>
        <span>|</span>
        <span style={{ color: agents.filter((a) => a.status === "active").length > 0 ? "#22c55e" : "#374151" }}>
          {agents.filter((a) => a.status === "active").length} AGENTS ACTIVE
        </span>
        <span style={{ marginLeft: "auto" }}>
          LAST UPDATE: {clock}
        </span>
      </div>
    </div>
  )
}
