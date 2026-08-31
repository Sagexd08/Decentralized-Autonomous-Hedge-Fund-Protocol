import type { ReactNode } from "react"
import { ProvenanceNotice } from "@/components/iris/provenance-notice"

/**
 * A server layout, so the §0c notice is in the HTML the server sends —
 * before hydration, without JavaScript, and in the loading and error states.
 * It reports what is actually true — live, mixed or simulated — rather
 * than a hardcoded label. See components/iris/provenance-notice.
 */
export default function ProtocolLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <ProvenanceNotice />
      {children}
    </>
  )
}
