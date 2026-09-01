"use client"

/**
 * The last-resort error boundary.
 *
 * A global error replaces the root layout entirely — it renders its own
 * `<html>` and `<body>` — which is exactly why this file has to exist. Without
 * it Next generates a default one, and generating it drags the root layout's
 * client providers into a render where React's dispatcher is not set:
 *
 *     Error occurred prerendering page "/_global-error"
 *     TypeError: Cannot read properties of null (reading 'useContext')
 *
 * That failed the production build outright. `next dev` never prerenders, so
 * the error appears for the first time in a deployment — the same shape as the
 * missing Suspense boundary on /observatory.
 *
 * The wording matters as much as the existence. This screen renders when the
 * app has already failed, which is the moment it is most likely to be showing
 * something stale or nothing at all. Section 0c's rule applies with more force
 * here, not less: it must not imply that anything below it is trustworthy, and
 * it must not carry the live-data label, because at this point nothing has
 * confirmed that the feed is live.
 */

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <html lang="en" className="dark">
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#09090b",
          color: "#e4e4e7",
          fontFamily:
            "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif",
          padding: "2rem",
        }}
      >
        <main style={{ maxWidth: "34rem" }}>
          <p
            role="note"
            data-provenance="unknown"
            style={{
              border: "1px solid rgba(113,113,122,0.35)",
              background: "rgba(113,113,122,0.12)",
              color: "#d4d4d8",
              borderRadius: "0.5rem",
              padding: "0.625rem 0.875rem",
              fontSize: "0.75rem",
              lineHeight: 1.6,
              marginBottom: "1.5rem",
            }}
          >
            <strong style={{ fontWeight: 600 }}>Provenance unconfirmed.</strong>{" "}
            The protocol screens could not load, so nothing here has been
            checked against the database. Treat any number you may have seen
            before this as unverified.
          </p>

          <h1 style={{ fontSize: "1.375rem", fontWeight: 600, margin: "0 0 0.75rem" }}>
            Something broke.
          </h1>
          <p style={{ fontSize: "0.875rem", lineHeight: 1.7, color: "#a1a1aa", margin: 0 }}>
            This is the application failing, not the protocol reporting a
            result. Agent runs, settlements and scores continue in the API
            regardless of whether this page renders — nothing here is lost by
            reloading.
          </p>

          {error?.digest && (
            <p
              style={{
                fontSize: "0.6875rem",
                color: "#71717a",
                fontFamily: "ui-monospace, SFMono-Regular, monospace",
                marginTop: "1rem",
              }}
            >
              digest {error.digest}
            </p>
          )}

          <button
            type="button"
            onClick={reset}
            style={{
              marginTop: "1.75rem",
              padding: "0.5rem 1rem",
              borderRadius: "0.5rem",
              border: "1px solid rgba(228,228,231,0.25)",
              background: "transparent",
              color: "#e4e4e7",
              fontSize: "0.8125rem",
              cursor: "pointer",
            }}
          >
            Try again
          </button>
        </main>
      </body>
    </html>
  )
}
