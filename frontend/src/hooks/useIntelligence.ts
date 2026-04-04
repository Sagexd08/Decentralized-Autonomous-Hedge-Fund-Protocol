import { useQuery } from '@tanstack/react-query'
import { api } from '../utils/api'

export interface IntelligenceStage {
  key: string
  label: string
  status: 'complete' | 'active' | 'pending'
}

export interface IntelligentAgent {
  id: string
  name: string
  strategy: string
  model: string
  risk: string
  regime_context: string
  capital_allocated_pct: number
  historical_return_pct: number
  sharpe_ratio: number
  drawdown_pct: number
  confidence_score: number
  trust_score: number
  var_95_pct: number
  anomaly_score: number
  stake_locked: number
  decision: 'BUY' | 'SELL' | 'HOLD'
  decision_signed: boolean
  risk_adjusted_score: number
  rogue_flag: boolean
  status: string
  dna: {
    style: string
    model_family: string
    primary_edge: string
    time_horizon: string
  }
}

export interface IntelligenceLoopState {
  timestamp: number
  loop_id: string
  regime: string
  meta_agent: {
    status: string
    recommendation: string
    capital_posture: string
  }
  system_metrics: {
    portfolio_var_95_pct: number
    avg_confidence: number
    autonomy_score: number
    execution_latency_ms: number
    ui_latency_ms: number
    active_agents: number
  }
  stage_status: IntelligenceStage[]
  leaderboard: Array<{
    rank: number
    agent_id: string
    name: string
    trust_score: number
    confidence_score: number
    capital_allocated_pct: number
    model: string
  }>
  agents: IntelligentAgent[]
  allocation_summary: {
    winners: string[]
    watchlist: string[]
    capital_rotation: string
  }
  slashing_summary: {
    candidates: Array<{
      agent_id: string
      name: string
      reason: string
      slash_pct: number
    }>
    slash_count: number
  }
}

export interface DemoState {
  headline: string
  judge_script: Array<{
    step: number
    title: string
    description: string
    status: 'complete' | 'active' | 'pending'
  }>
  talking_points: string[]
  contract_prompt_example: string
  loop_snapshot: IntelligenceLoopState
}

export interface GovernanceSuggestions {
  regime: string
  suggestions: Array<{
    title: string
    reason: string
    impact: string
  }>
  predictive_vote_outcome: {
    pass_probability: number
    delegation_bias: string
  }
}

export function useIntelligenceLoop() {
  return useQuery<IntelligenceLoopState>({
    queryKey: ['intelligence', 'loop'],
    queryFn: () => api.get('/api/intelligence/loop').then(r => r.data),
    refetchInterval: 4000,
  })
}

export function useDemoState() {
  return useQuery<DemoState>({
    queryKey: ['intelligence', 'demo'],
    queryFn: () => api.get('/api/intelligence/demo').then(r => r.data),
    refetchInterval: 8000,
  })
}

export function useGovernanceSuggestions() {
  return useQuery<GovernanceSuggestions>({
    queryKey: ['intelligence', 'governance-suggestions'],
    queryFn: () => api.get('/api/intelligence/governance-suggestions').then(r => r.data),
    refetchInterval: 10000,
  })
}
