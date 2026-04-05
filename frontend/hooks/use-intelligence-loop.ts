"use client"

import { useEffect, useState, useCallback } from "react"
import { intelligenceApi } from "@/lib/api"

export interface AgentDecision {
  id: string
  name: string
  strategy: string
  model: string
  decision: "BUY" | "SELL" | "HOLD"
  confidence_score: number
  trust_score: number
  anomaly_score: number
  rogue_flag: boolean
  status: string
  regime_context: string
}

export interface LoopState {
  regime: string
  meta_agent: {
    recommendation: string
    capital_posture: string
  }
  agents: AgentDecision[]
  system_metrics: {
    avg_confidence: number
    active_agents: number
    autonomy_score: number
  }
}

export function useIntelligenceLoop(pollMs = 5000) {
  const [state, setState] = useState<LoopState | null>(null)
  const [loading, setLoading] = useState(true)

  const fetch = useCallback(async () => {
    try {
      const data = await intelligenceApi.loop() as LoopState
      setState(data)
    } catch {
      // keep last state on error
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetch()
    const id = setInterval(fetch, pollMs)
    return () => clearInterval(id)
  }, [fetch, pollMs])

  return { state, loading }
}
