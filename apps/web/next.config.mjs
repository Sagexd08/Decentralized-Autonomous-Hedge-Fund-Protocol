import fs from "fs"
import path from "path"
import { fileURLToPath } from "url"

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// The monorepo keeps a single .env at the repo root. Next has no `envDir`
// option, so read the NEXT_PUBLIC_* keys out of it ourselves. The file is
// gitignored, so on Vercel it is absent and the platform env vars are used.
function rootPublicEnv() {
  const envPath = path.resolve(__dirname, "..", ".env")
  if (!fs.existsSync(envPath)) return {}

  const out = {}
  for (const line of fs.readFileSync(envPath, "utf8").split(/\r?\n/)) {
    const match = /^\s*(NEXT_PUBLIC_[A-Za-z0-9_]+)\s*=\s*(.*)$/.exec(line)
    if (!match) continue
    if (process.env[match[1]] !== undefined) continue // real env wins
    out[match[1]] = match[2].trim().replace(/^["'](.*)["']$/, "$1")
  }
  return out
}

// Where /api and /ws are proxied to.
//
// This was hardcoded to http://localhost:8000, which is correct in development
// and meaningless in production: on Vercel that address is the serverless
// function's own loopback, so every proxied request from a deployed build goes
// nowhere. Same class of mistake as using NEXT_PUBLIC_API_URL for a
// server-side fetch — "localhost" names a different machine depending on who
// is resolving it.
const API_ORIGIN = (
  process.env.API_PROXY_ORIGIN ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000"
).replace(/\/+$/, "")

/** @type {import('next').NextConfig} */
const nextConfig = {
  env: rootPublicEnv(),
  // Must equal turbopack.root below or Next warns and the two disagree about
  // which directory is the workspace. Both are pinned to this app because the
  // repo root carries a stray package-lock.json that would otherwise be
  // inferred as the root.
  outputFileTracingRoot: __dirname,
  turbopack: {
    // The repo root carries a stray package-lock.json, so pin the workspace
    // root to this app instead of letting Turbopack infer it.
    root: __dirname,
    resolveAlias: {
      // thread-stream resolves its worker with join(__dirname, ...) inside a
      // `new Worker(...)` call. Turbopack cannot follow that statically, so it
      // widens the request into a context module over the whole package and
      // then fails on the README, LICENSE, *.test.ts and .zip fixtures it
      // ships. pino (pulled in by @walletconnect/logger) only touches
      // thread-stream for transports, which this app never configures, so
      // point it at a stub. See stubs/thread-stream.cjs.
      "thread-stream": "./stubs/thread-stream.cjs",
    },
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${API_ORIGIN}/api/:path*`,
      },
      {
        source: "/ws/:path*",
        destination: `${API_ORIGIN}/ws/:path*`,
      },
    ]
  },
}

export default nextConfig
