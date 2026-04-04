import { useQuery } from '@tanstack/react-query'
import { api } from '../utils/api'

interface MonteCarloData {
  stats: Record<string, number>
  paths: number[][]
}

const mockMonteCarloData: MonteCarloData = {
  stats: {
    mean_return: 0.08,
    std_dev: 0.15,
    var_95: -0.12,
    cvar_95: -0.18,
    sharpe_ratio: 0.53,
  },
  paths: [],
}

export function useMonteCarloData() {
  return useQuery<MonteCarloData>({
    queryKey: ['monte-carlo'],
    queryFn: () => api.get('/api/analytics/monte-carlo').then(r => r.data),
    placeholderData: mockMonteCarloData,
  })
}
