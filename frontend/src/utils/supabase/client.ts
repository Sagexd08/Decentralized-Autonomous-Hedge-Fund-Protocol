import { createClient as createSupabaseBrowserClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabasePublishableKey = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY

export const isSupabaseConfigured = Boolean(supabaseUrl && supabasePublishableKey)

let browserClient: ReturnType<typeof createSupabaseBrowserClient> | null = null

export function createSupabaseClient() {
  if (!supabaseUrl || !supabasePublishableKey) {
    throw new Error('Supabase environment variables are missing in frontend/.env.local.')
  }

  if (!browserClient) {
    browserClient = createSupabaseBrowserClient(supabaseUrl, supabasePublishableKey, {
      auth: {
        autoRefreshToken: true,
        persistSession: true,
      },
    })
  }

  return browserClient
}
