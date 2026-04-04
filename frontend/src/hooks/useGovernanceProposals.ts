import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../utils/api'

export interface ParamMeta {
  label: string
  min: number
  max: number
  step: number
  unit: string
  category: string
}

export interface GovernanceProposal {
  id: string
  title: string
  description: string
  category: string
  param_name?: string
  current_value?: number
  proposed_value?: number
  proposer: string
  status: 'active' | 'passed' | 'rejected' | 'expired' | 'vetoed'
  votes_for: number
  votes_against: number
  votes_for_pct: number
  votes_against_pct: number
  total_votes: number
  quorum_pct_needed: number
  quorum_progress: number
  quorum_reached: boolean
  end_date: string
  created_date: string
  param_meta?: ParamMeta
}

export interface GovernanceParam {
  value: number
  label: string
  min: number
  max: number
  step: number
  unit: string
  category: string
}

export interface GovernanceStats {
  total_proposals: number
  active: number
  passed: number
  rejected: number
  expired: number
  total_votes_cast: number
  params_executed: number
}

export function useGovernanceProposals() {
  return useQuery<GovernanceProposal[]>({
    queryKey: ['governance', 'proposals'],
    queryFn: () => api.get('/api/governance/proposals').then(r => r.data),
    refetchInterval: 10000,
  })
}

export function useGovernanceParams() {
  return useQuery<Record<string, GovernanceParam>>({
    queryKey: ['governance', 'params'],
    queryFn: () => api.get('/api/governance/params').then(r => r.data),
    refetchInterval: 30000,
  })
}

export function useGovernanceStats() {
  return useQuery<GovernanceStats>({
    queryKey: ['governance', 'stats'],
    queryFn: () => api.get('/api/governance/stats').then(r => r.data),
    refetchInterval: 15000,
  })
}

export function useVoterHistory(address: string) {
  return useQuery({
    queryKey: ['governance', 'votes', address],
    queryFn: () => api.get(`/api/governance/votes/${address}`).then(r => r.data),
    enabled: !!address,
  })
}

export function useCastVote() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { proposal_id: string; voter: string; support: boolean; weight?: number }) =>
      api.post('/api/governance/vote', data).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['governance'] })
    },
  })
}

export function useVetoProposal() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { proposal_id: string; admin_address: string; reason: string }) =>
      api.post(`/api/governance/proposals/${data.proposal_id}/veto`, {
        admin_address: data.admin_address,
        reason: data.reason,
      }).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['governance'] })
    },
  })
}

export function useCreateProposal() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: {
      title: string
      description: string
      category: string
      param_name?: string
      proposed_value?: number
      proposer?: string
      duration_days?: number
    }) => api.post('/api/governance/propose', data).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['governance'] })
    },
  })
}
