import { AlertTriangle, FlaskConical, Radio, ShieldQuestion } from "lucide-react"

/**
 * The §0c notice, rendered on the server, saying what is actually true.
 *
 * This replaced a version that hardcoded "Simulated data". That was correct
 * for every phase up to 12 and became a lie the moment the protocol started
 * reading a real exchange — and a stale honesty label is worse than none,
 * because it is the thing a reader trusts to tell them when to stop trusting.
 *
 * A deliberate *server* component with no "use client". The client-side
 * `ProvenanceBanner` reports the sources behind one particular response, which
 * is the more precise statement — but it only appears once a fetch resolves
 * and the page hydrates, so it is absent from the initial HTML, absent with
 * JavaScript disabled, and absent while the page is loading or has errored.
 * This one is in the markup the server sends, so it is there before anything
 * else is.
 *
 * The state it reports is a *pair*, not a flag, because the protocol has two
 * independent provenances and either one can be synthetic:
 *
 *   * the **prices** an agent observed and was settled against, and
 *   * the **data the model was fitted on**.
 *
 * Live prices through a model trained on a synthetic tape is the worst of the
 * four combinations and the one that looks best from the outside: real
 * provenance, honest hashes, and predictions overstated by a factor of sixty.
 * It gets its own wording rather than being rounded to "live".
 */

export const dynamic = "force-dynamic"

type Feed = {
  healthy: boolean
  reasons: string[]
  lag_seconds: number | null
  sources: { source: string; provider: string | null; stale: boolean }[]
}

type Training = {
  is_real_market_data: boolean
  source: string | null
  provider: string | null
  asset: string | null
  return_sd_bps?: number
}

/**
 * The provenance of the rows actually rendered below the notice.
 *
 * Distinct from the feed's and the training set's, and the distinction is the
 * whole point: a live feed does not make a settled outcome from last week
 * live. The banner claimed "Real market data" over an Arena whose own endpoint
 * was simultaneously reporting `sources: ["LIVE", "SIMULATION"]` and "some
 * rows below were measured against simulated prices" — a live label sitting on
 * top of the API's own disclaimer, which is exactly the §0c failure.
 */
type Records = {
  provenance: { sources: string[]; live: boolean; note: string }
}

/**
 * The API address *from the server's point of view*.
 *
 * `NEXT_PUBLIC_API_URL` is the browser's view, and in local development it is
 * `http://localhost:8000` — which, evaluated inside the web container, means
 * the web container. Falling back to it server-side made every fetch here fail
 * and rendered "provenance unconfirmed" over a perfectly healthy stack. So a
 * localhost value is explicitly not trusted here. A real deployment either
 * sets INTERNAL_API_URL, or NEXT_PUBLIC_API_URL names a public host and is
 * correct from both sides.
 */
function apiBase(): string {
  const internal = process.env.INTERNAL_API_URL?.trim()
  if (internal) return internal.replace(/\/+$/, "")

  const publicUrl = process.env.NEXT_PUBLIC_API_URL?.trim() ?? ""
  if (publicUrl && !/^https?:\/\/(localhost|127\.0\.0\.1|\[::1\])/i.test(publicUrl)) {
    return publicUrl.replace(/\/+$/, "")
  }
  return "http://api:8000"
}

/**
 * Two attempts, because "slow" and "down" are different answers.
 *
 * The first request after a restart races the dev server's cold compile for
 * the event loop, and a single short timeout turned that into
 * "provenance unconfirmed" over a completely healthy stack. That fails in the
 * safe direction — it never claims live when it does not know — but it is
 * still a false negative on the one banner a reader is meant to trust.
 *
 * A retry with a longer budget separates the two. If both attempts fail the
 * API really is unreachable and the notice should say so.
 */
async function read<T>(path: string): Promise<T | null> {
  for (const timeout of [6000, 12000]) {
    try {
      // `no-store`: a cached provenance label is a label that can describe a
      // state the system has since left.
      const res = await fetch(`${apiBase()}${path}`, {
        cache: "no-store",
        signal: AbortSignal.timeout(timeout),
      })
      if (!res.ok) return null
      return (await res.json()) as T
    } catch {
      // fall through to the next attempt
    }
  }
  return null
}

const STYLES = {
  live: {
    icon: Radio,
    className: "border-emerald-500/30 bg-emerald-500/10 text-emerald-200",
  },
  mixed: {
    icon: AlertTriangle,
    className: "border-amber-500/30 bg-amber-500/10 text-amber-200",
  },
  simulated: {
    icon: FlaskConical,
    className: "border-amber-500/30 bg-amber-500/10 text-amber-200",
  },
  unknown: {
    icon: ShieldQuestion,
    className: "border-zinc-500/30 bg-zinc-500/10 text-zinc-200",
  },
} as const

export async function ProvenanceNotice() {
  const [feed, training, records] = await Promise.all([
    read<Feed>("/api/market/health?asset=BTC"),
    read<Training>("/api/market/training"),
    read<Records>("/api/protocol/summary"),
  ])

  const { kind, title, body } = describe(feed, training, records)
  const style = STYLES[kind]
  const Icon = style.icon

  return (
    <div
      role="note"
      data-provenance={kind}
      className={`flex items-start gap-3 border-b px-4 py-2.5 ${style.className}`}
    >
      <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <p className="text-xs leading-relaxed">
        <span className="font-medium">{title}</span> {body}
      </p>
    </div>
  )
}

function describe(
  feed: Feed | null,
  training: Training | null,
  records: Records | null,
): { kind: keyof typeof STYLES; title: string; body: string } {
  // Nothing answered. This must never resolve to "live" — an unreachable API
  // is precisely when a page is most likely to be showing something stale, and
  // a confident label over unknown data is the failure §0c exists to prevent.
  if (feed === null || training === null) {
    return {
      kind: "unknown",
      title: "Provenance unconfirmed.",
      body:
        "The protocol API did not answer, so this page cannot say whether the " +
        "numbers below came from a real market or a simulation. Treat them as " +
        "unverified.",
    }
  }

  const liveRows = feed.sources.filter((s) => s.source === "LIVE" && !s.stale)
  const venues = [...new Set(liveRows.map((s) => s.provider).filter(Boolean))]
  const pricesLive = feed.healthy && liveRows.length > 0
  const modelsReal = training.is_real_market_data

  // Deliberately pessimistic when the rows cannot be checked. A failed fetch
  // is not evidence that what is rendered below is live.
  const recordsLive = records?.provenance?.live === true
  const recordSources = records?.provenance?.sources ?? []

  if (pricesLive && modelsReal && recordsLive) {
    return {
      kind: "live",
      title: "Real market data.",
      body:
        `Prices come from ${venues.join(", ") || "a public exchange"} and the ` +
        `models are fitted on ${training.asset ?? "the same"} history from the ` +
        `same venue. Predictions are committed before their horizon and settled ` +
        `against the recorded tape. No live capital is deployed — allocations ` +
        `are weights, not transfers.`,
    }
  }

  if (pricesLive && modelsReal) {
    // The feed and the models are real; some of what is on screen is not.
    const mixed = recordSources.length
      ? ` The records below draw on ${recordSources.join(" and ")}.`
      : " The provenance of the records below could not be confirmed."
    return {
      kind: "mixed",
      title: "Live feed, mixed records.",
      body:
        `Prices come from ${venues.join(", ") || "a public exchange"} and the ` +
        `models are fitted on real history, but not every outcome below was ` +
        `measured against it — older ones were settled against a simulated ` +
        `tape and are kept, not deleted.${mixed} Read the per-row labels rather ` +
        `than this banner for any individual number.`,
    }
  }

  if (pricesLive && !modelsReal) {
    return {
      kind: "mixed",
      title: "Live prices, synthetic models.",
      body:
        "The price feed is real, but the models behind these predictions were " +
        "fitted on a synthetic tape whose returns are far larger than this " +
        "market's. Their predicted magnitudes are systematically overstated. " +
        "Directions and scores below should not be read as live performance.",
    }
  }

  const why = feed.reasons[0]
  return {
    kind: "simulated",
    title: "Simulated data.",
    body:
      `Prices are not coming from an exchange right now${why ? ` — ${why}` : ""}. ` +
      `The tape below is a seeded Ornstein-Uhlenbeck series and the models are ` +
      `trained on a synthetic one. Every score, allocation and slash is computed ` +
      `from that. Nothing here is evidence of live performance.`,
  }
}
