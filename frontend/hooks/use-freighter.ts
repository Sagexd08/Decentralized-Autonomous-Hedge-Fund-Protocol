"use client"

import { useState, useEffect, useCallback } from "react"

export type FreighterState = {
  address: string | null
  network: string | null
  connected: boolean
  connecting: boolean
  error: string | null
}

const SESSION_KEY = "dacap_freighter"

function saveSession(address: string, network: string) {
  try { sessionStorage.setItem(SESSION_KEY, JSON.stringify({ address, network })) } catch {}
}

function loadSession(): { address: string; network: string } | null {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY)
    return raw ? JSON.parse(raw) : null
  } catch { return null }
}

function clearSession() {
  try { sessionStorage.removeItem(SESSION_KEY) } catch {}
}

export function useFreighter() {
  const [state, setState] = useState<FreighterState>({
    address: null,
    network: null,
    connected: false,
    connecting: false,
    error: null,
  })

  // Restore session on mount — re-verify Freighter still has the account
  useEffect(() => {
    const session = loadSession()
    if (!session) return

    async function restore() {
      try {
        const { isConnected, getAddress, getNetwork } = await import("@stellar/freighter-api")
        const connected = await isConnected()
        if (!connected.isConnected) { clearSession(); return }
        const [addrResult, netResult] = await Promise.all([getAddress(), getNetwork()])
        if (!addrResult.error && addrResult.address === session!.address) {
          setState({
            address: addrResult.address,
            network: netResult.error ? session!.network : (netResult.network ?? session!.network),
            connected: true,
            connecting: false,
            error: null,
          })
        } else {
          clearSession()
        }
      } catch {
        clearSession()
      }
    }

    restore()
  }, [])

  const connect = useCallback(async () => {
    setState((prev) => ({ ...prev, connecting: true, error: null }))
    try {
      const { isConnected, requestAccess, getAddress, getNetwork } = await import("@stellar/freighter-api")

      const connResult = await isConnected()
      if (!connResult.isConnected) {
        setState((prev) => ({ ...prev, connecting: false, error: "Freighter extension not found. Install it from freighter.app" }))
        return
      }

      await requestAccess()

      const [addrResult, netResult] = await Promise.all([getAddress(), getNetwork()])

      if (addrResult.error) {
        setState((prev) => ({ ...prev, connecting: false, error: addrResult.error ?? "Access denied" }))
        return
      }

      const address = addrResult.address
      const network = netResult.error ? "TESTNET" : (netResult.network ?? "TESTNET")
      saveSession(address, network)
      setState({ address, network, connected: true, connecting: false, error: null })
    } catch (e: unknown) {
      setState((prev) => ({
        ...prev,
        connecting: false,
        error: e instanceof Error ? e.message : "Freighter connection failed",
      }))
    }
  }, [])

  const disconnect = useCallback(() => {
    clearSession()
    setState({ address: null, network: null, connected: false, connecting: false, error: null })
  }, [])

  const shortAddress = state.address
    ? `${state.address.slice(0, 4)}…${state.address.slice(-4)}`
    : null

  return { ...state, shortAddress, connect, disconnect }
}
