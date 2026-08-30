"use client"

/**
 * Agent Arena — IRIS_BUILD_PROMPT v2.0 section 15, Phase 10.
 *
 * The leaderboard, driven entirely by `reputation_scores` and
 * `allocation_history`. No fixtures anywhere in this path.
 *
 * The design decision that matters is the **Unranked** section. An agent with
 * no settled predictions has no IRIS Score — Phase 6 returns null rather than
 * 0, precisely so an untested agent cannot outrank one with a proven bad
 * record. Rendering them at the bottom of the same table would undo that: a
 * reader scanning a leaderboard reads "last" as "worst". They get their own
 * section, and it says why.
 */

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { AlertCircle, Loader2, Snowflake, Trophy, Zap } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Card } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import {
  ASSUMED_SIMULATION,
  ProvenanceBadge,
  ProvenanceBanner,
} from "@/components/iris/provenance-banner"
import { useProtocolEvents } from "@/hooks/use-protocol-events"
import {
  ago,
  fetchArena,
  num,
  pct,
  shortHash,
  type Arena,
  type ArenaEntry,
} from "@/lib/protocol"

const DIMENSIONS = [
  "accuracy",
  "calibration",
  "magnitude",
  "consistency",
  "risk_adjusted",
  "conviction",
] as const

const STATUS_STYLE: Record<string, string> = {
  ACTIVE: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  PROBATION: "bg-sky-500/15 text-sky-300 border-sky-500/30",
  FROZEN: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  SLASHED: "bg-red-500/15 text-red-300 border-red-500/30",
  RETIRED: "bg-zinc-500/15 text-zinc-300 border-zinc-500/30",
}

function ScoreBar({ entry }: { entry: ArenaEntry }) {
  const dims = entry.dimensions ?? {}
  return (
    <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 sm:grid-cols-3">
      {DIMENSIONS.map((name) => {
        const value = Number(dims[name] ?? 0)
        return (
          <div key={name} className="space-y-1">
            <div className="flex items-baseline justify-between text-[11px]">
              <span className="text-muted-foreground">{name.replace("_", " ")}</span>
              <span className="font-mono tabular-nums">{value.toFixed(2)}</span>
            </div>
            <Progress value={value * 100} className="h-1" />
          </div>
        )
      })}
    </div>
  )
}

function Row({ entry, rank }: { entry: ArenaEntry; rank: number }) {
  const evidence = Number(entry.dimensions?._evidence ?? 0)
  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 w-6 text-right font-mono text-sm text-muted-foreground tabular-nums">
            {rank}
          </span>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Link
                href={`/observatory?agent=${entry.agent_id}`}
                className="font-medium hover:underline"
              >
                {entry.name}
              </Link>
              <Badge variant="outline" className={STATUS_STYLE[entry.status] ?? ""}>
                {entry.status}
              </Badge>
              <span className="text-xs text-muted-foreground">{entry.strategy}</span>
            </div>
            <p className="mt-1 font-mono text-[11px] text-muted-foreground">
              {entry.model.family ?? "—"} v{entry.model.version ?? "?"} ·{" "}
              {shortHash(entry.model.hash, 6)}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-6 text-right">
          <div>
            <p className="text-[11px] text-muted-foreground">allocation</p>
            <p className="font-mono text-sm tabular-nums">
              {pct(entry.allocation_weight, 1)}
            </p>
          </div>
          <div>
            <p className="text-[11px] text-muted-foreground">settled</p>
            <p className="font-mono text-sm tabular-nums">{entry.settled_count}</p>
          </div>
          <div>
            <p className="text-[11px] text-muted-foreground">IRIS</p>
            <p className="font-mono text-xl font-semibold tabular-nums">
              {num(entry.iris_score, 1)}
            </p>
          </div>
        </div>
      </div>

      <div className="mt-4">
        <ScoreBar entry={entry} />
      </div>

      {/*
        The evidence factor, shown rather than folded silently into the score.
        A 92-quality agent with 12 settled predictions and one with 400 are
        very different propositions, and the multiplier is the only thing on
        screen that says so.
      */}
      <p className="mt-3 text-[11px] text-muted-foreground">
        score = quality × evidence ({evidence.toFixed(2)} over{" "}
        {entry.settled_count} settled predictions) · last settled{" "}
        {ago(entry.last_settled)}
      </p>
    </Card>
  )
}

export default function ArenaPage() {
  const [arena, setArena] = useState<Arena | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    try {
      setArena(await fetchArena())
      setError(null)
    } catch (err) {
      // Surfaced, not swallowed into an empty table. A leaderboard showing
      // nothing because a request failed looks identical to one showing
      // nothing because no agent has been scored yet.
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  // Reload when the protocol says something changed, rather than on a timer.
  const { events, connected } = useProtocolEvents({
    kinds: ["REPUTATION_UPDATED", "ALLOCATION_UPDATED", "AGENT_SLASHED", "AGENT_FROZEN"],
    replay: 0,
  })
  useEffect(() => {
    if (events.length) void load()
  }, [events.length, load])

  // The header renders in every state, including before any data has arrived.
  // The §0c label is a property of the system, not of a successful fetch —
  // rendering it only alongside data left it out of the server HTML and out of
  // the loading and error states, which is where a reader forms their first
  // impression of what they are looking at.
  const shell = (children: React.ReactNode) => (
    <main className="mx-auto max-w-5xl space-y-6 p-6">
      <header className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Trophy className="h-5 w-5 text-primary" />
            <h1 className="text-2xl font-semibold">Agent Arena</h1>
            <ProvenanceBadge
              sources={arena?.provenance.sources ?? ASSUMED_SIMULATION.sources}
            />
          </div>
          <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Zap
              className={`h-3.5 w-3.5 ${connected ? "text-emerald-400" : "text-zinc-500"}`}
            />
            {connected ? "live" : "reconnecting"}
          </span>
        </div>
        <ProvenanceBanner provenance={arena?.provenance ?? ASSUMED_SIMULATION} />
      </header>
      {children}
    </main>
  )

  if (loading) {
    return shell(
      <div className="flex min-h-[30vh] items-center justify-center">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>,
    )
  }

  if (error || !arena) {
    return shell(
      <Card className="flex items-start gap-3 border-red-500/40 bg-red-500/10 p-4">
        <AlertCircle className="mt-0.5 h-4 w-4 text-red-300" />
        <div>
          <p className="font-medium text-red-200">The Arena could not load.</p>
          <p className="mt-1 text-xs text-red-200/80">{error}</p>
        </div>
      </Card>,
    )
  }

  return shell(
    <>
      <div className="grid grid-cols-3 gap-3">
        {[
          ["agents", arena.totals.agents],
          ["scored", arena.totals.scored],
          ["allocated", arena.totals.allocated],
        ].map(([label, value]) => (
          <Card key={label as string} className="p-4">
            <p className="text-xs text-muted-foreground">{label}</p>
            <p className="font-mono text-2xl tabular-nums">{value as number}</p>
          </Card>
        ))}
      </div>

      <section className="space-y-3">
        <h2 className="text-sm font-medium text-muted-foreground">Ranked</h2>
        {arena.ranked.length === 0 ? (
          <Card className="p-6 text-sm text-muted-foreground">
            No agent has a settled record yet. Run{" "}
            <code className="font-mono">make cycle</code> to produce one.
          </Card>
        ) : (
          arena.ranked.map((entry, i) => (
            <Row key={entry.agent_id} entry={entry} rank={i + 1} />
          ))
        )}
      </section>

      {arena.unranked.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-sm font-medium text-muted-foreground">Unranked</h2>
          {/*
            Not "last place". These agents have made no settled prediction, so
            there is nothing to score — and an untested agent must not be shown
            as a bad one. Phase 7 still allocates to them at the floor, which
            is how they get the chance to earn a score.
          */}
          <Card className="border-dashed p-4">
            <p className="mb-3 text-xs text-muted-foreground">
              No settled predictions, so no IRIS Score. Unranked — not ranked
              last. They still receive a floor allocation, which is how they
              earn a record.
            </p>
            <div className="flex flex-wrap gap-2">
              {arena.unranked.map((entry) => (
                <span
                  key={entry.agent_id}
                  className="inline-flex items-center gap-2 rounded-md border px-2.5 py-1 text-xs"
                >
                  {entry.status === "FROZEN" && (
                    <Snowflake className="h-3 w-3 text-amber-400" />
                  )}
                  <span className="font-medium">{entry.name}</span>
                  <span className="text-muted-foreground">{entry.strategy}</span>
                  <span className="font-mono text-muted-foreground tabular-nums">
                    {pct(entry.allocation_weight, 1)}
                  </span>
                </span>
              ))}
            </div>
          </Card>
        </section>
      )}
    </>,
  )
}
