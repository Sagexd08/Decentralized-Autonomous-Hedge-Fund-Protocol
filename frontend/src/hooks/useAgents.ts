import { useQuery } from '@tanstack/react-query'
import { api } from '../utils/api'
import { agents as mockAgents } from '../utils/mockData'

export function useAgents() {
  return useQuery({
    queryKey: ['agents'],
    queryFn: () => api.get('/api/agents').then(r => r.data),
    placeholderData: mockAgents,
  })
}
