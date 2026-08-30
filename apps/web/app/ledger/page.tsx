"use client"

/**
 * Prediction Ledger — IRIS_BUILD_PROMPT v2.0 section 15, Phase 12.
 *
 * What was claimed, and what happened. Read from `predictions` and
 * `prediction_outcomes`.
 *
 * The screen is built around the commit-before-outcome primitive (§5): a hash
 * written and timestamped *before* the horizon it will be judged against, then
 * a settlement measured after. Both timestamps are shown side by side, because
 * the whole claim of the protocol is that the first precedes the second and the
 * database enforces it.
 *
 * `WAITING_FOR_OUTCOME` gets its own treatment rather than a spinner. It does
 * not mean "loading" or "not due yet" — it means the horizon has closed and
 * the protocol has *no price evidence*, so it is declining to score. That is
 * the most honest thing the system does, and collapsing it into a pending state
 * would hide it.
 */

import { useCallback, useEffect, useState } from "react"
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  FileQuestion,
  Loader2,
  Lock,
  ScrollText,
  XCircle,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Card } from "@/components/ui/card"
import {
  ASSUMED_SIMULATION,
  ProvenanceBadge,
  ProvenanceBanner,
} from "@/components/iris/provenance-banner"
import { useProtocolEvents } from "@/hooks/use-protocol-events"
import {
  ago,
  fetchLedger,
  num,
  pct,
  shortHash,
  type Ledger,
  type LedgerEntry,
} from "@/lib/protocol"

const STATUS_FILTERS = [
  ["all", null],
  ["committed", "COMMITTED"],
  ["waiting", "WAITING_FOR_OUTCOME"],
  ["evaluated", "EVALUATED"],
] as const

const DIRECTION_STYLE: Record<string, string> = {
  BUY: "text-emerald-400",
  SELL: "text-red-400",
  HOLD: "text-muted-foreground",
}

function Outcome({ entry }: { entry: LedgerEntry }) {
  if (entry.status === "WAITING_FOR_OUTCOME") {
    return (
      <div className="flex items-start gap-2 text-xs text-amber-300">
        <FileQuestion className="mt-0.5 h-3.5 w-3.5 shrink-0" />
        <span>
          Horizon closed with no price evidence. Deliberately unscored — it
          counts toward nothing.
        </span>
      </div>
    )
  }

  if (entry.evaluation_score === null || entry.evaluation_score === undefined) {
    return (
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Clock className="h-3.5 w-3.5" />
        <span>Horizon open until {new Date(entry.horizon_end).toLocaleTimeString()}</span>
      </div>
    )
  }

  const correct = entry.direction_correct
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-xs">
      <span className={`flex items-center gap-1.5 ${correct ? "text-emerald-400" : "text-red-400"}`}>
        {correct ? <CheckCircle2 className="h-3.5 w-3.5" /> : <XCircle className="h-3.5 w-3.5" />}
        {correct ? "correct" : "wrong"}
      </span>
      <span className="text-muted-foreground">
        actual <span className="font-mono tabular-nums">{pct(entry.actual_return, 3)}</span>
      </span>
      <span className="text-muted-foreground">
        error <span className="font-mono tabular-nums">{num(entry.error, 5)}</span>
      </span>
      <span className="text-muted-foreground">
        score{" "}
        <span className="font-mono tabular-nums">{num(entry.evaluation_score, 1)}</span>
      </span>
    </div>
  )
}

function Entry({ entry }: { entry: LedgerEntry }) {
  return (
    <Card className="space-y-3 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className={`font-mono font-semibold ${DIRECTION_STYLE[entry.direction]}`}>
              {entry.direction}
            </span>
            <span className="font-medium">{entry.asset}</span>
            <Badge variant="outline" className="text-[10px]">
              {entry.status}
            </Badge>
            {entry.data_source && (
              <ProvenanceBadge sources={[entry.data_source]} />
            )}
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {entry.agent_name ?? entry.agent_id} · expected{" "}
            <span className="font-mono tabular-nums">
              {pct(entry.expected_return, 3)}
            </span>{" "}
            at confidence{" "}
            <span className="font-mono tabular-nums">{num(entry.confidence, 2)}</span>
          </p>
        </div>
        <span className="text-xs text-muted-foreground">{ago(entry.committed_at)}</span>
      </div>

      {/*
        The primitive, made visible. The hash was written at `committed_at`,
        which is before `horizon_end` — and a database trigger rejects any
        outcome whose `settled_at` precedes that horizon, so this ordering is
        not a convention the UI is asserting.
      */}
      <div className="flex flex-wrap items-center gap-2 rounded-md bg-muted/40 px-3 py-2 text-[11px]">
        <Lock className="h-3 w-3 shrink-0 text-muted-foreground" />
        <span className="font-mono" title={entry.prediction_hash}>
          {shortHash(entry.prediction_hash, 10)}
        </span>
        <span className="text-muted-foreground">
          committed{" "}
          {entry.committed_at
            ? new Date(entry.committed_at).toLocaleTimeString()
            : "—"}{" "}
          → horizon {new Date(entry.horizon_end).toLocaleTimeString()}
        </span>
        {entry.committed_before_horizon && (
          <span className="text-emerald-400">✓ before the outcome existed</span>
        )}
      </div>

      <Outcome entry={entry} />
    </Card>
  )
}

export default function LedgerPage() {
  const [ledger, setLedger] = useState<Ledger | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    try {
      setLedger(await fetchLedger({ status: status ?? undefined, limit: 60 }))
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }, [status])

  useEffect(() => {
    void load()
  }, [load])

  const { events, connected } = useProtocolEvents({
    kinds: [
      "PREDICTION_COMMITTED",
      "PREDICTION_SETTLED",
      "PREDICTION_SCORED",
      "PREDICTION_WAITING_FOR_OUTCOME",
    ],
    replay: 0,
  })
  useEffect(() => {
    if (events.length) void load()
  }, [events.length, load])

  // Rendered in every state, including before data arrives — the §0c label is
  // a property of the system, not of a successful fetch.
  const shell = (children: React.ReactNode) => (
    <main className="mx-auto max-w-4xl space-y-6 p-6">
      <header className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <ScrollText className="h-5 w-5 text-primary" />
            <h1 className="text-2xl font-semibold">Prediction Ledger</h1>
            <ProvenanceBadge
              sources={ledger?.provenance.sources ?? ASSUMED_SIMULATION.sources}
            />
          </div>
          <span
            className={`text-xs ${connected ? "text-emerald-400" : "text-muted-foreground"}`}
          >
            {connected ? "live" : "reconnecting"}
          </span>
        </div>
        <ProvenanceBanner provenance={ledger?.provenance ?? ASSUMED_SIMULATION} />
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

  if (error || !ledger) {
    return shell(
      <Card className="flex items-start gap-3 border-red-500/40 bg-red-500/10 p-4">
        <AlertCircle className="mt-0.5 h-4 w-4 text-red-300" />
        <div>
          <p className="font-medium text-red-200">The Ledger could not load.</p>
          <p className="mt-1 text-xs text-red-200/80">{error}</p>
        </div>
      </Card>,
    )
  }

  const { counts, summary } = ledger

  return shell(
    <>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Card className="p-3">
          <p className="text-[11px] text-muted-foreground">committed</p>
          <p className="font-mono text-xl tabular-nums">{counts.committed}</p>
        </Card>
        <Card className="border-amber-500/30 p-3">
          <p className="text-[11px] text-amber-300">waiting</p>
          <p className="font-mono text-xl tabular-nums">{counts.waiting}</p>
          <p className="mt-0.5 text-[10px] leading-tight text-muted-foreground">
            no evidence — unscored
          </p>
        </Card>
        <Card className="p-3">
          <p className="text-[11px] text-muted-foreground">evaluated</p>
          <p className="font-mono text-xl tabular-nums">{counts.evaluated}</p>
        </Card>
        <Card className="p-3">
          <p className="text-[11px] text-muted-foreground">accuracy</p>
          <p className="font-mono text-xl tabular-nums">
            {summary.accuracy === null ? "—" : pct(summary.accuracy, 1)}
          </p>
          <p className="mt-0.5 text-[10px] leading-tight text-muted-foreground">
            {summary.correct}/{summary.scored} scored
          </p>
        </Card>
      </div>

      <div className="flex flex-wrap gap-2">
        {STATUS_FILTERS.map(([label, value]) => (
          <button
            key={label}
            type="button"
            onClick={() => setStatus(value)}
            className={`rounded-md border px-3 py-1 text-xs transition-colors ${
              status === value ? "border-primary bg-primary/10" : "hover:bg-muted/40"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <section className="space-y-3">
        {ledger.predictions.length === 0 ? (
          <Card className="p-6 text-sm text-muted-foreground">
            No predictions match this filter.
          </Card>
        ) : (
          ledger.predictions.map((entry) => <Entry key={entry.id} entry={entry} />)
        )}
      </section>
    </>,
  )
}
