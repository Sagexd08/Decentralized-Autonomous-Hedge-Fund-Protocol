"use client"

/**
 * Agent Floor — replaces the old World Monitor.
 *
 * That page rendered hardcoded macro headlines and a fake globe with no
 * fetch behind any of it — the exact thing section 0c exists to prevent,
 * just never wired to a `ProvenanceBanner` because nothing here ever
 * pretended to be real to begin with. This page shows what actually happens:
 * agents committing predictions, getting scored, and having capital
 * reallocated between them, read live off `/ws/events` — the same outbox
 * Arena and Ledger already trust, with no invented traffic and no timers.
 *
 * "Agents crossing" is not a board-game metaphor here. It is literal:
 * `ALLOCATION_UPDATED` is capital moving from one agent's weight to
 * another's, and this page's whole point is to make that motion visible as
 * it happens rather than only as an after-the-fact leaderboard delta.
 */

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import {
  Activity,
  AlertTriangle,
  ArrowRightLeft,
  Loader2,
  Radar,
  Snowflake,
  Zap,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Card } from "@/components/ui/card"
import {
  ASSUMED_SIMULATION,
  ProvenanceBadge,
  ProvenanceBanner,
} from "@/components/iris/provenance-banner"
import { useProtocolEvents } from "@/hooks/use-protocol-events"
import { ago, fetchArena, pct, type Arena, type ArenaEntry, type ProtocolEvent } from "@/lib/protocol"

const WATCHED_KINDS = [
  "RUN_STARTED",
  "RUN_SUCCEEDED",
  "RUN_FAILED",
  "NODE_COMPLETED",
  "PREDICTION_PREDICTED",
  "PREDICTION_COMMITTED",
  "PREDICTION_SETTLED",
  "PREDICTION_SCORED",
  "REPUTATION_UPDATED",
  "ALLOCATION_UPDATED",
  "RISK_DRAWDOWN_BREACH",
  "RISK_VOLATILITY_BREACH",
  "RISK_VAR_BREACH",
  "AGENT_SLASHED",
  "AGENT_FROZEN",
  "AGENT_ACTIVE",
  "AGENT_RETIRED",
]

const STATUS_STYLE: Record<string, string> = {
  ACTIVE: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  PROBATION: "bg-sky-500/15 text-sky-300 border-sky-500/30",
  FROZEN: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  SLASHED: "bg-red-500/15 text-red-300 border-red-500/30",
  RETIRED: "bg-zinc-500/15 text-zinc-300 border-zinc-500/30",
}

const KIND_STYLE: Record<string, { label: string; className: string }> = {
  RUN_STARTED: { label: "run started", className: "border-sky-500/30 text-sky-300" },
  RUN_SUCCEEDED: { label: "run ok", className: "border-emerald-500/30 text-emerald-300" },
  RUN_FAILED: { label: "run failed", className: "border-red-500/30 text-red-300" },
  NODE_COMPLETED: { label: "node", className: "border-zinc-500/30 text-zinc-300" },
  PREDICTION_PREDICTED: { label: "predicted", className: "border-sky-500/30 text-sky-300" },
  PREDICTION_COMMITTED: { label: "committed", className: "border-primary/30 text-primary" },
  PREDICTION_SETTLED: { label: "settled", className: "border-zinc-500/30 text-zinc-300" },
  PREDICTION_SCORED: { label: "scored", className: "border-emerald-500/30 text-emerald-300" },
  REPUTATION_UPDATED: { label: "reputation", className: "border-violet-500/30 text-violet-300" },
  ALLOCATION_UPDATED: { label: "capital crossed", className: "border-accent/40 text-accent" },
  AGENT_SLASHED: { label: "slashed", className: "border-red-500/30 text-red-300" },
  AGENT_FROZEN: { label: "frozen", className: "border-amber-500/30 text-amber-300" },
  AGENT_ACTIVE: { label: "reinstated", className: "border-emerald-500/30 text-emerald-300" },
  AGENT_RETIRED: { label: "retired", className: "border-zinc-500/30 text-zinc-300" },
}

function kindStyle(kind: string) {
  if (kind.startsWith("RISK_")) {
    return { label: kind.replace("RISK_", "").replace(/_/g, " ").toLowerCase(), className: "border-red-500/30 text-red-300" }
  }
  return KIND_STYLE[kind] ?? { label: kind.replace(/_/g, " ").toLowerCase(), className: "border-zinc-500/30 text-zinc-300" }
}

function agentLabel(entry: ArenaEntry | undefined, agentId: string | null) {
  if (entry) return entry.name
  return agentId ?? "protocol"
}

function EventLine({ event, agentName }: { event: ProtocolEvent; agentName: string }) {
  const style = kindStyle(event.kind)
  const payload = event.payload ?? {}

  let detail: string | null = null
  if (event.kind === "ALLOCATION_UPDATED") {
    detail = `weight → ${pct(payload.weight as number, 1)}`
  } else if (event.kind.startsWith("PREDICTION_")) {
    detail = [payload.asset, payload.direction].filter(Boolean).join(" ")
  } else if (event.kind === "REPUTATION_UPDATED") {
    const score = payload.iris_score
    detail = score === null || score === undefined ? "unranked" : `IRIS ${Number(score).toFixed(1)}`
  } else if (event.kind.startsWith("RISK_")) {
    detail = `${payload.measured_bps ?? "?"}bps vs ${payload.limit_bps ?? "?"}bps limit`
  }

  return (
    <div className="flex items-center gap-3 border-b border-border/20 px-4 py-2.5 text-sm last:border-0">
      <span className="w-16 shrink-0 font-mono text-[11px] text-muted-foreground tabular-nums">
        {ago(event.created_at)}
      </span>
      <Badge variant="outline" className={`shrink-0 text-[10px] ${style.className}`}>
        {style.label}
      </Badge>
      <span className="shrink-0 font-medium">{agentName}</span>
      {detail && <span className="truncate font-mono text-xs text-muted-foreground">{detail}</span>}
      <span className="ml-auto shrink-0 font-mono text-[10px] text-muted-foreground/60">
        {event.data_source}
      </span>
    </div>
  )
}

function Lane({ entry, active }: { entry: ArenaEntry; active: boolean }) {
  return (
    <Card className={`relative overflow-hidden p-4 transition-colors ${active ? "border-accent/50" : ""}`}>
      {active && (
        <span className="absolute inset-x-0 top-0 h-0.5 animate-pulse bg-accent" aria-hidden />
      )}
      <div className="flex items-start justify-between gap-2">
        <div>
          <Link href={`/observatory?agent=${entry.agent_id}`} className="font-medium hover:underline">
            {entry.name}
          </Link>
          <p className="text-xs text-muted-foreground">{entry.strategy}</p>
        </div>
        <Badge variant="outline" className={STATUS_STYLE[entry.status] ?? ""}>
          {entry.status === "FROZEN" && <Snowflake className="mr-1 h-3 w-3" />}
          {entry.status}
        </Badge>
      </div>
      <div className="mt-3 flex items-end justify-between">
        <div>
          <p className="text-[11px] text-muted-foreground">allocation</p>
          <p className="font-mono text-lg tabular-nums">{pct(entry.allocation_weight, 1)}</p>
        </div>
        <div className="text-right">
          <p className="text-[11px] text-muted-foreground">IRIS</p>
          <p className="font-mono text-lg tabular-nums">
            {entry.iris_score === null ? "—" : entry.iris_score.toFixed(1)}
          </p>
        </div>
      </div>
    </Card>
  )
}

export default function WorldMonitorPage() {
  const [arena, setArena] = useState<Arena | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    fetchArena()
      .then((data) => !cancelled && setArena(data))
      .catch((err) => !cancelled && setError(err instanceof Error ? err.message : String(err)))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [])

  const { events, connected } = useProtocolEvents({ kinds: WATCHED_KINDS, replay: 60 })

  // Re-poll the roster on anything that changes an agent's standing, so lanes
  // reflect the same numbers the event ledger is describing rather than
  // drifting from a stale initial fetch.
  useEffect(() => {
    if (!events.length) return
    const kind = events[0].kind
    if (!["ALLOCATION_UPDATED", "REPUTATION_UPDATED", "AGENT_SLASHED", "AGENT_FROZEN", "AGENT_ACTIVE", "AGENT_RETIRED"].includes(kind)) {
      return
    }
    fetchArena().then(setArena).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [events.length])

  const allAgents = useMemo(
    () => [...(arena?.ranked ?? []), ...(arena?.unranked ?? [])],
    [arena],
  )
  const byId = useMemo(() => {
    const map = new Map<string, ArenaEntry>()
    for (const entry of allAgents) map.set(entry.agent_id, entry)
    return map
  }, [allAgents])

  // Agents with activity in the last ~20s, for the pulse on their lane.
  const recentlyActive = useMemo(() => {
    const cutoff = Date.now() - 20_000
    const set = new Set<string>()
    for (const event of events) {
      if (!event.agent_id) continue
      if (new Date(event.created_at).getTime() >= cutoff) set.add(event.agent_id)
    }
    return set
  }, [events])

  const crossings = useMemo(
    () => events.filter((e) => e.kind === "ALLOCATION_UPDATED").slice(0, 8),
    [events],
  )

  const provenance = arena?.provenance ?? ASSUMED_SIMULATION

  return (
    <main className="mx-auto max-w-6xl space-y-6 p-6">
      <header className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Radar className="h-5 w-5 text-primary" />
            <h1 className="text-2xl font-semibold">Agent Floor</h1>
            <ProvenanceBadge sources={provenance.sources} />
          </div>
          <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Zap className={`h-3.5 w-3.5 ${connected ? "text-emerald-400" : "text-zinc-500"}`} />
            {connected ? "live" : "reconnecting"}
          </span>
        </div>
        <p className="text-sm text-muted-foreground">
          Every agent's lane, and the live outbox of everything they're doing — predictions
          committed, outcomes settled, scores updated, capital crossing between them as
          allocation shifts.
        </p>
        <ProvenanceBanner provenance={provenance} />
      </header>

      {loading ? (
        <div className="flex min-h-[30vh] items-center justify-center">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      ) : error || !arena ? (
        <Card className="flex items-start gap-3 border-red-500/40 bg-red-500/10 p-4">
          <AlertTriangle className="mt-0.5 h-4 w-4 text-red-300" />
          <div>
            <p className="font-medium text-red-200">The Floor could not load.</p>
            <p className="mt-1 text-xs text-red-200/80">{error}</p>
          </div>
        </Card>
      ) : (
        <>
          {crossings.length > 0 && (
            <section className="space-y-2">
              <h2 className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
                <ArrowRightLeft className="h-3.5 w-3.5" />
                Recent crossings
              </h2>
              <div className="flex flex-wrap gap-2">
                {crossings.map((event) => {
                  const entry = event.agent_id ? byId.get(event.agent_id) : undefined
                  return (
                    <span
                      key={event.seq}
                      className="inline-flex items-center gap-2 rounded-md border border-accent/30 bg-accent/5 px-2.5 py-1 text-xs"
                    >
                      <span className="font-medium">{agentLabel(entry, event.agent_id)}</span>
                      <span className="font-mono text-accent">
                        → {pct(event.payload.weight as number, 1)}
                      </span>
                      <span className="text-muted-foreground">{ago(event.created_at)}</span>
                    </span>
                  )
                })}
              </div>
            </section>
          )}

          <section className="space-y-3">
            <h2 className="text-sm font-medium text-muted-foreground">
              Floor ({allAgents.length} agents)
            </h2>
            {allAgents.length === 0 ? (
              <Card className="p-6 text-sm text-muted-foreground">No agents registered yet.</Card>
            ) : (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
                {allAgents.map((entry) => (
                  <Lane key={entry.agent_id} entry={entry} active={recentlyActive.has(entry.agent_id)} />
                ))}
              </div>
            )}
          </section>

          <section className="space-y-3">
            <h2 className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
              <Activity className="h-3.5 w-3.5" />
              Live activity
            </h2>
            <Card className="overflow-hidden p-0">
              {events.length === 0 ? (
                <p className="p-6 text-sm text-muted-foreground">
                  No activity yet. Run <code className="font-mono">make cycle</code> to produce
                  some.
                </p>
              ) : (
                <div className="max-h-[480px] overflow-y-auto">
                  {events.map((event) => (
                    <EventLine
                      key={event.seq}
                      event={event}
                      agentName={agentLabel(event.agent_id ? byId.get(event.agent_id) : undefined, event.agent_id)}
                    />
                  ))}
                </div>
              )}
            </Card>
          </section>
        </>
      )}
    </main>
  )
}
