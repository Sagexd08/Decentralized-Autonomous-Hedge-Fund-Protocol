import { useQuery } from '@tanstack/react-query'
import { api } from '../utils/api'
import { pools as mockPools } from '../utils/mockData'

export function usePools() {
  return useQuery({
    queryKey: ['pools'],
    queryFn: () => api.get('/api/pools').then(r => r.data),
    placeholderData: mockPools,
  })
}
