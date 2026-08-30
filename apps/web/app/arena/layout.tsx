import type { ReactNode } from "react"
import { SimulationNotice } from "@/components/iris/simulation-notice"

/**
 * A server layout, so the §0c notice is in the HTML the server sends —
 * before hydration, without JavaScript, and in the loading and error states.
 * See components/iris/simulation-notice.
 */
export default function ProtocolLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <SimulationNotice />
      {children}
    </>
  )
}
