import React, { useState, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Vote, CheckCircle, XCircle, Clock, AlertCircle, Plus, ChevronDown,
  ChevronUp, Users, Zap, Shield, Settings, BarChart2, X, TrendingUp,
} from 'lucide-react'
import {
  useGovernanceProposals, useGovernanceParams, useGovernanceStats,
  useCastVote, useCreateProposal, useVetoProposal, GovernanceProposal,
} from '../hooks/useGovernanceProposals'
import { useGovernanceSuggestions } from '../hooks/useIntelligence'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
const VOTER_ADDRESS = '0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266' // simulated connected wallet
const ADMIN_ADDRESS = '0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266' // same as voter for demo — admin has extra powers

const CATEGORY_META: Record<string, { label: string; icon: React.ReactNode; color: string }> = {
  allocation: { label: 'Allocation',  icon: <BarChart2 size={12} />, color: 'text-cyan border-cyan/30 bg-cyan/10' },
  risk:        { label: 'Risk',        icon: <Shield size={12} />,    color: 'text-red-400 border-red-400/30 bg-red-400/10' },
  agents:      { label: 'Agents',      icon: <Zap size={12} />,       color: 'text-purple border-purple/30 bg-purple/10' },
  governance:  { label: 'Governance',  icon: <Settings size={12} />,  color: 'text-yellow-400 border-yellow-400/30 bg-yellow-400/10' },
  general:     { label: 'General',     icon: <Users size={12} />,     color: 'text-slate-400 border-slate-400/30 bg-slate-400/10' },
}

const STATUS_META: Record<string, { icon: React.ReactNode; style: string; label: string }> = {
  active:   { icon: <Clock size={11} />,        style: 'text-cyan border-cyan/20 bg-cyan/10',                 label: 'Active' },
  passed:   { icon: <CheckCircle size={11} />,  style: 'text-green border-green/20 bg-green/10',              label: 'Passed' },
  rejected: { icon: <XCircle size={11} />,      style: 'text-red-400 border-red-400/20 bg-red-400/10',       label: 'Rejected' },
  expired:  { icon: <AlertCircle size={11} />,  style: 'text-slate-400 border-slate-400/20 bg-slate-400/10', label: 'Expired' },
  vetoed:   { icon: <Shield size={11} />,       style: 'text-orange-400 border-orange-400/20 bg-orange-400/10', label: 'Vetoed' },
}

const PARAM_CATEGORIES = ['all', 'allocation', 'risk', 'agents', 'governance']
const PROPOSAL_FILTERS = ['all', 'active', 'passed', 'rejected', 'expired', 'vetoed']

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------
function StatCard({ label, value, sub, color = 'text-white' }: { label: string; value: string | number; sub?: string; color?: string }) {
  return (
    <div className="card py-3 px-4">
      <p className="text-xs text-slate-500 mb-1">{label}</p>
      <p className={`text-xl font-bold font-mono ${color}`}>{value}</p>
      {sub && <p className="text-xs text-slate-600 mt-0.5">{sub}</p>}
    </div>
  )
}

function QuorumBar({ progress, needed, reached }: { progress: number; needed: number; reached: boolean }) {
  return (
    <div className="mt-2">
      <div className="flex justify-between text-xs text-slate-500 mb-1">
        <span>Quorum {progress.toFixed(1)}% / {needed}% needed</span>
        {reached
          ? <span className="text-green flex items-center gap-1"><CheckCircle size={10} /> Reached</span>
          : <span className="text-slate-500">Not reached</span>}
      </div>
      <div className="h-1 bg-border rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${reached ? 'bg-green' : 'bg-slate-500'}`}
          style={{ width: `${Math.min(progress / needed * 100, 100)}%` }}
        />
      </div>
    </div>
  )
}

function VoteBar({ forPct, againstPct }: { forPct: number; againstPct: number }) {
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-slate-400">
        <span className="text-green">For {forPct.toFixed(1)}%</span>
        <span className="text-red-400">Against {againstPct.toFixed(1)}%</span>
      </div>
      <div className="h-2 bg-border rounded-full overflow-hidden flex">
        <div className="h-full bg-green transition-all" style={{ width: `${forPct}%` }} />
        <div className="h-full bg-red-500 transition-all" style={{ width: `${againstPct}%` }} />
      </div>
    </div>
  )
}

function ProposalCard({
  proposal, onVote, votedIds, isAdmin, onVeto,
}: {
  proposal: GovernanceProposal
  onVote: (id: string, support: boolean) => void
  votedIds: Set<string>
  isAdmin: boolean
  onVeto: (id: string, reason: string) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const [showVetoInput, setShowVetoInput] = useState(false)
  const [vetoReason, setVetoReason] = useState('')
  const status = STATUS_META[proposal.status] ?? STATUS_META.expired
  const cat = CATEGORY_META[proposal.category] ?? CATEGORY_META.general
  const hasVoted = votedIds.has(proposal.id)
  const canVeto = isAdmin && proposal.status !== 'vetoed'

  const submitVeto = () => {
    onVeto(proposal.id, vetoReason)
    setShowVetoInput(false)
    setVetoReason('')
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      className="border border-border rounded-xl p-4 hover:border-slate-600 transition-all"
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1.5 flex-wrap">
            <span className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border ${cat.color}`}>
              {cat.icon} {cat.label}
            </span>
            <span className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border ${status.style}`}>
              {status.icon} {status.label}
            </span>
            {proposal.status === 'passed' && proposal.param_name && (
              <span className="text-xs text-green/70 font-mono">✓ Executed</span>
            )}
          </div>
          <p className="text-sm text-white font-medium leading-snug">{proposal.title}</p>
        </div>
        <button onClick={() => setExpanded(e => !e)} className="text-slate-500 hover:text-slate-300 mt-1 shrink-0">
          {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </button>
      </div>

      {/* Vote bars */}
      <VoteBar forPct={proposal.votes_for_pct} againstPct={proposal.votes_against_pct} />
      <QuorumBar progress={proposal.quorum_progress} needed={proposal.quorum_pct_needed} reached={proposal.quorum_reached} />

      {/* Expanded detail */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="mt-3 pt-3 border-t border-border space-y-2">
              <p className="text-xs text-slate-400 leading-relaxed">{proposal.description}</p>
              {proposal.param_name && (
                <div className="flex gap-4 text-xs font-mono">
                  <span className="text-slate-500">
                    Current: <span className="text-white">{proposal.current_value} {proposal.param_meta?.unit}</span>
                  </span>
                  <span className="text-slate-500">
                    Proposed: <span className="text-cyan">{proposal.proposed_value} {proposal.param_meta?.unit}</span>
                  </span>
                </div>
              )}
              <div className="flex gap-4 text-xs text-slate-600">
                <span>By: <span className="font-mono">{proposal.proposer.slice(0, 10)}…</span></span>
                <span>Created: {proposal.created_date}</span>
                <span>Total votes: {proposal.total_votes.toLocaleString()}</span>
              </div>
              {(proposal as any).veto_reason && (
                <div className="mt-2 p-2 rounded-lg bg-orange-400/10 border border-orange-400/20">
                  <p className="text-xs text-orange-400 font-medium">Admin Veto</p>
                  <p className="text-xs text-slate-400 mt-0.5">{(proposal as any).veto_reason || 'No reason given'}</p>
                  {(proposal as any).veto_reverted && (
                    <p className="text-xs text-orange-300 mt-0.5">⚠ Parameter change was reverted</p>
                  )}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Vote actions + veto */}
      <div className="mt-3 space-y-2">
        <div className="flex items-center justify-between">
          <p className="text-xs text-slate-600">Ends: {proposal.end_date}</p>
          <div className="flex items-center gap-2">
            {proposal.status === 'active' && (
              hasVoted
                ? <span className="text-xs text-slate-500 italic">You voted</span>
                : (
                  <>
                    <button
                      onClick={() => onVote(proposal.id, true)}
                      className="px-3 py-1 rounded-lg text-xs font-medium bg-green/10 text-green border border-green/20 hover:bg-green/20 transition-all"
                    >
                      Vote For
                    </button>
                    <button
                      onClick={() => onVote(proposal.id, false)}
                      className="px-3 py-1 rounded-lg text-xs font-medium bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20 transition-all"
                    >
                      Vote Against
                    </button>
                  </>
                )
            )}
            {canVeto && (
              <button
                onClick={() => setShowVetoInput(v => !v)}
                className={`px-3 py-1 rounded-lg text-xs font-medium border transition-all flex items-center gap-1 ${
                  showVetoInput
                    ? 'bg-orange-400/20 text-orange-300 border-orange-400/30'
                    : 'bg-orange-400/10 text-orange-400 border-orange-400/20 hover:bg-orange-400/20'
                }`}
              >
                <Shield size={10} /> {showVetoInput ? 'Cancel' : 'Admin Veto'}
              </button>
            )}
          </div>
        </div>

        {/* Inline veto reason input */}
        <AnimatePresence>
          {showVetoInput && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="overflow-hidden"
            >
              <div className="flex gap-2 pt-1">
                <input
                  value={vetoReason}
                  onChange={e => setVetoReason(e.target.value)}
                  placeholder="Veto reason (optional)…"
                  className="flex-1 bg-slate-900 border border-orange-400/30 rounded-lg px-3 py-1.5 text-xs text-slate-100 placeholder-slate-600 focus:outline-none focus:border-orange-400/60"
                  onKeyDown={e => e.key === 'Enter' && submitVeto()}
                />
                <button
                  onClick={submitVeto}
                  className="px-3 py-1.5 rounded-lg text-xs font-medium bg-orange-400 text-black hover:bg-orange-300 transition-all"
                >
                  Confirm Veto
                </button>
              </div>
              {proposal.status === 'passed' && (
                <p className="text-xs text-orange-400/70 mt-1">
                  ⚠ This proposal already passed — vetoing will revert the parameter change.
                </p>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  )
}

// ---------------------------------------------------------------------------
// Proposal creation modal
// ---------------------------------------------------------------------------
function NewProposalModal({ params, onClose, onSubmit }: {
  params: Record<string, any>
  onClose: () => void
  onSubmit: (data: any) => void
}) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [category, setCategory] = useState('general')
  const [paramName, setParamName] = useState('')
  const [proposedValue, setProposedValue] = useState('')
  const [duration, setDuration] = useState(5)
  const [isParam, setIsParam] = useState(false)

  const selectedParam = paramName ? params[paramName] : null

  const handleSubmit = () => {
    if (!title.trim() || !description.trim()) return
    onSubmit({
      title: title.trim(),
      description: description.trim(),
      category,
      param_name: isParam && paramName ? paramName : undefined,
      proposed_value: isParam && proposedValue ? parseFloat(proposedValue) : undefined,
      proposer: VOTER_ADDRESS,
      duration_days: duration,
    })
    onClose()
  }

  const paramsByCategory = useMemo(() => {
    const grouped: Record<string, { key: string; meta: any }[]> = {}
    Object.entries(params).forEach(([key, meta]) => {
      const cat = meta.category || 'general'
      if (!grouped[cat]) grouped[cat] = []
      grouped[cat].push({ key, meta })
    })
    return grouped
  }, [params])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="bg-slate-950 border border-border rounded-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto"
      >
        <div className="flex items-center justify-between p-5 border-b border-border">
          <h2 className="text-sm font-semibold text-white">New Proposal</h2>
          <button onClick={onClose} className="text-slate-500 hover:text-white"><X size={16} /></button>
        </div>

        <div className="p-5 space-y-4">
          {/* Title */}
          <div>
            <label className="text-xs text-slate-400 mb-1.5 block">Title</label>
            <input
              value={title}
              onChange={e => setTitle(e.target.value)}
              placeholder="Short, descriptive proposal title"
              className="w-full bg-slate-900 border border-border rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-cyan/50"
            />
          </div>

          {/* Description */}
          <div>
            <label className="text-xs text-slate-400 mb-1.5 block">Description</label>
            <textarea
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="Explain the rationale, expected impact, and any risks..."
              rows={4}
              className="w-full bg-slate-900 border border-border rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-cyan/50 resize-none"
            />
          </div>

          {/* Category */}
          <div>
            <label className="text-xs text-slate-400 mb-1.5 block">Category</label>
            <div className="flex flex-wrap gap-2">
              {Object.entries(CATEGORY_META).map(([key, meta]) => (
                <button
                  key={key}
                  onClick={() => setCategory(key)}
                  className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border transition-all ${
                    category === key ? meta.color : 'text-slate-500 border-border hover:border-slate-500'
                  }`}
                >
                  {meta.icon} {meta.label}
                </button>
              ))}
            </div>
          </div>

          {/* Parameter change toggle */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsParam(v => !v)}
              className={`w-9 h-5 rounded-full transition-all relative ${isParam ? 'bg-cyan' : 'bg-border'}`}
            >
              <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all ${isParam ? 'left-4' : 'left-0.5'}`} />
            </button>
            <span className="text-xs text-slate-400">This proposal changes a protocol parameter</span>
          </div>

          {/* Parameter selector */}
          {isParam && (
            <div className="space-y-3 p-3 bg-slate-900 rounded-xl border border-border">
              <div>
                <label className="text-xs text-slate-400 mb-1.5 block">Parameter</label>
                <select
                  value={paramName}
                  onChange={e => { setParamName(e.target.value); setProposedValue('') }}
                  className="w-full bg-slate-900 border border-border rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-cyan/50"
                >
                  <option value="">Select parameter…</option>
                  {Object.entries(paramsByCategory).map(([cat, items]) => (
                    <optgroup key={cat} label={cat.toUpperCase()}>
                      {items.map(({ key, meta }) => (
                        <option key={key} value={key}>{meta.label}</option>
                      ))}
                    </optgroup>
                  ))}
                </select>
              </div>

              {selectedParam && (
                <div>
                  <div className="flex justify-between text-xs text-slate-500 mb-1">
                    <span>Current: <span className="text-white font-mono">{selectedParam.value} {selectedParam.unit}</span></span>
                    <span>Range: {selectedParam.min} – {selectedParam.max}</span>
                  </div>
                  <label className="text-xs text-slate-400 mb-1.5 block">Proposed Value</label>
                  <input
                    type="number"
                    value={proposedValue}
                    onChange={e => setProposedValue(e.target.value)}
                    min={selectedParam.min}
                    max={selectedParam.max}
                    step={selectedParam.step}
                    placeholder={`e.g. ${selectedParam.value}`}
                    className="w-full bg-slate-900 border border-border rounded-lg px-3 py-2 text-sm text-slate-100 font-mono focus:outline-none focus:border-cyan/50"
                  />
                </div>
              )}
            </div>
          )}

          {/* Duration */}
          <div>
            <div className="flex justify-between text-xs mb-1.5">
              <span className="text-slate-400">Voting Duration</span>
              <span className="text-cyan font-mono">{duration} days</span>
            </div>
            <input
              type="range" min={1} max={14} step={1} value={duration}
              onChange={e => setDuration(parseInt(e.target.value))}
              className="w-full accent-cyan"
            />
          </div>

          <button
            onClick={handleSubmit}
            disabled={!title.trim() || !description.trim()}
            className="w-full py-2.5 rounded-xl text-sm font-medium bg-cyan/10 text-cyan border border-cyan/20 hover:bg-cyan/20 transition-all disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            <Vote size={13} /> Submit Proposal
          </button>
        </div>
      </motion.div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function Governance() {
  const [filter, setFilter] = useState<string>('all')
  const [paramCategory, setParamCategory] = useState<string>('all')
  const [showModal, setShowModal] = useState(false)
  const [votedIds, setVotedIds] = useState<Set<string>>(new Set())
  const [toast, setToast] = useState<string | null>(null)

  const { data: proposals = [], isLoading } = useGovernanceProposals()
  const { data: params = {} } = useGovernanceParams()
  const { data: stats } = useGovernanceStats()
  const { data: suggestions } = useGovernanceSuggestions()
  const castVote = useCastVote()
  const createProposal = useCreateProposal()
  const vetoProposal = useVetoProposal()

  const isAdmin = VOTER_ADDRESS.toLowerCase() === ADMIN_ADDRESS.toLowerCase()

  const showToast = (msg: string) => {
    setToast(msg)
    setTimeout(() => setToast(null), 3000)
  }

  const handleVote = (proposalId: string, support: boolean) => {
    castVote.mutate(
      { proposal_id: proposalId, voter: VOTER_ADDRESS, support, weight: 100 },
      {
        onSuccess: () => {
          setVotedIds(prev => new Set([...prev, proposalId]))
          showToast(support ? 'Voted For ✓' : 'Voted Against ✓')
        },
        onError: (e: any) => showToast(e?.response?.data?.detail ?? 'Vote failed'),
      }
    )
  }

  const handleVeto = (proposalId: string, reason: string) => {
    vetoProposal.mutate(
      { proposal_id: proposalId, admin_address: ADMIN_ADDRESS, reason },
      {
        onSuccess: () => showToast('Proposal vetoed by admin ✓'),
        onError: (e: any) => showToast(e?.response?.data?.detail ?? 'Veto failed'),
      }
    )
  }

  const handleCreateProposal = (data: any) => {
    createProposal.mutate(data, {
      onSuccess: () => showToast('Proposal submitted ✓'),
      onError: () => showToast('Failed to submit proposal'),
    })
  }

  const filteredProposals = useMemo(() =>
    filter === 'all' ? proposals : proposals.filter(p => p.status === filter),
    [proposals, filter]
  )

  const filteredParams = useMemo(() =>
    Object.entries(params).filter(([, meta]) =>
      paramCategory === 'all' || meta.category === paramCategory
    ),
    [params, paramCategory]
  )

  return (
    <div className="space-y-5">
      {/* Toast */}
      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="fixed top-4 right-4 z-50 bg-surface border border-border rounded-xl px-4 py-2.5 text-sm text-white shadow-xl"
          >
            {toast}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Modal */}
      {showModal && (
        <NewProposalModal
          params={params}
          onClose={() => setShowModal(false)}
          onSubmit={handleCreateProposal}
        />
      )}

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Governance DAO</h1>
          <p className="text-slate-500 text-sm mt-0.5">On-chain parameter control, proposals, and community voting</p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium bg-cyan/10 text-cyan border border-cyan/20 hover:bg-cyan/20 transition-all"
        >
          <Plus size={13} /> New Proposal
        </button>
      </div>

      {/* Stats row */}
      {stats && (
        <div className="grid grid-cols-4 gap-3">
          <StatCard label="Total Proposals" value={stats.total_proposals} />
          <StatCard label="Active" value={stats.active} color="text-cyan" />
          <StatCard label="Passed & Executed" value={stats.passed} color="text-green" sub={`${stats.params_executed} params changed`} />
          <StatCard label="Total Votes Cast" value={stats.total_votes_cast.toLocaleString()} color="text-purple" />
        </div>
      )}

      {suggestions && (
        <div className="card border border-purple/20">
          <div className="flex items-start justify-between gap-4 mb-3">
            <div>
              <h3 className="text-sm font-semibold text-white">AI-Assisted Governance</h3>
              <p className="text-xs text-slate-500 mt-1">
                Regime-aware governance guidance for the current market state: <span className="text-cyan font-mono">{suggestions.regime}</span>
              </p>
            </div>
            <div className="text-right">
              <p className="text-xs text-slate-500">Predicted Pass Rate</p>
              <p className="text-lg font-bold font-mono text-purple">{Math.round(suggestions.predictive_vote_outcome.pass_probability * 100)}%</p>
              <p className="text-xs text-slate-600">Bias: {suggestions.predictive_vote_outcome.delegation_bias}</p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {suggestions.suggestions.map(suggestion => (
              <div key={suggestion.title} className="rounded-xl border border-border bg-slate-900/50 p-3">
                <div className="flex items-center justify-between mb-1.5">
                  <p className="text-sm text-white">{suggestion.title}</p>
                  <span className="text-xs px-2 py-0.5 rounded-full border bg-cyan/10 text-cyan border-cyan/20">{suggestion.impact}</span>
                </div>
                <p className="text-xs text-slate-500 leading-relaxed">{suggestion.reason}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-3 gap-4">
        {/* Proposals list */}
        <div className="col-span-2 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white">Proposals</h3>
            <div className="flex gap-1">
              {PROPOSAL_FILTERS.map(f => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={`text-xs px-2.5 py-1 rounded-lg capitalize transition-all ${
                    filter === f
                      ? 'bg-cyan/10 text-cyan border border-cyan/20'
                      : 'text-slate-500 hover:text-slate-300'
                  }`}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>

          {isLoading && (
            <div className="space-y-3">
              {[1, 2, 3].map(i => (
                <div key={i} className="h-28 bg-surface rounded-xl animate-pulse border border-border" />
              ))}
            </div>
          )}

          {!isLoading && filteredProposals.length === 0 && (
            <div className="card text-center py-10 text-slate-500 text-sm">No proposals found</div>
          )}

          <div className="space-y-3">
            {filteredProposals.map((p, i) => (
              <motion.div key={p.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.05 }}>
                <ProposalCard proposal={p} onVote={handleVote} votedIds={votedIds} isAdmin={isAdmin} onVeto={handleVeto} />
              </motion.div>
            ))}
          </div>
        </div>

        {/* Right panel: live params */}
        <div className="space-y-3">
          <div className="card space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-white">Protocol Parameters</h3>
              <TrendingUp size={13} className="text-slate-500" />
            </div>
            <p className="text-xs text-slate-500 -mt-2">Live values — changed by passed proposals</p>

            {/* Category filter */}
            <div className="flex flex-wrap gap-1">
              {PARAM_CATEGORIES.map(c => (
                <button
                  key={c}
                  onClick={() => setParamCategory(c)}
                  className={`text-xs px-2 py-0.5 rounded-md capitalize transition-all ${
                    paramCategory === c
                      ? 'bg-purple/10 text-purple border border-purple/20'
                      : 'text-slate-500 hover:text-slate-300'
                  }`}
                >
                  {c}
                </button>
              ))}
            </div>

            <div className="space-y-3 max-h-[520px] overflow-y-auto pr-1">
              {filteredParams.map(([key, meta]) => {
                const pct = ((meta.value - meta.min) / (meta.max - meta.min)) * 100
                const cat = CATEGORY_META[meta.category] ?? CATEGORY_META.general
                return (
                  <div key={key}>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-slate-400 flex items-center gap-1">
                        <span className={meta.category === 'risk' ? 'text-red-400' : meta.category === 'allocation' ? 'text-cyan' : meta.category === 'agents' ? 'text-purple' : 'text-yellow-400'}>
                          {cat.icon}
                        </span>
                        {meta.label}
                      </span>
                      <span className="font-mono text-white">{meta.value}{meta.unit}</span>
                    </div>
                    <div className="h-1.5 bg-border rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${
                          meta.category === 'risk' ? 'bg-red-400' :
                          meta.category === 'allocation' ? 'bg-cyan' :
                          meta.category === 'agents' ? 'bg-purple' : 'bg-yellow-400'
                        }`}
                        style={{ width: `${Math.max(4, pct)}%` }}
                      />
                    </div>
                    <div className="flex justify-between text-xs text-slate-700 mt-0.5">
                      <span>{meta.min}</span><span>{meta.max}</span>
                    </div>
                  </div>
                )
              })}
            </div>

            <button
              onClick={() => setShowModal(true)}
              className="w-full py-2 rounded-lg text-xs font-medium bg-purple/10 text-purple border border-purple/20 hover:bg-purple/20 transition-all flex items-center justify-center gap-1.5"
            >
              <Vote size={11} /> Propose Parameter Change
            </button>
          </div>

          {/* Connected wallet info */}
          <div className="card space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-semibold text-slate-400">Your Wallet</h3>
              {isAdmin && (
                <span className="flex items-center gap-1 text-xs text-orange-400 border border-orange-400/20 bg-orange-400/10 px-2 py-0.5 rounded-full">
                  <Shield size={9} /> Admin
                </span>
              )}
            </div>
            <p className="text-xs font-mono text-white">{VOTER_ADDRESS.slice(0, 14)}…{VOTER_ADDRESS.slice(-6)}</p>
            <div className="flex justify-between text-xs">
              <span className="text-slate-500">Voting Power</span>
              <span className="text-cyan font-mono">100 DAC</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-slate-500">Votes Cast</span>
              <span className="text-white font-mono">{votedIds.size}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
