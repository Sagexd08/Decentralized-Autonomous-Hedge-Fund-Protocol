"use client"

import { useEffect, useState, useCallback } from "react"
import { agentsApi, type Agent } from "@/lib/api"

/**
 * Fetches the agent list from the backend, with an optional risk filter.
 * Refreshes every 30 seconds.
 */
export function useAgents(risk?: string): {
  agents: Agent[]
  loading: boolean
  error: string | null
  refetch: () => void
} {
  const [agents, setAgents] = useState<Agent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetch = useCallback(() => {
    setLoading(true)
    agentsApi
      .list(risk)
      .then((data) => {
        setAgents(data)
        setError(null)
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [risk])

  useEffect(() => {
    fetch()
    const id = setInterval(fetch, 30_000)
    return () => clearInterval(id)
  }, [fetch])

  return { agents, loading, error, refetch: fetch }
}

/**
 * Fetches a single agent by id.
 */
export function useAgent(id: string): {
  agent: Agent | null
  loading: boolean
  error: string | null
  refetch: () => void
} {
  const [agent, setAgent] = useState<Agent | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetch = useCallback(() => {
    setLoading(true)
    agentsApi
      .get(id)
      .then((data) => {
        setAgent(data)
        setError(null)
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [id])

  useEffect(() => {
    fetch()
  }, [fetch])

  return { agent, loading, error, refetch: fetch }
}
