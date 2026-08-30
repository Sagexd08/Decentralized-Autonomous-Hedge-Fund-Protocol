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

/** @type {import('next').NextConfig} */
const nextConfig = {
  env: rootPublicEnv(),
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
        destination: "http://localhost:8000/api/:path*",
      },
      {
        source: "/ws/:path*",
        destination: "http://localhost:8000/ws/:path*",
      },
    ]
  },
}

export default nextConfig
