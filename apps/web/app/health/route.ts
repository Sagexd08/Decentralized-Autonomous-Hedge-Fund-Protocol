import { NextResponse } from "next/server"

// Liveness probe for the web container. Static so it answers before any
// backend or database is reachable — `docker compose` gates the web service on
// this alone, and on the API's own /health separately.
export const dynamic = "force-static"

export function GET() {
  return NextResponse.json({ status: "ok", service: "iris-web" })
}
