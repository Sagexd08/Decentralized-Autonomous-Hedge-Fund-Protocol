"use client"

import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { SectionHeader } from "@/components/dacap/section-header"
import { StatusBadge } from "@/components/dacap/status-badge"
import { MetricCard } from "@/components/dacap/metric-card"
import { ProposalCard } from "@/components/dacap/proposal-card"
import {
  Vote,
  Users,
  Clock,
  CheckCircle,
  XCircle,
  ArrowRight,
  Plus,
  TrendingUp,
  Settings,
  Shield,
  FileText,
} from "lucide-react"

const proposals = [
  {
    id: "DIP-047",
    title: "Increase Learning Rate Parameter",
    description: "Proposal to adjust the allocation engine learning rate (eta) from 0.15 to 0.18 for faster adaptation to market regime changes.",
    status: "active" as const,
    forPercentage: 67.3,
    againstPercentage: 32.7,
    quorum: 45,
    quorumRequired: 40,
    endTime: "2d 14h",
    category: "Parameters",
    author: "0x7a3f...e2c1",
  },
  {
    id: "DIP-046",
    title: "Add Solana DEX Integration",
    description: "Expand protocol capabilities to include Solana-based DEX strategies via cross-chain bridging infrastructure.",
    status: "active" as const,
    forPercentage: 82.1,
    againstPercentage: 17.9,
    quorum: 52,
    quorumRequired: 40,
    endTime: "4d 6h",
    category: "Integration",
    author: "0x2b9c...f847",
  },
  {
    id: "DIP-045",
    title: "Reduce Conservative Pool Cap",
    description: "Lower the maximum allocation to Conservative risk pool from 40% to 35% to enable more aggressive strategies.",
    status: "passed" as const,
    forPercentage: 71.2,
    againstPercentage: 28.8,
    quorum: 58,
    quorumRequired: 40,
    endTime: "Ended",
    category: "Risk",
    author: "0x5d1e...a392",
  },
  {
    id: "DIP-044",
    title: "Agent Staking Requirement Increase",
    description: "Increase minimum stake requirement for agent registration from 10,000 to 15,000 tokens.",
    status: "failed" as const,
    forPercentage: 34.5,
    againstPercentage: 65.5,
    quorum: 61,
    quorumRequired: 40,
    endTime: "Ended",
    category: "Agents",
    author: "0x9f3a...c219",
  },
  {
    id: "DIP-043",
    title: "Emergency Pause Threshold",
    description: "Lower the emergency pause trigger from 15% drawdown to 12% for enhanced capital protection.",
    status: "passed" as const,
    forPercentage: 89.2,
    againstPercentage: 10.8,
    quorum: 72,
    quorumRequired: 40,
    endTime: "Ended",
    category: "Risk",
    author: "0x1c4d...8726",
  },
]

const parameters = [
  { name: "Learning Rate (eta)", value: "0.15", category: "Allocation", lastChange: "14d ago" },
  { name: "Max Agent Allocation", value: "25%", category: "Risk", lastChange: "30d ago" },
  { name: "Slashing Threshold", value: "8%", category: "Risk", lastChange: "45d ago" },
  { name: "Quorum Requirement", value: "40%", category: "Governance", lastChange: "60d ago" },
  { name: "Proposal Duration", value: "7 days", category: "Governance", lastChange: "90d ago" },
  { name: "Min Agent Stake", value: "10,000", category: "Agents", lastChange: "30d ago" },
  { name: "Confidence Threshold", value: "0.75", category: "Intelligence", lastChange: "21d ago" },
  { name: "Rebalance Frequency", value: "4 hours", category: "Allocation", lastChange: "7d ago" },
]

const recentVotes = [
  { proposal: "DIP-047", voter: "0x7a3f...e2c1", vote: "for", power: "125,000", time: "2h ago" },
  { proposal: "DIP-047", voter: "0x2b9c...f847", vote: "against", power: "45,000", time: "4h ago" },
  { proposal: "DIP-046", voter: "0x5d1e...a392", vote: "for", power: "89,000", time: "6h ago" },
  { proposal: "DIP-047", voter: "0x9f3a...c219", vote: "for", power: "67,500", time: "8h ago" },
  { proposal: "DIP-046", voter: "0x1c4d...8726", vote: "for", power: "234,000", time: "12h ago" },
]

export default function GovernancePage() {
  const activeProposals = proposals.filter(p => p.status === "active")
  const pastProposals = proposals.filter(p => p.status !== "active")

  return (
    <div className="min-h-screen bg-transparent">
      <div className="max-w-[1800px] mx-auto px-4 md:px-6 py-8">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
          <SectionHeader
            eyebrow="Governance"
            title="Protocol DAO"
            description="Participate in protocol governance through voting and proposal creation."
            className="mb-0"
          />
          <div className="flex items-center gap-3">
            <Button variant="outline" size="sm">
              <FileText className="w-4 h-4 mr-2" />
              View Constitution
            </Button>
            <Button size="sm" className="glow-cyan">
              <Plus className="w-4 h-4 mr-2" />
              Create Proposal
            </Button>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <MetricCard
            title="Total Proposals"
            value="47"
            change={{ value: 3, label: "this month" }}
            icon={FileText}
          />
          <MetricCard
            title="Active Proposals"
            value="2"
            icon={Vote}
          />
          <MetricCard
            title="Total Voters"
            value="1,247"
            change={{ value: 12.3, label: "vs last month" }}
            icon={Users}
          />
          <MetricCard
            title="Voting Power"
            value="2.4M"
            subtitle="Total staked"
            icon={TrendingUp}
          />
        </div>

        {/* Main Content */}
        <div className="grid lg:grid-cols-3 gap-6">
          {/* Proposals Column */}
          <div className="lg:col-span-2">
            <Tabs defaultValue="active" className="w-full">
              <TabsList className="mb-6">
                <TabsTrigger value="active" className="flex items-center gap-2">
                  <Clock className="w-4 h-4" />
                  Active ({activeProposals.length})
                </TabsTrigger>
                <TabsTrigger value="passed" className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4" />
                  Passed
                </TabsTrigger>
                <TabsTrigger value="failed" className="flex items-center gap-2">
                  <XCircle className="w-4 h-4" />
                  Failed
                </TabsTrigger>
                <TabsTrigger value="all">All</TabsTrigger>
              </TabsList>

              <TabsContent value="active" className="space-y-4">
                {activeProposals.map((proposal) => (
                  <ProposalCard key={proposal.id} proposal={proposal} />
                ))}
              </TabsContent>

              <TabsContent value="passed" className="space-y-4">
                {pastProposals.filter(p => p.status === "passed").map((proposal) => (
                  <ProposalCard key={proposal.id} proposal={proposal} />
                ))}
              </TabsContent>

              <TabsContent value="failed" className="space-y-4">
                {pastProposals.filter(p => p.status === "failed").map((proposal) => (
                  <ProposalCard key={proposal.id} proposal={proposal} />
                ))}
              </TabsContent>

              <TabsContent value="all" className="space-y-4">
                {proposals.map((proposal) => (
                  <ProposalCard key={proposal.id} proposal={proposal} />
                ))}
              </TabsContent>
            </Tabs>
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Protocol Parameters */}
            <div className="glass rounded-xl p-6 border border-border/30">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold text-foreground flex items-center gap-2">
                  <Settings className="w-4 h-4 text-primary" />
                  Protocol Parameters
                </h3>
              </div>

              <div className="space-y-3">
                {parameters.slice(0, 6).map((param) => (
                  <div key={param.name} className="flex items-center justify-between py-2 border-b border-border/20 last:border-0">
                    <div>
                      <div className="text-sm text-foreground">{param.name}</div>
                      <div className="text-xs text-muted-foreground">{param.category}</div>
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-mono text-primary">{param.value}</div>
                      <div className="text-xs text-muted-foreground">{param.lastChange}</div>
                    </div>
                  </div>
                ))}
              </div>

              <Button variant="ghost" size="sm" className="w-full mt-4">
                View All Parameters
                <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </div>

            {/* Recent Votes */}
            <div className="glass rounded-xl p-6 border border-border/30">
              <h3 className="font-semibold text-foreground mb-4 flex items-center gap-2">
                <Vote className="w-4 h-4 text-primary" />
                Recent Votes
              </h3>

              <div className="space-y-3">
                {recentVotes.map((vote, i) => (
                  <div key={i} className="flex items-center justify-between py-2 border-b border-border/20 last:border-0">
                    <div className="flex items-center gap-3">
                      <div className={`w-2 h-2 rounded-full ${vote.vote === "for" ? "bg-accent" : "bg-destructive"}`} />
                      <div>
                        <div className="text-sm text-foreground">{vote.voter}</div>
                        <div className="text-xs text-muted-foreground">{vote.proposal}</div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-mono text-muted-foreground">{vote.power}</div>
                      <div className="text-xs text-muted-foreground">{vote.time}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Your Voting Power */}
            <div className="glass rounded-xl p-6 border border-border/30">
              <h3 className="font-semibold text-foreground mb-4 flex items-center gap-2">
                <Shield className="w-4 h-4 text-primary" />
                Your Voting Power
              </h3>

              <div className="text-center py-4">
                <div className="text-3xl font-bold text-foreground mb-1">0</div>
                <div className="text-sm text-muted-foreground mb-4">Voting Power</div>
                <Button className="w-full glow-cyan">
                  Connect Wallet
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
