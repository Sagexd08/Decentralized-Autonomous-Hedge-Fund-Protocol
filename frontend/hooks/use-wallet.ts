"use client"

import { useState, useEffect, useCallback } from "react"

export type WalletState = {
  address: string | null
  chainId: number | null
  connected: boolean
  connecting: boolean
  error: string | null
}

const SESSION_KEY = "iris_wallet"

function saveSession(address: string, chainId: number) {
  try {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify({ address, chainId }))
  } catch {}
}

function loadSession(): { address: string; chainId: number } | null {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY)
    if (!raw) return null
    return JSON.parse(raw)
  } catch {
    return null
  }
}

function clearSession() {
  try {
    sessionStorage.removeItem(SESSION_KEY)
  } catch {}
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function getEthereum(): any {
  if (typeof window === "undefined") return null
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return (window as any).ethereum ?? null
}

export function useWallet() {
  const [state, setState] = useState<WalletState>({
    address: null,
    chainId: null,
    connected: false,
    connecting: false,
    error: null,
  })

  // Restore session on mount
  useEffect(() => {
    const session = loadSession()
    if (!session) return
    const eth = getEthereum()
    if (!eth) return

    // Verify the wallet still has the account exposed (no re-prompt)
    eth.request({ method: "eth_accounts" }).then((accounts: string[]) => {
      if (accounts.length > 0 && accounts[0].toLowerCase() === session.address.toLowerCase()) {
        setState({
          address: session.address,
          chainId: session.chainId,
          connected: true,
          connecting: false,
          error: null,
        })
      } else {
        clearSession()
      }
    }).catch(() => clearSession())
  }, [])

  // Listen for account/chain changes
  useEffect(() => {
    const eth = getEthereum()
    if (!eth) return

    const onAccounts = (accounts: string[]) => {
      if (accounts.length === 0) {
        clearSession()
        setState({ address: null, chainId: null, connected: false, connecting: false, error: null })
      } else {
        setState((prev) => {
          const next = { ...prev, address: accounts[0], connected: true }
          if (next.chainId) saveSession(accounts[0], next.chainId)
          return next
        })
      }
    }

    const onChainChanged = (chainIdHex: string) => {
      const chainId = parseInt(chainIdHex, 16)
      setState((prev) => {
        const next = { ...prev, chainId }
        if (next.address) saveSession(next.address, chainId)
        return next
      })
    }

    eth.on("accountsChanged", onAccounts)
    eth.on("chainChanged", onChainChanged)
    return () => {
      eth.removeListener("accountsChanged", onAccounts)
      eth.removeListener("chainChanged", onChainChanged)
    }
  }, [])

  const connect = useCallback(async () => {
    const eth = getEthereum()
    if (!eth) {
      setState((prev) => ({ ...prev, error: "No wallet detected. Install MetaMask." }))
      return
    }

    setState((prev) => ({ ...prev, connecting: true, error: null }))
    try {
      const [accounts, chainIdHex] = await Promise.all([
        eth.request({ method: "eth_requestAccounts" }) as Promise<string[]>,
        eth.request({ method: "eth_chainId" }) as Promise<string>,
      ])
      const address = accounts[0]
      const chainId = parseInt(chainIdHex, 16)
      saveSession(address, chainId)
      setState({ address, chainId, connected: true, connecting: false, error: null })
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Connection rejected"
      setState((prev) => ({ ...prev, connecting: false, error: msg }))
    }
  }, [])

  const disconnect = useCallback(() => {
    clearSession()
    setState({ address: null, chainId: null, connected: false, connecting: false, error: null })
  }, [])

  const shortAddress = state.address
    ? `${state.address.slice(0, 6)}…${state.address.slice(-4)}`
    : null

  return { ...state, shortAddress, connect, disconnect }
}
