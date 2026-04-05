const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
const WS_BASE = API_BASE.replace(/^http/, "ws")

export const API_URL = API_BASE
export const WS_URL = WS_BASE

// ─── types ──────────────────────────────────────────────────────────────────

export interface Agent {
  id: string
  name: string
  strategy: string
  risk: string
  sharpe: number
  drawdown: number
  allocation: number
  pnl: number
  volatility: number
  stake: number
  status: string
  score: number
  address: string | null
  description: string
  model?: string
  trust_score?: number
  confidence_score?: number
  anomaly_score?: number
}

export interface PriceTick {
  type?: string
  symbol?: string
  price?: number
  change_pct?: number
  timestamp?: number
  // batch format
  prices?: Record<string, { price: number; change_pct: number; initial: number }>
}

export interface TradeEvent {
  agent: string
  token: string
  amountIn: string
  amountOut: string
  timestamp: number
  type: string
}

export interface PortfolioResponse {
  token_balances: Record<string, string>
  pnl_wei: string
  trading_active: boolean
}

// ─── REST helpers ────────────────────────────────────────────────────────────

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" })
  if (!res.ok) throw new Error(`API ${path} → ${res.status}`)
  return res.json() as Promise<T>
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: body !== undefined ? { "Content-Type": "application/json" } : {},
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`POST ${path} → ${res.status}`)
  return res.json() as Promise<T>
}

// ─── Agents ──────────────────────────────────────────────────────────────────

export const agentsApi = {
  list: (risk?: string) =>
    get<Agent[]>(`/api/agents/${risk ? `?risk=${encodeURIComponent(risk)}` : ""}`),
  get: (id: string) => get<Agent>(`/api/agents/${id}`),
  startTrading: (id: string) => post<{ status: string }>(`/api/agents/${id}/start-trading`),
  stopTrading: (id: string) => post<{ status: string }>(`/api/agents/${id}/stop-trading`),
  portfolio: (id: string) => get<PortfolioResponse>(`/api/agents/${id}/portfolio`),
}

// ─── Prices ──────────────────────────────────────────────────────────────────

export const pricesApi = {
  current: () => get<Record<string, { price: number; change_pct: number; initial: number }>>("/api/prices/current"),
}

// ─── Governance ──────────────────────────────────────────────────────────────

export const governanceApi = {
  proposals: () => get<unknown[]>("/api/governance/proposals"),
  vote: (id: string, support: boolean) =>
    post(`/api/governance/proposals/${id}/vote`, { support }),
}

// ─── Analytics ───────────────────────────────────────────────────────────────

export const analyticsApi = {
  monteCarlo: (params: unknown) => post("/api/analytics/monte-carlo", params),
}

// ─── Contract addresses ───────────────────────────────────────────────────────

export interface ContractAddresses {
  stellar: {
    agent_registry: string
    allocation_engine: string
    capital_vault: string
    slashing_module: string
    network: string
    rpc_url: string
  }
  solana: {
    agent_registry: string
    allocation_engine: string
    capital_vault: string
    slashing_module: string
    wallet: string
    network: string
    rpc_url: string
  }
}

export const contractsApi = {
  addresses: () => get<ContractAddresses>("/api/contracts/addresses"),
}
