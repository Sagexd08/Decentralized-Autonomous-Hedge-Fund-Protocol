"use client"

import { useEffect, useState, useCallback, useRef } from "react"
import { newsApi, type NewsItem, type NewsSignal } from "@/lib/api"

const POLL_INTERVAL_MS = 60_000 // 1 minute

export function useNews(limit = 20): {
  items: NewsItem[]
  signals: NewsSignal[]
  loading: boolean
  error: string | null
  refresh: () => void
} {
  const [items, setItems]     = useState<NewsItem[]>([])
  const [signals, setSignals] = useState<NewsSignal[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState<string | null>(null)
  const timer = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetch = useCallback(async () => {
    try {
      const [newsRes, sigRes] = await Promise.allSettled([
        newsApi.crypto(limit),
        newsApi.signals(10),
      ])

      if (newsRes.status === "fulfilled") {
        setItems(newsRes.value.items ?? [])
        setError(null)
      } else {
        setError("News unavailable")
      }

      if (sigRes.status === "fulfilled") {
        setSignals(sigRes.value.signals ?? [])
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Fetch failed")
    } finally {
      setLoading(false)
    }
  }, [limit])

  useEffect(() => {
    fetch()
    timer.current = setInterval(fetch, POLL_INTERVAL_MS)
    return () => {
      if (timer.current) clearInterval(timer.current)
    }
  }, [fetch])

  return { items, signals, loading, error, refresh: fetch }
}
