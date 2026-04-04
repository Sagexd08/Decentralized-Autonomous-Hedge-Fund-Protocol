import { useState } from 'react'
import { ethers } from 'ethers'
import { CAPITAL_VAULT_ABI } from '../contracts/CapitalVaultABI'
import rawConfig from '../contracts/config.json'

interface ContractConfig {
  CapitalVault: string
  AllocationEngine: string
  AgentRegistry: string
  SlashingModule: string
}

function getConfig(): ContractConfig {
  const cfg = rawConfig as ContractConfig
  if (!cfg.CapitalVault || !cfg.AllocationEngine || !cfg.AgentRegistry || !cfg.SlashingModule) {
    throw new Error('Contract configuration not found. Please deploy contracts first.')
  }
  return cfg
}

export interface DelegationFormParams {
  agentAddress: string
  agentName: string
  pool: 0 | 1 | 2
  ethAmount: string
  maxDrawdownBps: number
  maxAllocationEth: string
}

interface UseContractInteractionReturn {
  signDelegation: (params: DelegationFormParams, investorAddress: string) => Promise<string>
  depositETH: (params: DelegationFormParams, signature: string, investorAddress: string) => Promise<string>
  isLoading: boolean
  error: string | null
}

export function useContractInteraction(): UseContractInteractionReturn {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const signDelegation = async (params: DelegationFormParams, investorAddress: string): Promise<string> => {
    setIsLoading(true)
    setError(null)
    try {
      const cfg = getConfig()

      if (!window.ethereum) {
        throw new Error('MetaMask not detected')
      }

      const chainIdHex = await window.ethereum.request({ method: 'eth_chainId' }) as string
      const chainId = parseInt(chainIdHex, 16)
      if (chainId !== 1337 && chainId !== 31337) {
        throw new Error('Please switch to the local network (Ganache port 7545 or Hardhat port 8545)')
      }

      const payload = {
        domain: {
          name: 'DACAP',
          version: '1',
          chainId: chainId,
          verifyingContract: cfg.CapitalVault,
        },
        types: {
          DelegationParams: [
            { name: 'pool', type: 'uint8' },
            { name: 'agent', type: 'address' },
            { name: 'amount', type: 'uint256' },
            { name: 'maxDrawdownBps', type: 'uint256' },
            { name: 'maxAllocationWei', type: 'uint256' },
            { name: 'investor', type: 'address' },
          ],
        },
        primaryType: 'DelegationParams',
        message: {
          pool: params.pool,
          agent: params.agentAddress,
          amount: ethers.parseEther(params.ethAmount).toString(),
          maxDrawdownBps: params.maxDrawdownBps,
          maxAllocationWei: ethers.parseEther(params.maxAllocationEth).toString(),
          investor: ethers.getAddress(investorAddress),
        },
      }

      const signature = await window.ethereum.request({
        method: 'eth_signTypedData_v4',
        params: [investorAddress, JSON.stringify(payload)],
      }) as string

      console.log('EIP-712 payload:', JSON.stringify(payload, null, 2))
      console.log('Signature:', signature)

      return signature
    } catch (err: unknown) {
      const e = err as { code?: number; message?: string }
      if (e.code === 4001) {
        const msg = 'Signature rejected. Please try again.'
        setError(msg)
        throw new Error(msg)
      }
      const msg = e.message ?? 'Unknown error during signing'
      setError(msg)
      throw new Error(msg)
    } finally {
      setIsLoading(false)
    }
  }

  const depositETH = async (
    params: DelegationFormParams,
    signature: string,
    investorAddress: string
  ): Promise<string> => {
    setIsLoading(true)
    setError(null)
    try {
      const cfg = getConfig()

      if (!window.ethereum) {
        throw new Error('MetaMask not detected')
      }

      const chainIdHex = await window.ethereum.request({ method: 'eth_chainId' }) as string
      const chainId = parseInt(chainIdHex, 16)

      const provider = new ethers.BrowserProvider(window.ethereum, {
        chainId,
        name: 'local',
      })
      const signer = await provider.getSigner()
      const contract = new ethers.Contract(cfg.CapitalVault, CAPITAL_VAULT_ABI, signer)

      const tx = await contract.depositETH(
        params.pool,
        params.agentAddress,
        params.maxDrawdownBps,
        ethers.parseEther(params.maxAllocationEth),
        signature,
        { value: ethers.parseEther(params.ethAmount) }
      )

      const receipt = await tx.wait()
      return (receipt?.hash ?? tx.hash) as string
    } catch (err: unknown) {
      const e = err as { code?: number | string; message?: string; reason?: string; data?: { message?: string } }

      if (e.code === 4001 || e.code === 'ACTION_REJECTED') {
        const msg = 'Transaction rejected.'
        setError(msg)
        throw new Error(msg)
      }

      const reason =
        e.reason ??
        e.data?.message ??
        e.message ??
        'Transaction failed'

      setError(reason)
      throw new Error(reason)
    } finally {
      setIsLoading(false)
    }
  }

  return { signDelegation, depositETH, isLoading, error }
}
