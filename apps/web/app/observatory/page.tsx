"use client"

/**
 * AI Observatory — IRIS_BUILD_PROMPT v2.0 section 15, Phase 11.
 *
 * How a decision was actually made, read from `agent_runs` and
 * `graph_checkpoints`. Eleven nodes per committing run, each with its latency
 * and the hash of the state it produced.
 *
 * The chain indicator is the point of the screen. Each checkpoint's
 * `input_hash` equals the previous node's `output_hash`, so the trace is a
 * chain rather than eleven snapshots — meaning it can be *verified* rather than
 * believed. A screen that just listed the nodes in order would look identical
 * whether or not that held.
 */

import { Suspense, useCallback, useEffect, useState } from "react"
import { useSearchParams } from "next/navigation"
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Link2,
  Link2Off,
  Loader2,
  MinusCircle,
  Radio,
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
  fetchRun,
  fetchRuns,
  num,
  pct,
  shortHash,
  type RunDetail,
  type RunSummary,
} from "@/lib/protocol"

const OUTCOME_ICON: Record<string, typeof CheckCircle2> = {
  COMPLETED: CheckCircle2,
  ABSTAINED: MinusCircle,
  FAILED: XCircle,
  RUNNING: Loader2,
}

const OUTCOME_STYLE: Record<string, string> = {
  COMPLETED: "text-emerald-400",
  // Not an error colour. Declining to trade because the risk layer objected is
  // the system working, and Phase 3 records it as ABSTAINED rather than FAILED
  // for the same reason.
  ABSTAINED: "text-sky-400",
  FAILED: "text-red-400",
  RUNNING: "text-muted-foreground",
}

function RunRow({
  run,
  selected,
  onSelect,
}: {
  run: RunSummary
  selected: boolean
  onSelect: (id: string) => void
}) {
  const Icon = OUTCOME_ICON[run.status] ?? Clock
  return (
    <button
      type="button"
      onClick={() => onSelect(run.id)}
      className={`w-full rounded-lg border p-3 text-left transition-colors ${
        selected ? "border-primary bg-primary/5" : "hover:bg-muted/40"
      }`}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 truncate">
          <Icon
            className={`h-4 w-4 shrink-0 ${OUTCOME_STYLE[run.status] ?? ""} ${
              run.status === "RUNNING" ? "animate-spin" : ""
            }`}
          />
          <span className="truncate text-sm font-medium">
            {run.agent_name ?? run.agent_id}
          </span>
          <span className="hidden text-xs text-muted-foreground sm:inline">
            {run.strategy}
          </span>
        </div>
        <div className="flex shrink-0 items-center gap-3 text-xs text-muted-foreground">
          <span className="font-mono tabular-nums">{run.nodes} nodes</span>
          <span className="font-mono tabular-nums">{run.latency_ms ?? "—"}ms</span>
          <span>{ago(run.started_at)}</span>
        </div>
      </div>
    </button>
  )
}

function NodeTrace({ detail }: { detail: RunDetail }) {
  const slowest = Math.max(1, ...detail.checkpoints.map((c) => c.latency_ms ?? 0))

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        {detail.chain_intact ? (
          <>
            <Link2 className="h-4 w-4 text-emerald-400" />
            <span className="text-xs text-emerald-300">
              Hash chain intact — each node&apos;s input is the previous node&apos;s output
            </span>
          </>
        ) : (
          <>
            <Link2Off className="h-4 w-4 text-red-400" />
            <span className="text-xs text-red-300">
              Hash chain broken — this trace cannot be verified
            </span>
          </>
        )}
      </div>

      <ol className="space-y-1.5">
        {detail.checkpoints.map((cp) => (
          <li key={cp.seq} className="flex items-center gap-3 text-sm">
            <span className="w-5 text-right font-mono text-[11px] text-muted-foreground tabular-nums">
              {cp.seq}
            </span>
            <span className="w-48 shrink-0 font-mono text-xs">{cp.node}</span>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-primary/60"
                style={{ width: `${((cp.latency_ms ?? 0) / slowest) * 100}%` }}
              />
            </div>
            <span className="w-14 text-right font-mono text-[11px] tabular-nums text-muted-foreground">
              {cp.latency_ms ?? 0}ms
            </span>
            <span
              className="w-24 truncate font-mono text-[11px] text-muted-foreground"
              title={cp.output_hash}
            >
              {shortHash(cp.output_hash, 6)}
            </span>
          </li>
        ))}
      </ol>
    </div>
  )
}

/**
 * The page, split around its `useSearchParams` call.
 *
 * Next prerenders every page at build time, and `useSearchParams` cannot be
 * prerendered — the query string is not known until a request exists. Without
 * a Suspense boundary to bail out at, the production build fails outright:
 *
 *     useSearchParams() should be wrapped in a suspense boundary at
 *     page "/observatory"
 *
 * `next dev` renders on demand and never hits this, so the error appears for
 * the first time in a deployment build. The fallback is the same header the
 * page shows while loading, so the §0c provenance notice — which lives in the
 * route layout above this — is on screen either way.
 */
export default function ObservatoryPage() {
  return (
    <Suspense
      fallback={
        <main className="mx-auto max-w-6xl space-y-6 p-6">
          <div className="flex min-h-[30vh] items-center justify-center">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        </main>
      }
    >
      <Observatory />
    </Suspense>
  )
}


function Observatory() {
  const params = useSearchParams()
  const agentFilter = params.get("agent") ?? undefined

  const [runs, setRuns] = useState<RunSummary[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [detail, setDetail] = useState<RunDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const loadRuns = useCallback(async () => {
    try {
      const data = await fetchRuns(agentFilter, 30)
      setRuns(data.runs)
      setSelected((current) => current ?? data.runs[0]?.id ?? null)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }, [agentFilter])

  useEffect(() => {
    void loadRuns()
  }, [loadRuns])

  useEffect(() => {
    if (!selected) return
    let cancelled = false
    fetchRun(selected)
      .then((d) => !cancelled && setDetail(d))
      .catch((err) => !cancelled && setError(String(err)))
    return () => {
      cancelled = true
    }
  }, [selected])

  const { events, connected } = useProtocolEvents({
    agent: agentFilter,
    kinds: ["RUN_STARTED", "RUN_COMPLETED", "RUN_ABSTAINED", "RUN_FAILED"],
    replay: 0,
  })
  useEffect(() => {
    if (events.length) void loadRuns()
  }, [events.length, loadRuns])

  // Rendered in every state, including before data arrives — the §0c label is
  // a property of the system, not of a successful fetch.
  const header = (
    <header className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Radio className="h-5 w-5 text-primary" />
          <h1 className="text-2xl font-semibold">AI Observatory</h1>
          <ProvenanceBadge
            sources={detail?.provenance.sources ?? ASSUMED_SIMULATION.sources}
          />
          {agentFilter && <Badge variant="outline">{agentFilter}</Badge>}
        </div>
        <span
          className={`text-xs ${connected ? "text-emerald-400" : "text-muted-foreground"}`}
        >
          {connected ? "live" : "reconnecting"}
        </span>
      </div>
      <ProvenanceBanner provenance={detail?.provenance ?? ASSUMED_SIMULATION} />
    </header>
  )

  if (loading) {
    return (
      <main className="mx-auto max-w-6xl space-y-6 p-6">
        {header}
        <div className="flex min-h-[30vh] items-center justify-center">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      </main>
    )
  }

  return (
    <main className="mx-auto max-w-6xl space-y-6 p-6">
      {header}

      {error && (
        <Card className="flex items-start gap-3 border-red-500/40 bg-red-500/10 p-4">
          <AlertCircle className="mt-0.5 h-4 w-4 text-red-300" />
          <p className="text-sm text-red-200">{error}</p>
        </Card>
      )}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <section className="space-y-2">
          <h2 className="text-sm font-medium text-muted-foreground">
            Runs ({runs.length})
          </h2>
          {runs.length === 0 ? (
            <Card className="p-6 text-sm text-muted-foreground">
              No agent has run yet. Try{" "}
              <code className="font-mono">make cycle</code>.
            </Card>
          ) : (
            <div className="max-h-[70vh] space-y-2 overflow-y-auto pr-1">
              {runs.map((run) => (
                <RunRow
                  key={run.id}
                  run={run}
                  selected={run.id === selected}
                  onSelect={setSelected}
                />
              ))}
            </div>
          )}
        </section>

        <section className="space-y-4">
          {detail ? (
            <>
              <Card className="space-y-4 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="font-medium">
                      {detail.run.agent_name ?? detail.run.agent_id}
                    </p>
                    <p className="font-mono text-[11px] text-muted-foreground">
                      {detail.run.id}
                    </p>
                  </div>
                  <Badge
                    variant="outline"
                    className={OUTCOME_STYLE[detail.run.status] ?? ""}
                  >
                    {detail.run.status}
                  </Badge>
                </div>
                <NodeTrace detail={detail} />
              </Card>

              {detail.prediction ? (
                <Card className="space-y-3 p-4">
                  <h3 className="text-sm font-medium">Commitment</h3>
                  <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
                    <div>
                      <dt className="text-xs text-muted-foreground">direction</dt>
                      <dd className="font-mono">
                        {detail.prediction.direction} {detail.prediction.asset}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs text-muted-foreground">expected</dt>
                      <dd className="font-mono tabular-nums">
                        {pct(detail.prediction.expected_return, 3)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs text-muted-foreground">confidence</dt>
                      <dd className="font-mono tabular-nums">
                        {num(detail.prediction.confidence, 3)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs text-muted-foreground">status</dt>
                      <dd className="font-mono">{detail.prediction.status}</dd>
                    </div>
                    <div className="col-span-2">
                      <dt className="text-xs text-muted-foreground">
                        hash, committed before the horizon it is judged against
                      </dt>
                      <dd className="break-all font-mono text-[11px]">
                        {detail.prediction.prediction_hash}
                      </dd>
                    </div>
                  </dl>
                </Card>
              ) : (
                <Card className="p-4 text-sm text-muted-foreground">
                  {/*
                    An abstention is a first-class outcome, not a missing
                    result. The graph reached VALIDATION, the validator said no,
                    and nothing was committed — which is the boundary in §10
                    doing its job.
                  */}
                  This run committed nothing. The validator rejected the
                  proposal, so the agent abstained — a first-class outcome, not
                  a failure.
                </Card>
              )}
            </>
          ) : (
            <Card className="p-6 text-sm text-muted-foreground">
              Select a run to see its node-by-node trace.
            </Card>
          )}
        </section>
      </div>
    </main>
  )
}
