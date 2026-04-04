import { useQuery } from '@tanstack/react-query'
import { api } from '../utils/api'
import { agents as mockAgents } from '../utils/mockData'

export function useAgent(id: string) {
  return useQuery({
    queryKey: ['agents', id],
    queryFn: () => api.get(`/api/agents/${id}`).then(r => r.data),
    placeholderData: mockAgents.find(a => a.id === id),
    enabled: !!id,
  })
}
