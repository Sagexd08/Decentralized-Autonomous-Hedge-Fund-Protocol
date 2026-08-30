"use client"

import { AlertTriangle, FlaskConical, Radio, TestTube2 } from "lucide-react"
import type { Provenance } from "@/lib/protocol"
import { cn } from "@/lib/utils"

/**
 * The §0c label, on screen.
 *
 * Section 0c: never fake production readiness — label simulated, testnet and
 * historical data as such in the UI. Everything in this system is currently
 * derived from a simulated price tape and models trained on a synthetic
 * series, and until this component existed that fact lived only in the
 * database and the API response.
 *
 * Deliberately not dismissible and not subtle. A reader who sees a Sharpe
 * ratio and an IRIS Score should not have to go looking for whether the
 * numbers came from a real market — that is precisely the confusion the rule
 * exists to prevent. It renders on every protocol screen, above the data, not
 * in a footer.
 */

const STYLES = {
  SIMULATION: {
    icon: FlaskConical,
    label: "Simulated",
    className: "border-amber-500/40 bg-amber-500/10 text-amber-200",
    dot: "bg-amber-400",
  },
  TESTNET: {
    icon: TestTube2,
    label: "Testnet",
    className: "border-sky-500/40 bg-sky-500/10 text-sky-200",
    dot: "bg-sky-400",
  },
  LIVE: {
    icon: Radio,
    label: "Live",
    className: "border-emerald-500/40 bg-emerald-500/10 text-emerald-200",
    dot: "bg-emerald-400",
  },
  FIXTURE: {
    icon: AlertTriangle,
    label: "Illustrative",
    className: "border-red-500/40 bg-red-500/10 text-red-200",
    dot: "bg-red-400",
  },
} as const

type Kind = keyof typeof STYLES

function kindOf(sources: string[]): Kind {
  // The weakest source wins. A response mixing one live row into forty
  // simulated ones is not live, and reporting the strongest would let a single
  // real number launder a screen full of synthetic ones.
  if (sources.includes("FIXTURE")) return "FIXTURE"
  if (sources.includes("SIMULATION") || sources.length === 0) return "SIMULATION"
  if (sources.includes("TESTNET")) return "TESTNET"
  return "LIVE"
}

export function ProvenanceBadge({ sources }: { sources: string[] }) {
  const kind = kindOf(sources)
  const style = STYLES[kind]
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium",
        style.className,
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", style.dot)} aria-hidden />
      {style.label}
    </span>
  )
}

export function ProvenanceBanner({
  provenance,
  className,
}: {
  provenance: Provenance
  className?: string
}) {
  const kind = kindOf(provenance.sources)
  const style = STYLES[kind]
  const Icon = style.icon

  return (
    <div
      role="note"
      className={cn(
        "flex items-start gap-3 rounded-lg border px-4 py-3 text-sm",
        style.className,
        className,
      )}
    >
      <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <div className="space-y-1">
        <p className="font-medium leading-none">
          {kind === "LIVE"
            ? "Live data"
            : kind === "FIXTURE"
              ? "Illustrative data — not produced by this protocol"
              : `${style.label} data`}
        </p>
        <p className="text-xs leading-relaxed opacity-80">{provenance.note}</p>
        {provenance.sources.length > 1 && (
          <p className="text-xs opacity-70">
            Mixed sources: {provenance.sources.join(", ")}. Treated as the weakest.
          </p>
        )}
      </div>
    </div>
  )
}

/**
 * The label when no data has loaded yet.
 *
 * The provenance of this system is not a property of a successful fetch — it
 * is simulated whether or not the request came back. Rendering the banner only
 * once data arrives left the label out of the server-rendered HTML entirely,
 * and out of the loading and error states, which is exactly where a reader
 * forms their first impression of what they are looking at.
 *
 * So the page shell renders this unconditionally and swaps in the real
 * provenance once it knows the actual sources.
 */
export const ASSUMED_SIMULATION: Provenance = {
  sources: ["SIMULATION"],
  live: false,
  note:
    "Simulated market data and synthetically trained models. " +
    "Not evidence of live performance.",
}
