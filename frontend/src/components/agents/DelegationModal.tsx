import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Wallet, CheckCircle, AlertCircle, Loader2, ArrowRight } from 'lucide-react'
import { useProtocolStore } from '../../store/protocolStore'
import { useContractInteraction, DelegationFormParams } from '../../hooks/useContractInteraction'
export interface DelegationModalProps {
  isOpen: boolean
  onClose: () => void
  agent: { id: string; name: string; risk: string; score: number; riskPool: 0 | 1 | 2 } | null
}

type Step = 'params' | 'signing' | 'confirming' | 'success' | 'error'

interface FormValues {
  ethAmount: string
  maxDrawdownPct: string
  maxAllocationEth: string
}

interface FormErrors {
  ethAmount?: string
  maxDrawdownPct?: string
  maxAllocationEth?: string
}

function validateForm(values: FormValues): FormErrors {
  const errors: FormErrors = {}
  const amount = parseFloat(values.ethAmount)
  if (!values.ethAmount || isNaN(amount) || amount <= 0) {
    errors.ethAmount = 'Deposit amount must be greater than 0'
  }
  const pct = parseFloat(values.maxDrawdownPct)
  const bps = Math.round(pct * 100)
  if (!values.maxDrawdownPct || isNaN(pct) || bps < 100 || bps > 5000) {
    errors.maxDrawdownPct = 'Max drawdown must be between 1% and 50%'
  }
  const alloc = parseFloat(values.maxAllocationEth)
  if (!values.maxAllocationEth || isNaN(alloc)) {
    errors.maxAllocationEth = 'Allocation cap is required'
  } else if (!errors.ethAmount && alloc > amount) {
    errors.maxAllocationEth = 'Allocation cap cannot exceed deposit amount'
  }
  return errors
}

export default function DelegationModal({ isOpen, onClose, agent }: DelegationModalProps) {
  const { walletAddress, isConnected, addDelegation } = useProtocolStore()
  const { signDelegation, depositETH, isLoading } = useContractInteraction()

  const [step, setStep] = useState<Step>('params')
  const [form, setForm] = useState<FormValues>({ ethAmount: '', maxDrawdownPct: '', maxAllocationEth: '' })
  const [formErrors, setFormErrors] = useState<FormErrors>({})
  const [stepError, setStepError] = useState<string | null>(null)
  const [signature, setSignature] = useState<string>('')
  const [txHash, setTxHash] = useState<string>('')

  if (!isOpen || !agent) return null

  const params: DelegationFormParams = {
    agentAddress: agent.id.startsWith('0x') && agent.id.length === 42
      ? agent.id
      : '0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266',
    agentName: agent.name,
    pool: agent.riskPool,
    ethAmount: form.ethAmount,
    maxDrawdownBps: Math.round(parseFloat(form.maxDrawdownPct || '0') * 100),
    maxAllocationEth: form.maxAllocationEth,
  }

  const handleParamsSubmit = () => {
    const errors = validateForm(form)
    if (Object.keys(errors).length > 0) {
      setFormErrors(errors)
      return
    }
    setFormErrors({})
    setStep('signing')
    handleSign()
  }

  const handleSign = async () => {
    if (!walletAddress) return
    setStepError(null)
    try {
      const sig = await signDelegation(params, walletAddress)
      setSignature(sig)
      setStep('confirming')
    } catch (err: unknown) {
      const e = err as { message?: string }
      setStepError(e.message ?? 'Signing failed')
      setStep('signing')
    }
  }

  const handleDeposit = async () => {
    if (!walletAddress) return
    setStepError(null)
    try {
      const hash = await depositETH(params, signature, walletAddress)
      setTxHash(hash)
      // Persist delegation so agents page can gate Start AI button
      addDelegation({
        agentId: agent.id,
        agentName: agent.name,
        agentRisk: agent.risk,
        ethAmount: parseFloat(form.ethAmount),
        txHash: hash,
        timestamp: Date.now(),
        walletAddress: walletAddress,
      })
      setStep('success')
    } catch (err: unknown) {
      const e = err as { message?: string }
      setStepError(e.message ?? 'Transaction failed')
    }
  }

  const handleClose = () => {
    setStep('params')
    setForm({ ethAmount: '', maxDrawdownPct: '', maxAllocationEth: '' })
    setFormErrors({})
    setStepError(null)
    setSignature('')
    setTxHash('')
    onClose()
  }

  const truncateHash = (hash: string) =>
    hash ? `${hash.slice(0, 10)}...${hash.slice(-8)}` : ''

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        className="bg-[#0f1117] border border-border rounded-2xl w-full max-w-md mx-4 overflow-hidden"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h2 className="text-white font-bold text-base">Delegate Capital</h2>
          <button onClick={handleClose} className="text-slate-500 hover:text-white text-lg leading-none">×</button>
        </div>

        <AnimatePresence mode="wait">
          {/* Step 1: Params */}
          {step === 'params' && (
            <motion.div
              key="params"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              className="p-6 space-y-4"
            >
              {/* Agent info */}
              <div className="bg-surface rounded-xl p-4 space-y-1">
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">Agent</span>
                  <span className="text-white font-medium">{agent.name}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">Risk Tier</span>
                  <span className="text-cyan font-medium">{agent.risk}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">Protocol Score</span>
                  <span className="text-white font-mono">{agent.score}/100</span>
                </div>
              </div>

              {/* ETH Amount */}
              <div>
                <label className="block text-xs text-slate-400 mb-1">ETH Amount</label>
                <input
                  type="number"
                  min="0"
                  step="0.001"
                  value={form.ethAmount}
                  onChange={e => setForm(f => ({ ...f, ethAmount: e.target.value }))}
                  placeholder="0.0"
                  className="w-full bg-surface border border-border rounded-lg px-3 py-2 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-cyan/40"
                />
                {formErrors.ethAmount && (
                  <p className="text-red-400 text-xs mt-1">{formErrors.ethAmount}</p>
                )}
              </div>

              {/* Max Drawdown */}
              <div>
                <label className="block text-xs text-slate-400 mb-1">Max Drawdown % (1–50)</label>
                <input
                  type="number"
                  min="1"
                  max="50"
                  step="0.01"
                  value={form.maxDrawdownPct}
                  onChange={e => setForm(f => ({ ...f, maxDrawdownPct: e.target.value }))}
                  placeholder="e.g. 10"
                  className="w-full bg-surface border border-border rounded-lg px-3 py-2 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-cyan/40"
                />
                {formErrors.maxDrawdownPct && (
                  <p className="text-red-400 text-xs mt-1">{formErrors.maxDrawdownPct}</p>
                )}
              </div>

              {/* Max Allocation */}
              <div>
                <label className="block text-xs text-slate-400 mb-1">Max Allocation ETH (≤ deposit)</label>
                <input
                  type="number"
                  min="0"
                  step="0.001"
                  value={form.maxAllocationEth}
                  onChange={e => setForm(f => ({ ...f, maxAllocationEth: e.target.value }))}
                  placeholder="0.0"
                  className="w-full bg-surface border border-border rounded-lg px-3 py-2 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-cyan/40"
                />
                {formErrors.maxAllocationEth && (
                  <p className="text-red-400 text-xs mt-1">{formErrors.maxAllocationEth}</p>
                )}
              </div>

              {!isConnected && (
                <div className="flex items-center gap-2 text-xs text-slate-400 bg-surface rounded-lg px-3 py-2">
                  <Wallet size={13} />
                  <span>Connect wallet first</span>
                </div>
              )}

              <button
                onClick={handleParamsSubmit}
                disabled={!isConnected}
                className="btn-primary w-full flex items-center justify-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Sign &amp; Continue <ArrowRight size={14} />
              </button>
            </motion.div>
          )}

          {/* Step 2: Signing */}
          {step === 'signing' && (
            <motion.div
              key="signing"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              className="p-6 space-y-4"
            >
              {!stepError ? (
                <div className="flex flex-col items-center gap-4 py-6">
                  <Loader2 size={32} className="text-cyan animate-spin" />
                  <p className="text-slate-300 text-sm">Signing delegation parameters...</p>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="flex items-start gap-3 bg-red-500/10 border border-red-500/20 rounded-xl p-4">
                    <AlertCircle size={16} className="text-red-400 mt-0.5 shrink-0" />
                    <p className="text-red-400 text-sm">{stepError}</p>
                  </div>
                  <button
                    onClick={handleSign}
                    disabled={isLoading}
                    className="btn-primary w-full flex items-center justify-center gap-2"
                  >
                    {isLoading ? <Loader2 size={14} className="animate-spin" /> : null}
                    Retry Signing
                  </button>
                </div>
              )}
            </motion.div>
          )}

          {/* Step 3: Confirming */}
          {step === 'confirming' && (
            <motion.div
              key="confirming"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              className="p-6 space-y-4"
            >
              <div className="bg-surface rounded-xl p-4 space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-slate-500">Agent</span>
                  <span className="text-white">{agent.name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Amount</span>
                  <span className="text-cyan font-mono">{form.ethAmount} ETH</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Max Drawdown</span>
                  <span className="text-white">{form.maxDrawdownPct}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Allocation Cap</span>
                  <span className="text-white font-mono">{form.maxAllocationEth} ETH</span>
                </div>
              </div>

              {stepError && (
                <div className="flex items-start gap-3 bg-red-500/10 border border-red-500/20 rounded-xl p-4">
                  <AlertCircle size={16} className="text-red-400 mt-0.5 shrink-0" />
                  <p className="text-red-400 text-sm">{stepError}</p>
                </div>
              )}

              <button
                onClick={handleDeposit}
                disabled={isLoading}
                className="btn-primary w-full flex items-center justify-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {isLoading ? (
                  <>
                    <Loader2 size={14} className="animate-spin" />
                    Confirming...
                  </>
                ) : (
                  <>
                    Confirm Deposit <ArrowRight size={14} />
                  </>
                )}
              </button>
            </motion.div>
          )}

          {/* Success */}
          {step === 'success' && (
            <motion.div
              key="success"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              className="p-6 space-y-4"
            >
              <div className="flex flex-col items-center gap-3 py-4">
                <CheckCircle size={40} className="text-green" />
                <p className="text-white font-bold text-base">Delegation Confirmed</p>
              </div>

              <div className="bg-surface rounded-xl p-4 space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-slate-500">Agent</span>
                  <span className="text-white">{agent.name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Amount</span>
                  <span className="text-cyan font-mono">{form.ethAmount} ETH</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Max Drawdown</span>
                  <span className="text-white">{form.maxDrawdownPct}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Allocation Cap</span>
                  <span className="text-white font-mono">{form.maxAllocationEth} ETH</span>
                </div>
                <div className="flex justify-between items-center pt-2 border-t border-border">
                  <span className="text-slate-500">Tx Hash</span>
                  <span className="text-cyan font-mono text-xs" title={txHash}>
                    {truncateHash(txHash)}
                  </span>
                </div>
              </div>

              <button onClick={handleClose} className="btn-primary w-full">
                Done
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  )
}
