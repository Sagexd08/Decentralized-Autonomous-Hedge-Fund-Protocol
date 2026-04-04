import { useQuery } from '@tanstack/react-query'
import { api } from '../utils/api'

export interface SupabaseStatus {
  configured: boolean
  project_url: string
  project_ref: string
  using_supabase_database: boolean
  auth_reachable: boolean
  storage_reachable: boolean
  error: string | null
}

export function useSupabaseStatus() {
  return useQuery({
    queryKey: ['supabase-status'],
    queryFn: () => api.get<SupabaseStatus>('/api/integrations/supabase/status').then((response) => response.data),
    retry: 1,
    staleTime: 30_000,
  })
}
