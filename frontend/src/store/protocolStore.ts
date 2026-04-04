import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface DelegationRecord {
  agentId: string
  agentName: string
  agentRisk: string
  ethAmount: number
  txHash: string
  timestamp: number
  walletAddress: string
}

export interface TradeRecord {
  id: string
  timestamp: number
  token: string
  type: 'BUY' | 'SELL'
  ethAmount: number
  tokenAmount: number
  price: number
  pnlDelta: number
  decision: string
  confidence: number
}

export interface TradingSession {
  id: string
  agentId: string
  agentName: string
  agentRisk: string
  ethDeposited: number
  startTime: number
  endTime?: number
  finalPnlEth?: number
  finalPnlPct?: number
  trades: number
  status: 'active' | 'completed'
  // Rich trading stats
  tradeRecords: TradeRecord[]
  maxDrawdownEth?: number
  peakPnlEth?: number
  winTrades?: number
  lossTrades?: number
  avgWinEth?: number
  avgLossEth?: number
  sharpeRatio?: number
  tokensTraded?: string[]
}

interface ProtocolState {
  walletAddress: string | null
  isConnected: boolean
  delegations: Record<string, DelegationRecord>
  sessions: TradingSession[]
  activeSessionId: string | null

  connect: (address: string) => void
  disconnect: () => void
  addDelegation: (record: DelegationRecord) => void
  removeDelegation: (agentId: string) => void
  startSession: (agentId: string, agentName: string, agentRisk: string, ethAmount: number) => string
  endSession: (sessionId: string, finalPnlEth: number, trades: number, tradeRecords?: TradeRecord[]) => void
  addTradeRecord: (sessionId: string, trade: TradeRecord) => void
  incrementSessionTrades: (agentId: string) => void
}

export const useProtocolStore = create<ProtocolState>()(
  persist(
    (set, get) => ({
      walletAddress: null,
      isConnected: false,
      delegations: {},
      sessions: [],
      activeSessionId: null,

      connect: (address) => set({ walletAddress: address, isConnected: true }),
      disconnect: () => set({ walletAddress: null, isConnected: false }),

      addDelegation: (record) => set(state => ({
        delegations: { ...state.delegations, [record.agentId]: record },
      })),

      removeDelegation: (agentId) => set(state => {
        const d = { ...state.delegations }
        delete d[agentId]
        return { delegations: d }
      }),

      startSession: (agentId, agentName, agentRisk, ethAmount) => {
        const id = `session-${Date.now()}-${agentId}`
        const session: TradingSession = {
          id, agentId, agentName, agentRisk, ethDeposited: ethAmount,
          startTime: Date.now(), trades: 0, status: 'active',
          tradeRecords: [], tokensTraded: [],
        }
        set(state => ({
          sessions: [...state.sessions, session],
          activeSessionId: id,
        }))
        return id
      },

      endSession: (sessionId, finalPnlEth, trades, tradeRecords) => {
        const state = get()
        const session = state.sessions.find(s => s.id === sessionId)
        const records = tradeRecords ?? session?.tradeRecords ?? []

        // Compute rich stats
        const wins = records.filter(t => t.pnlDelta > 0)
        const losses = records.filter(t => t.pnlDelta < 0)
        const avgWin = wins.length ? wins.reduce((s, t) => s + t.pnlDelta, 0) / wins.length : 0
        const avgLoss = losses.length ? losses.reduce((s, t) => s + t.pnlDelta, 0) / losses.length : 0
        const pnlDeltas = records.map(t => t.pnlDelta)
        const mean = pnlDeltas.length ? pnlDeltas.reduce((a, b) => a + b, 0) / pnlDeltas.length : 0
        const std = pnlDeltas.length > 1
          ? Math.sqrt(pnlDeltas.reduce((s, v) => s + (v - mean) ** 2, 0) / pnlDeltas.length)
          : 0.001
        const sharpe = std > 0 ? (mean / std) * Math.sqrt(252) : 0
        const deposited = session?.ethDeposited ?? 1
        const finalPnlPct = (finalPnlEth / deposited) * 100

        // Peak and max drawdown
        let peak = 0, maxDD = 0, running = 0
        for (const t of records) {
          running += t.pnlDelta
          if (running > peak) peak = running
          const dd = peak - running
          if (dd > maxDD) maxDD = dd
        }

        const tokensTraded = [...new Set(records.map(t => t.token))]

        set(state => ({
          sessions: state.sessions.map(s =>
            s.id === sessionId ? {
              ...s,
              endTime: Date.now(),
              finalPnlEth,
              finalPnlPct,
              trades,
              status: 'completed' as const,
              tradeRecords: records,
              winTrades: wins.length,
              lossTrades: losses.length,
              avgWinEth: avgWin,
              avgLossEth: avgLoss,
              sharpeRatio: parseFloat(sharpe.toFixed(3)),
              maxDrawdownEth: maxDD,
              peakPnlEth: peak,
              tokensTraded,
            } : s
          ),
          activeSessionId: state.activeSessionId === sessionId ? null : state.activeSessionId,
        }))
      },

      addTradeRecord: (sessionId, trade) => set(state => ({
        sessions: state.sessions.map(s =>
          s.id === sessionId
            ? { ...s, tradeRecords: [...(s.tradeRecords ?? []), trade].slice(-500) }
            : s
        ),
      })),

      incrementSessionTrades: (agentId) => set(state => ({
        sessions: state.sessions.map(s =>
          s.agentId === agentId && s.status === 'active'
            ? { ...s, trades: s.trades + 1 }
            : s
        ),
      })),
    }),
    {
      name: 'dacap-protocol-store',
      version: 3,
      migrate: (persistedState: any, version: number) => {
        // Migrate from any previous version — preserve sessions and delegations
        if (version < 3) {
          return {
            ...persistedState,
            sessions: (persistedState.sessions ?? []).map((s: any) => ({
              tradeRecords: [],
              tokensTraded: [],
              ...s,
            })),
          }
        }
        return persistedState
      },
      partialize: (state) => ({
        walletAddress: state.walletAddress,
        isConnected: state.isConnected,
        delegations: state.delegations,
        sessions: state.sessions,
        activeSessionId: state.activeSessionId,
      }),
    }
  )
)
