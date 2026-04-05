"use client"

import { useEffect, useRef } from "react"
import { Badge } from "@/components/ui/badge"
import type { NewsItem, NewsSignal } from "@/lib/api"
import { RefreshCw, Loader2, AlertCircle, Radio } from "lucide-react"

// ─── Sentiment helpers ────────────────────────────────────────────────────────
function sentimentColor(hint: NewsItem["sentiment_hint"]): string {
  if (hint === "bullish") return "#22c55e"
  if (hint === "bearish") return "#ef4444"
  return "#6b7280"
}

function sentimentBg(hint: NewsItem["sentiment_hint"]): string {
  if (hint === "bullish") return "#22c55e18"
  if (hint === "bearish") return "#ef444418"
  return "#6b728012"
}

function sentimentLabel(hint: NewsItem["sentiment_hint"]): string {
  if (hint === "bullish") return "BULL"
  if (hint === "bearish") return "BEAR"
  return "NEUT"
}

function timeAgo(published: string): string {
  if (!published || published === "unknown" || published === "just now") return "LIVE"
  try {
    const d = new Date(published)
    if (isNaN(d.getTime())) return published
    const diff = (Date.now() - d.getTime()) / 1000
    if (diff < 60) return `${Math.floor(diff)}s`
    if (diff < 3600) return `${Math.floor(diff / 60)}m`
    if (diff < 86400) return `${Math.floor(diff / 3600)}h`
    return `${Math.floor(diff / 86400)}d`
  } catch {
    return published
  }
}

// ─── Single news row ──────────────────────────────────────────────────────────
function NewsRow({ item, index }: { item: NewsItem; index: number }) {
  const color = sentimentColor(item.sentiment_hint)
  const bg    = sentimentBg(item.sentiment_hint)
  const label = sentimentLabel(item.sentiment_hint)

  return (
    <div
      style={{
        display: "flex",
        gap: 10,
        padding: "9px 10px",
        borderBottom: "1px solid #ffffff08",
        transition: "background 0.15s",
        animation: index === 0 ? "newsFlash 1.2s ease" : undefined,
      }}
      className="group hover:bg-white/[0.03]"
    >
      {/* Sentiment pill */}
      <div
        style={{
          minWidth: 36,
          background: bg,
          border: `1px solid ${color}33`,
          borderRadius: 3,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          height: 18,
          marginTop: 2,
          flexShrink: 0,
        }}
      >
        <span style={{ fontSize: 9, fontFamily: "monospace", color, fontWeight: 700, letterSpacing: "0.05em" }}>
          {label}
        </span>
      </div>

      {/* Content */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <p
          style={{
            fontSize: 12,
            lineHeight: 1.4,
            color: "#d1d5db",
            margin: 0,
            overflow: "hidden",
            display: "-webkit-box",
            WebkitLineClamp: 2,
            WebkitBoxOrient: "vertical" as const,
          }}
        >
          {item.title}
        </p>
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 4, flexWrap: "wrap" }}>
          <span style={{ fontSize: 10, color: "#4b5563", fontFamily: "monospace" }}>
            {item.source?.toUpperCase()}
          </span>
          {item.coins?.slice(0, 3).map((coin) => (
            <span
              key={coin}
              style={{
                fontSize: 9,
                color: "#f59e0b",
                background: "#f59e0b12",
                border: "1px solid #f59e0b33",
                borderRadius: 2,
                padding: "0px 4px",
                fontFamily: "monospace",
              }}
            >
              {coin}
            </span>
          ))}
          <span style={{ fontSize: 10, color: "#374151", fontFamily: "monospace", marginLeft: "auto" }}>
            {timeAgo(item.published)}
          </span>
        </div>
      </div>
    </div>
  )
}

// ─── Signals panel ────────────────────────────────────────────────────────────
function SignalRow({ signal }: { signal: NewsSignal }) {
  const isPositive = signal.sentiment > 0.1
  const isNegative = signal.sentiment < -0.1
  const color = isPositive ? "#22c55e" : isNegative ? "#ef4444" : "#6b7280"
  const pct   = Math.round(Math.abs(signal.sentiment) * 100)
  const conf  = Math.round(signal.confidence * 100)

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        padding: "7px 10px",
        borderBottom: "1px solid #ffffff06",
        gap: 8,
      }}
    >
      <span
        style={{
          minWidth: 36,
          fontFamily: "monospace",
          fontSize: 11,
          fontWeight: 700,
          color: "#f59e0b",
        }}
      >
        {signal.asset}
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 11, color: "#9ca3af", overflow: "hidden", whiteSpace: "nowrap", textOverflow: "ellipsis" }}>
          {signal.event}
        </div>
      </div>
      <div style={{ textAlign: "right", flexShrink: 0 }}>
        <div style={{ fontSize: 11, fontFamily: "monospace", color, fontWeight: 600 }}>
          {isPositive ? "+" : isNegative ? "-" : "~"}{pct}%
        </div>
        <div style={{ fontSize: 9, color: "#4b5563" }}>conf {conf}%</div>
      </div>
    </div>
  )
}

// ─── Main news feed component ─────────────────────────────────────────────────
interface NewsFeedProps {
  items: NewsItem[]
  signals: NewsSignal[]
  loading: boolean
  error: string | null
  refresh: () => void
  /** Max height for the scrollable news list */
  maxHeight?: number
  showSignals?: boolean
}

export function NewsFeed({
  items,
  signals,
  loading,
  error,
  refresh,
  maxHeight = 420,
  showSignals = true,
}: NewsFeedProps) {
  const scrollRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to top on new items
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = 0
    }
  }, [items.length])

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* News header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "8px 10px",
          borderBottom: "1px solid #f59e0b22",
          flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <Radio size={12} color="#f59e0b" />
          <span style={{ fontSize: 11, fontFamily: "monospace", color: "#f59e0b", letterSpacing: "0.1em" }}>
            MARKET INTEL
          </span>
          {items.length > 0 && (
            <span style={{ fontSize: 9, color: "#4b5563", fontFamily: "monospace" }}>
              ({items.length})
            </span>
          )}
        </div>
        <button
          onClick={refresh}
          disabled={loading}
          style={{ background: "transparent", border: "none", cursor: "pointer", color: "#4b5563", padding: 2 }}
        >
          {loading ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
        </button>
      </div>

      {/* Error state */}
      {error && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            padding: "6px 10px",
            background: "#ef444410",
            borderBottom: "1px solid #ef444430",
            fontSize: 11,
            color: "#ef4444",
          }}
        >
          <AlertCircle size={11} />
          {error} — showing cached data
        </div>
      )}

      {/* News scroll */}
      <div
        ref={scrollRef}
        style={{
          overflowY: "auto",
          maxHeight,
          flex: 1,
          scrollbarWidth: "thin",
          scrollbarColor: "#f59e0b22 transparent",
        }}
      >
        {loading && items.length === 0 ? (
          <div style={{ display: "flex", justifyContent: "center", padding: 24 }}>
            <Loader2 size={18} className="animate-spin" color="#f59e0b" />
          </div>
        ) : items.length === 0 ? (
          <div style={{ padding: "24px 12px", textAlign: "center", fontSize: 12, color: "#4b5563" }}>
            No news available
          </div>
        ) : (
          items.map((item, i) => <NewsRow key={`${item.title}-${i}`} item={item} index={i} />)
        )}
      </div>

      {/* Signals panel */}
      {showSignals && signals.length > 0 && (
        <>
          <div
            style={{
              padding: "7px 10px",
              borderTop: "1px solid #f59e0b22",
              borderBottom: "1px solid #f59e0b22",
              flexShrink: 0,
            }}
          >
            <span style={{ fontSize: 10, fontFamily: "monospace", color: "#f59e0b", letterSpacing: "0.1em" }}>
              AI SIGNALS
            </span>
          </div>
          <div style={{ overflowY: "auto", maxHeight: 180, scrollbarWidth: "thin", scrollbarColor: "#f59e0b22 transparent" }}>
            {signals.map((s, i) => <SignalRow key={i} signal={s} />)}
          </div>
        </>
      )}
    </div>
  )
}
