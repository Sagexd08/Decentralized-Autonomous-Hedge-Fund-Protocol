const API_BASE = (process.env.NEXT_PUBLIC_API_URL ?? "").trim().replace(/\/+$/, "")
const WS_BASE = (process.env.NEXT_PUBLIC_WS_URL ?? (API_BASE ? API_BASE.replace(/^http/i, "ws") : ""))
  .trim()
  .replace(/\/+$/, "")

export const API_URL = API_BASE || "same-origin"
export const WS_URL = WS_BASE || "same-origin"

function resolveApiUrl(path: string): string {
  return API_BASE ? `${API_BASE}${path}` : path
}

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

// ─── News ────────────────────────────────────────────────────────────────────

export interface NewsItem {
  title: string
  published: string
  coins: string[]
  votes: unknown[]
  source: string
  provider: string
  sentiment_hint: "bullish" | "bearish" | "neutral"
}

export interface NewsSignal {
  asset: string
  sentiment: number   // -1 to 1
  event: string
  confidence: number  // 0 to 1
  source: string
  provider: string
  title: string
}

export interface NewsResponse {
  items: NewsItem[]
  count: number
  providers: Record<string, unknown>
}

export interface SignalsResponse {
  signals: NewsSignal[]
  count: number
}

export interface PortfolioResponse {
  token_balances: Record<string, string>
  pnl_wei: string
  trading_active: boolean
}

// ─── REST helpers ────────────────────────────────────────────────────────────

async function get<T>(path: string): Promise<T> {
  const res = await fetch(resolveApiUrl(path), { cache: "no-store" })
  if (!res.ok) throw new Error(`API ${path} → ${res.status}`)
  return res.json() as Promise<T>
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(resolveApiUrl(path), {
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
  register: (data: unknown) => post("/api/agents/register", data),
  stake: (data: { agent_id: string; amount: number; address: string }) =>
    post("/api/agents/stake", data),
  chainActive: () => get("/api/agents/chain/active"),
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
  createProposal: (data: unknown) => post("/api/governance/proposals", data),
  vote: (id: string, voter_address: string, support: boolean) =>
    post(`/api/governance/vote`, { proposal_id: id, voter_address, support }),
  params: () => get("/api/governance/params"),
  stats: () => get("/api/governance/stats"),
}

// ─── Analytics ───────────────────────────────────────────────────────────────

export const analyticsApi = {
  monteCarlo: (S0 = 100000, mu = 0.15, sigma = 0.20, T = 30, n_paths = 200) =>
    get(`/api/analytics/monte-carlo?S0=${S0}&mu=${mu}&sigma=${sigma}&T=${T}&n_paths=${n_paths}`),
  rollingVolatility: (window = 30) =>
    get(`/api/analytics/rolling-volatility?window=${window}`),
  regime: () => get("/api/analytics/regime"),
  allocationWeights: (eta?: number, steps = 50) =>
    get(`/api/analytics/allocation-weights?steps=${steps}${eta !== undefined ? `&eta=${eta}` : ""}`),
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
  list: () => get<unknown[]>("/api/contracts/"),
}

// ─── Trading ─────────────────────────────────────────────────────────────────

export const tradingApi = {
  status: () => get("/api/trading/status"),
  chainHealth: () => get("/health/chains"),
}

// ─── Pools ───────────────────────────────────────────────────────────────────

export interface DepositRequest {
  pool_id: string
  amount: number
  investor_address: string
}

export const poolsApi = {
  list: () => get<unknown[]>("/api/pools/"),
  get: (id: string) => get(`/api/pools/${id}`),
  deposit: (data: DepositRequest) => post("/api/pools/deposit", data),
}

// ─── Intelligence ─────────────────────────────────────────────────────────────

export const intelligenceApi = {
  loop: () => get("/api/intelligence/loop"),
  demo: () => get("/api/intelligence/demo"),
  governanceSuggestions: () => get("/api/intelligence/governance-suggestions"),
}

// ─── News ─────────────────────────────────────────────────────────────────────

export const newsApi = {
  crypto: (limit = 20) => get<NewsResponse>(`/api/news/crypto?limit=${limit}`),
  signals: (limit = 10) => get<SignalsResponse>(`/api/news/signals?limit=${limit}`),
}
