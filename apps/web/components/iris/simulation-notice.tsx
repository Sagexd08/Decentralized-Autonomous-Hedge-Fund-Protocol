import { FlaskConical } from "lucide-react"

/**
 * The §0c notice, rendered on the server.
 *
 * A deliberate *server* component with no "use client" and no data dependency.
 * The client-side `ProvenanceBanner` reports the actual sources behind a
 * particular response, which is the more precise statement — but it only
 * appears once a fetch resolves and the page hydrates, so it is absent from the
 * initial HTML, absent with JavaScript disabled, and absent while the page is
 * loading or has errored.
 *
 * Section 0c says label simulated data *in the UI*. A label that requires a
 * successful round trip to appear is not a label on the system; it is a label
 * on the happy path. This one is in the markup the server sends, so it is there
 * before anything else is.
 *
 * It states the standing fact — every number in this protocol currently derives
 * from a simulated price tape and models trained on a synthetic series. The
 * per-response banner refines it.
 */
export function SimulationNotice() {
  return (
    <div
      role="note"
      data-provenance="SIMULATION"
      className="flex items-start gap-3 border-b border-amber-500/30 bg-amber-500/10 px-4 py-2.5 text-amber-200"
    >
      <FlaskConical className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <p className="text-xs leading-relaxed">
        <span className="font-medium">Simulated data.</span>{" "}
        Prices come from a seeded Ornstein–Uhlenbeck tape, not an exchange, and
        the models are trained on a synthetic series. Every score, allocation
        and slash below is computed from that. Nothing here is evidence of live
        performance, and no live capital is involved.
      </p>
    </div>
  )
}
