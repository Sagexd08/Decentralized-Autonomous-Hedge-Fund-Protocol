import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Shield, CheckCircle, AlertTriangle, ExternalLink, Copy,
  FileCode2, ChevronRight, X, Upload, Plus, Clock,
} from 'lucide-react'
import { api } from '../utils/api'
import { useDemoState } from '../hooks/useIntelligence'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface ContractSummary {
  id: string
  name: string
  version: string
  address: string
  status: string
  audited: boolean
  tvl: number
  explanation: string
  submitted_by: string | null
  submitted_at?: number
}

interface ContractDetail extends ContractSummary {
  source_code: string
  key_functions: { name: string; desc: string }[]
  events: string[]
}

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------
function useContracts() {
  return useQuery<ContractSummary[]>({
    queryKey: ['contracts'],
    queryFn: () => api.get('/api/contracts/').then(r => r.data),
  })
}

function useContractDetail(id: string | null) {
  return useQuery<ContractDetail>({
    queryKey: ['contracts', id],
    queryFn: () => api.get(`/api/contracts/${id}`).then(r => r.data),
    enabled: !!id,
  })
}

function useSubmitContract() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: {
      name: string; version: string; address: string
      source_code: string; explanation: string; submitted_by: string
    }) => api.post('/api/contracts/submit', data).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['contracts'] }),
  })
}

// ---------------------------------------------------------------------------
// Syntax highlighter (minimal — colours Solidity keywords)
// ---------------------------------------------------------------------------
function SolidityCode({ code }: { code: string }) {
  const lines = code.split('\n')
  return (
    <div className="font-mono text-xs leading-relaxed overflow-x-auto">
      {lines.map((line, i) => (
        <div key={i} className="flex">
          <span className="select-none text-slate-700 w-10 shrink-0 text-right pr-3">{i + 1}</span>
          <span dangerouslySetInnerHTML={{ __html: highlight(line) }} />
        </div>
      ))}
    </div>
  )
}

function highlight(line: string): string {
  return line
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/(\/\/.*$)/g, '<span style="color:#64748b">$1</span>')
    .replace(/\b(pragma|solidity|contract|interface|library|import|using|for|is|mapping|address|uint256|uint8|uint|int256|bool|bytes32|string|memory|storage|calldata|public|private|external|internal|view|pure|payable|returns|return|emit|event|modifier|require|revert|if|else|for|while|struct|enum|constructor|function|override|virtual|abstract|immutable|constant|indexed)\b/g,
      '<span style="color:#a855f7">$1</span>')
    .replace(/\b(true|false|msg|block|tx|this|super|owner)\b/g,
      '<span style="color:#f59e0b">$1</span>')
    .replace(/"([^"]*)"/g, '<span style="color:#10b981">"$1"</span>')
    .replace(/\b(\d+)\b/g, '<span style="color:#00f5ff">$1</span>')
}

// ---------------------------------------------------------------------------
// Submit modal
// ---------------------------------------------------------------------------
function SubmitModal({ onClose, onSubmit }: { onClose: () => void; onSubmit: (d: any) => void }) {
  const [name, setName] = useState('')
  const [version, setVersion] = useState('v1.0')
  const [address, setAddress] = useState('')
  const [source, setSource] = useState('')
  const [explanation, setExplanation] = useState('')
  const [submitter, setSubmitter] = useState('')

  const valid = name.trim() && source.trim().length > 20 && explanation.trim().length > 10

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="bg-slate-950 border border-border rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto"
      >
        <div className="flex items-center justify-between p-5 border-b border-border">
          <div className="flex items-center gap-2">
            <Upload size={14} className="text-cyan" />
            <h2 className="text-sm font-semibold text-white">Submit Smart Contract</h2>
          </div>
          <button onClick={onClose} className="text-slate-500 hover:text-white"><X size={16} /></button>
        </div>

        <div className="p-5 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-slate-400 mb-1.5 block">Contract Name</label>
              <input value={name} onChange={e => setName(e.target.value)}
                placeholder="e.g. MyYieldStrategy"
                className="w-full bg-slate-900 border border-border rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-cyan/50" />
            </div>
            <div>
              <label className="text-xs text-slate-400 mb-1.5 block">Version</label>
              <input value={version} onChange={e => setVersion(e.target.value)}
                placeholder="v1.0"
                className="w-full bg-slate-900 border border-border rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-cyan/50" />
            </div>
          </div>

          <div>
            <label className="text-xs text-slate-400 mb-1.5 block">Deployed Address (optional)</label>
            <input value={address} onChange={e => setAddress(e.target.value)}
              placeholder="0x..."
              className="w-full bg-slate-900 border border-border rounded-lg px-3 py-2 text-sm text-slate-100 font-mono placeholder-slate-600 focus:outline-none focus:border-cyan/50" />
          </div>

          <div>
            <label className="text-xs text-slate-400 mb-1.5 block">Solidity Source Code</label>
            <textarea value={source} onChange={e => setSource(e.target.value)}
              placeholder="// SPDX-License-Identifier: MIT&#10;pragma solidity ^0.8.20;&#10;&#10;contract MyContract { ... }"
              rows={10}
              className="w-full bg-slate-900 border border-border rounded-lg px-3 py-2 text-sm text-slate-100 font-mono placeholder-slate-600 focus:outline-none focus:border-cyan/50 resize-none" />
          </div>

          <div>
            <label className="text-xs text-slate-400 mb-1.5 block">Explanation</label>
            <textarea value={explanation} onChange={e => setExplanation(e.target.value)}
              placeholder="Describe what this contract does, its key mechanisms, security considerations, and how it integrates with DACAP..."
              rows={4}
              className="w-full bg-slate-900 border border-border rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-cyan/50 resize-none" />
          </div>

          <div>
            <label className="text-xs text-slate-400 mb-1.5 block">Your Address / Name (optional)</label>
            <input value={submitter} onChange={e => setSubmitter(e.target.value)}
              placeholder="0x... or anonymous"
              className="w-full bg-slate-900 border border-border rounded-lg px-3 py-2 text-sm text-slate-100 font-mono placeholder-slate-600 focus:outline-none focus:border-cyan/50" />
          </div>

          <button
            onClick={() => { onSubmit({ name, version, address, source_code: source, explanation, submitted_by: submitter || 'anonymous' }); onClose() }}
            disabled={!valid}
            className="w-full py-2.5 rounded-xl text-sm font-medium bg-cyan/10 text-cyan border border-cyan/20 hover:bg-cyan/20 transition-all disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            <Upload size={13} /> Submit Contract
          </button>
        </div>
      </motion.div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function Contracts() {
  const [selectedId, setSelectedId] = useState<string | null>('capital-vault')
  const [showSubmit, setShowSubmit] = useState(false)
  const [copied, setCopied] = useState(false)
  const [toast, setToast] = useState<string | null>(null)

  const { data: contracts = [], isLoading } = useContracts()
  const { data: detail, isLoading: detailLoading } = useContractDetail(selectedId)
  const { data: demo } = useDemoState()
  const submitContract = useSubmitContract()

  const showToast = (msg: string) => { setToast(msg); setTimeout(() => setToast(null), 3000) }

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  const handleSubmit = (data: any) => {
    submitContract.mutate(data, {
      onSuccess: () => showToast('Contract submitted for review ✓'),
      onError: (e: any) => showToast(e?.response?.data?.detail ?? 'Submission failed'),
    })
  }

  const builtinContracts = contracts.filter(c => !c.submitted_by)
  const userContracts = contracts.filter(c => c.submitted_by)

  return (
    <div className="space-y-5">
      {/* Toast */}
      <AnimatePresence>
        {toast && (
          <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="fixed top-4 right-4 z-50 bg-slate-900 border border-border rounded-xl px-4 py-2.5 text-sm text-white shadow-xl">
            {toast}
          </motion.div>
        )}
      </AnimatePresence>

      {showSubmit && <SubmitModal onClose={() => setShowSubmit(false)} onSubmit={handleSubmit} />}

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Smart Contracts</h1>
          <p className="text-slate-500 text-sm mt-0.5">Protocol infrastructure plus AI-assisted contract generation for the hackathon demo</p>
        </div>
        <button
          onClick={() => setShowSubmit(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium bg-cyan/10 text-cyan border border-cyan/20 hover:bg-cyan/20 transition-all"
        >
          <Plus size={13} /> Submit Contract
        </button>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div className="card col-span-2">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold text-white">AI Smart Contract Generator</h3>
            <span className="text-xs px-2 py-0.5 rounded-full border bg-cyan/10 text-cyan border-cyan/20">ChatGPT for Smart Contracts</span>
          </div>
          <p className="text-xs text-slate-500 mb-3">
            Use the generator prompt below in the demo to show natural-language-to-protocol scaffolding.
          </p>
          <div className="rounded-xl border border-purple/20 bg-purple/5 p-3 font-mono text-xs text-slate-200">
            {demo?.contract_prompt_example ?? 'Create a hedge fund that rebalances every hour based on volatility and slashes agents after a 15% drawdown.'}
          </div>
        </div>
        <div className="card">
          <h3 className="text-sm font-semibold text-white mb-2">Next-Gen Contract Map</h3>
          <div className="space-y-2 text-xs">
            {['StrategyNFT.sol', 'AnalyticsOracle.sol', 'GovernanceExecutor.sol'].map(name => (
              <div key={name} className="rounded-lg border border-border bg-slate-900/50 px-3 py-2 text-slate-300">
                {name}
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-4 h-[calc(100vh-180px)] min-h-[600px]">
        {/* Left sidebar — contract list */}
        <div className="col-span-1 space-y-2 overflow-y-auto pr-1">
          {/* Protocol contracts */}
          <p className="text-xs text-slate-500 font-medium px-1 mb-2">Protocol Contracts</p>
          {isLoading ? (
            [1,2,3,4].map(i => <div key={i} className="h-16 bg-surface rounded-xl animate-pulse border border-border" />)
          ) : (
            builtinContracts.map(c => (
              <button
                key={c.id}
                onClick={() => setSelectedId(c.id)}
                className={`w-full text-left p-3 rounded-xl border transition-all ${
                  selectedId === c.id
                    ? 'border-cyan/40 bg-cyan/5'
                    : 'border-border hover:border-slate-600 bg-surface'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-semibold text-white">{c.name}</span>
                  <ChevronRight size={11} className={selectedId === c.id ? 'text-cyan' : 'text-slate-600'} />
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-500 font-mono">{c.version}</span>
                  {c.audited
                    ? <span className="flex items-center gap-0.5 text-xs text-green"><CheckCircle size={9} /> Audited</span>
                    : <span className="flex items-center gap-0.5 text-xs text-yellow-400"><AlertTriangle size={9} /> Pending</span>}
                </div>
                {c.tvl > 0 && (
                  <p className="text-xs text-slate-600 mt-1">${(c.tvl / 1e6).toFixed(1)}M TVL</p>
                )}
              </button>
            ))
          )}

          {/* User submissions */}
          {userContracts.length > 0 && (
            <>
              <p className="text-xs text-slate-500 font-medium px-1 mt-4 mb-2">Community Submissions</p>
              {userContracts.map(c => (
                <button
                  key={c.id}
                  onClick={() => setSelectedId(c.id)}
                  className={`w-full text-left p-3 rounded-xl border transition-all ${
                    selectedId === c.id
                      ? 'border-purple/40 bg-purple/5'
                      : 'border-border hover:border-slate-600 bg-surface'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-semibold text-white">{c.name}</span>
                    <Clock size={10} className="text-yellow-400" />
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-500">{c.version}</span>
                    <span className="text-xs text-yellow-400">Pending Review</span>
                  </div>
                  <p className="text-xs text-slate-600 mt-0.5 truncate">by {c.submitted_by}</p>
                </button>
              ))}
            </>
          )}
        </div>

        {/* Right panel — contract detail */}
        <div className="col-span-3 overflow-y-auto space-y-4">
          {!selectedId && (
            <div className="card h-full flex items-center justify-center text-slate-500 text-sm">
              Select a contract to view its source and details
            </div>
          )}

          {detailLoading && (
            <div className="card h-40 animate-pulse" />
          )}

          {detail && !detailLoading && (
            <motion.div key={detail.id} initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} className="space-y-4">
              {/* Header */}
              <div className="card">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-xl bg-cyan/10 flex items-center justify-center">
                      <FileCode2 size={16} className="text-cyan" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h2 className="text-base font-bold text-white">{detail.name}</h2>
                        <span className="text-xs text-slate-500 font-mono">{detail.version}</span>
                        {detail.audited
                          ? <span className="flex items-center gap-1 text-xs text-green border border-green/20 bg-green/10 px-2 py-0.5 rounded-full"><CheckCircle size={9} /> Audited</span>
                          : <span className="flex items-center gap-1 text-xs text-yellow-400 border border-yellow-400/20 bg-yellow-400/10 px-2 py-0.5 rounded-full"><AlertTriangle size={9} /> Pending Audit</span>}
                        {detail.status === 'pending_review' && (
                          <span className="flex items-center gap-1 text-xs text-purple border border-purple/20 bg-purple/10 px-2 py-0.5 rounded-full"><Clock size={9} /> Community</span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-xs font-mono text-slate-500">{detail.address}</span>
                        <button onClick={() => handleCopy(detail.address)} className="text-slate-600 hover:text-slate-300 transition-colors">
                          <Copy size={11} />
                        </button>
                        <button className="text-slate-600 hover:text-slate-300 transition-colors">
                          <ExternalLink size={11} />
                        </button>
                      </div>
                    </div>
                  </div>
                  {detail.tvl > 0 && (
                    <div className="text-right">
                      <p className="text-xs text-slate-500">TVL</p>
                      <p className="text-lg font-bold font-mono text-cyan">${(detail.tvl / 1e6).toFixed(1)}M</p>
                    </div>
                  )}
                </div>

                {/* Explanation */}
                <div className="p-3 bg-slate-900/50 rounded-xl border border-border">
                  <p className="text-xs text-slate-400 leading-relaxed">{detail.explanation}</p>
                </div>

                {/* Functions + Events */}
                {(detail.key_functions?.length > 0 || detail.events?.length > 0) && (
                  <div className="grid grid-cols-2 gap-4 mt-3">
                    {detail.key_functions?.length > 0 && (
                      <div>
                        <p className="text-xs text-slate-500 font-medium mb-2">Key Functions</p>
                        <div className="space-y-1.5">
                          {detail.key_functions.map(f => (
                            <div key={f.name} className="p-2 rounded-lg bg-cyan/5 border border-cyan/10">
                              <p className="font-mono text-xs text-cyan">{f.name}</p>
                              <p className="text-xs text-slate-500 mt-0.5">{f.desc}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {detail.events?.length > 0 && (
                      <div>
                        <p className="text-xs text-slate-500 font-medium mb-2">Events</p>
                        <div className="space-y-1">
                          {detail.events.map(e => (
                            <div key={e} className="font-mono text-xs text-purple bg-purple/5 rounded px-2 py-1 border border-purple/10">{e}</div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Source code */}
              <div className="card">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                    <FileCode2 size={13} className="text-slate-400" />
                    {detail.name}.sol
                  </h3>
                  <button
                    onClick={() => handleCopy(detail.source_code)}
                    className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-white transition-colors px-2 py-1 rounded-lg hover:bg-white/5"
                  >
                    <Copy size={11} /> {copied ? 'Copied!' : 'Copy'}
                  </button>
                </div>
                <div className="bg-slate-950 rounded-xl border border-border p-4 overflow-x-auto max-h-[600px] overflow-y-auto">
                  <SolidityCode code={detail.source_code} />
                </div>
              </div>
            </motion.div>
          )}
        </div>
      </div>
    </div>
  )
}
