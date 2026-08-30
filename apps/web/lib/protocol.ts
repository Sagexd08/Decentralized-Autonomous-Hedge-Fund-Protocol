/**
 * The v2 protocol screens — IRIS_BUILD_PROMPT v2.0 section 15, Phases 10-12.
 *
 * Types and fetchers for `/api/protocol/*`, which reads the tables phases 5-8
 * write. Deliberately separate from `lib/api.ts`, which serves the pre-v2
 * dashboard and still has a fixture fallback behind it.
 *
 * `Provenance` is on every response and is not optional. Section 0c requires
 * simulated data to be labelled wherever it surfaces, and a label that stops at
 * the API boundary is not a label — so it is a required field on every type
 * here, which makes rendering a number without it a type error rather than an
 * oversight.
 */

const API_BASE = (process.env.NEXT_PUBLIC_API_URL ?? "").trim().replace(/\/+$/, "")
const WS_BASE = (process.env.NEXT_PUBLIC_WS_URL ??
  (API_BASE ? API_BASE.replace(/^http/i, "ws") : ""))
  .trim()
  .replace(/\/+$/, "")

function url(path: string): string {
  return API_BASE ? `${API_BASE}${path}` : path
}

export function wsUrl(path: string): string {
  if (WS_BASE) return `${WS_BASE}${path}`
  if (typeof window === "undefined") return path
  const scheme = window.location.protocol === "https:" ? "wss:" : "ws:"
  return `${scheme}//${window.location.host}${path}`
}

// ─── provenance ─────────────────────────────────────────────────────────────

export interface Provenance {
  /** Every distinct `data_source` behind the rows in this response. */
  sources: string[]
  /** True only when every contributing row is LIVE. A mixed response is not live. */
  live: boolean
  note: string
}

// ─── Phase 10: Agent Arena ──────────────────────────────────────────────────

export interface ArenaEntry {
  agent_id: string
  name: string
  strategy: string
  status: string
  vault_id: string | null
  /**
   * Null when the agent has no settled record — not 0.
   *
   * Phase 6 returns None for an untested agent so a default cannot let it
   * outrank one with a proven bad record. The type keeps that distinction
   * alive: `iris_score ?? 0` anywhere in a component would throw it away.
   */
  iris_score: number | null
  dimensions: Record<string, number | string> | null
  weights: Record<string, number> | null
  allocation_weight: number
  allocation_step: number | null
  settled_count: number
  accuracy: number | null
  mean_score: number | null
  stake: number
  model: { family: string | null; version: number | null; hash: string | null }
  last_settled: string | null
}

export interface Arena {
  ranked: ArenaEntry[]
  /** Untested agents. Unranked, not last — a different claim from "measured and bad". */
  unranked: ArenaEntry[]
  totals: { agents: number; scored: number; allocated: number }
  provenance: Provenance
}

// ─── Phase 11: AI Observatory ───────────────────────────────────────────────

export interface RunSummary {
  id: string
  agent_id: string
  agent_name: string | null
  strategy: string | null
  status: string
  started_at: string
  finished_at: string | null
  latency_ms: number | null
  error: string | null
  prediction_id: string | null
  nodes: number
}

export interface Checkpoint {
  seq: number
  node: string
  latency_ms: number | null
  input_hash: string
  output_hash: string
  state: Record<string, unknown>
  created_at: string
}

export interface RunDetail {
  run: RunSummary
  checkpoints: Checkpoint[]
  /**
   * Each node's `input_hash` equals the previous node's `output_hash`.
   * Computed server-side from the rows, not assumed — a broken chain would
   * make this screen a reconstruction rather than a recording.
   */
  chain_intact: boolean
  prediction: LedgerEntry | null
  provenance: Provenance
}

// ─── Phase 12: Prediction Ledger ────────────────────────────────────────────

export interface LedgerEntry {
  id: string
  agent_id: string
  agent_name?: string | null
  asset: string
  direction: "BUY" | "SELL" | "HOLD"
  expected_return: string | number
  confidence: string | number
  horizon_seconds?: number
  prediction_hash: string
  status: "PREDICTED" | "COMMITTED" | "WAITING_FOR_OUTCOME" | "SETTLED" | "EVALUATED"
  predicted_at?: string
  committed_at: string | null
  horizon_end: string
  solana_sig?: string | null
  actual_return: string | number | null
  error: string | number | null
  direction_correct: boolean | null
  evaluation_score: string | number | null
  settled_at?: string | null
  data_source: string | null
  committed_before_horizon?: boolean
}

export interface Ledger {
  predictions: LedgerEntry[]
  counts: {
    committed: number
    /**
     * Due, but with no price evidence. Not "pending" — this is the protocol
     * declining to score something it cannot measure, and it counts toward
     * nothing.
     */
    waiting: number
    settled: number
    evaluated: number
    total: number
  }
  summary: {
    scored: number
    correct: number
    accuracy: number | null
    mean_score: number | null
  }
  provenance: Provenance
}

// ─── risk ───────────────────────────────────────────────────────────────────

export interface RiskEvent {
  id: string
  agent_id: string
  kind: string
  severity: "INFO" | "WARN" | "CRITICAL"
  measured_bps: number | null
  limit_bps: number | null
  detail: Record<string, unknown> | null
  data_source: string
  created_at: string
}

export interface SlashEvent {
  id: string
  agent_id: string
  risk_event_id: string | null
  drawdown_bps: number
  slash_bps: number
  amount_slashed: string | number | null
  data_source: string
  created_at: string
}

export interface RiskFeed {
  risk_events: RiskEvent[]
  slash_events: SlashEvent[]
  provenance: Provenance
}

// ─── summary ────────────────────────────────────────────────────────────────

export interface ProtocolSummary {
  totals: {
    active_agents: number
    frozen_agents: number
    slashed_agents: number
    predictions: number
    settled: number
    waiting: number
    runs: number
    allocation_step: number
    events: number
  }
  provenance: Provenance
}

// ─── events ─────────────────────────────────────────────────────────────────

export interface ProtocolEvent {
  seq: number
  kind: string
  /** The table this came from. With `source_id`, lets a client verify the feed. */
  source_table: string
  source_id: string
  agent_id: string | null
  data_source: string
  payload: Record<string, unknown>
  created_at: string
}

// ─── fetching ───────────────────────────────────────────────────────────────

async function get<T>(path: string): Promise<T> {
  const res = await fetch(url(path), { cache: "no-store" })
  if (!res.ok) {
    // Thrown, not swallowed into an empty default. A screen that renders zeros
    // because a request failed is indistinguishable from one where the
    // protocol genuinely has not done anything yet.
    throw new Error(`${path} → ${res.status} ${res.statusText}`)
  }
  return (await res.json()) as T
}

export const fetchArena = () => get<Arena>("/api/protocol/arena")
export const fetchSummary = () => get<ProtocolSummary>("/api/protocol/summary")
export const fetchRiskFeed = () => get<RiskFeed>("/api/protocol/risk")

export const fetchRuns = (agent?: string, limit = 25) =>
  get<{ runs: RunSummary[]; count: number; provenance: Provenance }>(
    `/api/protocol/observatory/runs?limit=${limit}${agent ? `&agent=${agent}` : ""}`,
  )

export const fetchRun = (runId: string) =>
  get<RunDetail>(`/api/protocol/observatory/runs/${runId}`)

export const fetchLedger = (opts: { agent?: string; status?: string; limit?: number } = {}) => {
  const params = new URLSearchParams()
  if (opts.agent) params.set("agent", opts.agent)
  if (opts.status) params.set("status", opts.status)
  params.set("limit", String(opts.limit ?? 50))
  return get<Ledger>(`/api/protocol/ledger?${params}`)
}

// ─── formatting ─────────────────────────────────────────────────────────────

export function pct(value: number | string | null | undefined, digits = 2): string {
  if (value === null || value === undefined) return "—"
  const n = typeof value === "string" ? Number.parseFloat(value) : value
  return Number.isFinite(n) ? `${(n * 100).toFixed(digits)}%` : "—"
}

export function num(value: number | string | null | undefined, digits = 2): string {
  if (value === null || value === undefined) return "—"
  const n = typeof value === "string" ? Number.parseFloat(value) : value
  return Number.isFinite(n) ? n.toFixed(digits) : "—"
}

export function bps(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : `${(value / 100).toFixed(2)}%`
}

export function shortHash(hash: string | null | undefined, size = 8): string {
  if (!hash) return "—"
  return hash.length <= size * 2 ? hash : `${hash.slice(0, size)}…${hash.slice(-4)}`
}

export function ago(iso: string | null | undefined): string {
  if (!iso) return "—"
  const then = new Date(iso).getTime()
  if (!Number.isFinite(then)) return "—"
  const seconds = Math.max(0, Math.floor((Date.now() - then) / 1000))
  if (seconds < 60) return `${seconds}s ago`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
  return `${Math.floor(seconds / 86400)}d ago`
}
