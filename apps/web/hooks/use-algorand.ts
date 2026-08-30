"use client"

import { useState, useEffect, useCallback, useRef } from "react"

export type AlgorandState = {
  address: string | null
  connected: boolean
  connecting: boolean
  error: string | null
}

const SESSION_KEY = "dacap_algorand"

function saveSession(address: string) {
  try { sessionStorage.setItem(SESSION_KEY, address) } catch {}
}

function loadSession(): string | null {
  try { return sessionStorage.getItem(SESSION_KEY) } catch { return null }
}

function clearSession() {
  try { sessionStorage.removeItem(SESSION_KEY) } catch {}
}

export function useAlgorand() {
  const [state, setState] = useState<AlgorandState>({
    address: null,
    connected: false,
    connecting: false,
    error: null,
  })

  // peraWallet instance — kept in a ref so it's stable across renders
  const peraRef = useRef<InstanceType<Awaited<typeof import("@perawallet/connect")>["PeraWalletConnect"]> | null>(null)

  const getOrCreatePera = useCallback(async () => {
    if (peraRef.current) return peraRef.current
    const { PeraWalletConnect } = await import("@perawallet/connect")
    const pera = new PeraWalletConnect()
    peraRef.current = pera
    return pera
  }, [])

  // Restore session on mount
  useEffect(() => {
    const saved = loadSession()
    if (!saved) return

    async function restore() {
      try {
        const pera = await getOrCreatePera()
        const accounts = await pera.reconnectSession()
        if (accounts.length > 0 && accounts[0] === saved) {
          setState({ address: accounts[0], connected: true, connecting: false, error: null })
        } else {
          clearSession()
        }
      } catch {
        clearSession()
      }
    }

    restore()
  }, [getOrCreatePera])

  const connect = useCallback(async () => {
    setState((prev) => ({ ...prev, connecting: true, error: null }))
    try {
      const pera = await getOrCreatePera()
      const accounts = await pera.connect()
      if (!accounts || accounts.length === 0) {
        setState((prev) => ({ ...prev, connecting: false, error: "No account returned from Pera Wallet" }))
        return
      }
      const address = accounts[0]
      saveSession(address)
      setState({ address, connected: true, connecting: false, error: null })
    } catch (e: unknown) {
      setState((prev) => ({
        ...prev,
        connecting: false,
        error: e instanceof Error ? e.message : "Pera Wallet connection failed",
      }))
    }
  }, [getOrCreatePera])

  const disconnect = useCallback(async () => {
    try {
      const pera = peraRef.current
      if (pera) await pera.disconnect()
    } catch {}
    clearSession()
    setState({ address: null, connected: false, connecting: false, error: null })
  }, [])

  const shortAddress = state.address
    ? `${state.address.slice(0, 4)}…${state.address.slice(-4)}`
    : null

  return { ...state, shortAddress, connect, disconnect }
}
