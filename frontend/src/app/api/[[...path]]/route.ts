import { NextRequest } from 'next/server'

const BACKEND_BASE_URL = process.env.API_BASE_URL ?? 'http://localhost:8000'

export const dynamic = 'force-dynamic'

function buildTargetUrl(req: NextRequest, path?: string[]) {
  const incoming = new URL(req.url)
  const suffix = path?.join('/') ?? ''
  const target = new URL(`/api/${suffix}`, BACKEND_BASE_URL)
  target.search = incoming.search
  return target
}

async function proxyRequest(req: NextRequest, path?: string[]) {
  const target = buildTargetUrl(req, path)

  const headers = new Headers(req.headers)
  headers.delete('host')
  headers.delete('connection')
  headers.delete('content-length')

  const init: RequestInit = {
    method: req.method,
    headers,
    redirect: 'manual',
    cache: 'no-store',
  }

  if (req.method !== 'GET' && req.method !== 'HEAD') {
    init.body = await req.arrayBuffer()
  }

  const upstream = await fetch(target, init)
  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: upstream.headers,
  })
}

type RouteParams = { path?: string[] }

export async function GET(req: NextRequest, { params }: { params: RouteParams }) {
  return proxyRequest(req, params.path)
}

export async function POST(req: NextRequest, { params }: { params: RouteParams }) {
  return proxyRequest(req, params.path)
}

export async function PUT(req: NextRequest, { params }: { params: RouteParams }) {
  return proxyRequest(req, params.path)
}

export async function PATCH(req: NextRequest, { params }: { params: RouteParams }) {
  return proxyRequest(req, params.path)
}

export async function DELETE(req: NextRequest, { params }: { params: RouteParams }) {
  return proxyRequest(req, params.path)
}

export async function OPTIONS(req: NextRequest, { params }: { params: RouteParams }) {
  return proxyRequest(req, params.path)
}
