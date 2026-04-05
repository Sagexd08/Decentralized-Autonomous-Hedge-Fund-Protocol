"use client"

import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { SectionHeader } from "@/components/dacap/section-header"
import { StatusBadge } from "@/components/dacap/status-badge"
import { ContractCard } from "@/components/dacap/contract-card"
import {
  FileCode,
  Shield,
  ExternalLink,
  Copy,
  CheckCircle,
  AlertTriangle,
  Lock,
  Layers,
  Brain,
  Vote,
  Wallet,
  Activity,
} from "lucide-react"

const contracts = [
  {
    name: "CapitalVault",
    address: "0x7a3f...e2c1",
    description: "Core capital custody contract. Holds all protocol assets with multi-sig governance controls.",
    version: "2.1.0",
    audited: true,
    auditor: "Trail of Bits",
    tvl: "$49.3M",
    category: "core",
    icon: Lock,
    functions: ["deposit()", "withdraw()", "allocateToAgent()", "revokeAllocation()"],
    lastUpgrade: "45 days ago",
    chain: "Ethereum",
  },
  {
    name: "AllocationEngine",
    address: "0x2b9c...f847",
    description: "Implements multiplicative weights algorithm for dynamic capital allocation across agents.",
    version: "1.8.3",
    audited: true,
    auditor: "OpenZeppelin",
    tvl: "N/A",
    category: "core",
    icon: Layers,
    functions: ["updateWeights()", "calculateAllocation()", "rebalance()", "getAgentWeight()"],
    lastUpgrade: "21 days ago",
    chain: "Ethereum",
  },
  {
    name: "AgentRegistry",
    address: "0x5d1e...a392",
    description: "Manages agent registration, staking, and performance tracking.",
    version: "1.5.2",
    audited: true,
    auditor: "Certik",
    tvl: "$12.4M",
    category: "agents",
    icon: Brain,
    functions: ["registerAgent()", "stake()", "slash()", "updatePerformance()"],
    lastUpgrade: "60 days ago",
    chain: "Ethereum",
  },
  {
    name: "RiskPoolManager",
    address: "0x9f3a...c219",
    description: "Manages risk pool tiers with volatility caps and drawdown enforcement.",
    version: "2.0.1",
    audited: true,
    auditor: "Trail of Bits",
    tvl: "$49.3M",
    category: "risk",
    icon: Shield,
    functions: ["createPool()", "depositToPool()", "enforceDrawdown()", "getPoolMetrics()"],
    lastUpgrade: "30 days ago",
    chain: "Ethereum",
  },
  {
    name: "GovernanceDAO",
    address: "0x1c4d...8726",
    description: "DAO governance with proposal creation, voting, and parameter execution.",
    version: "1.3.0",
    audited: true,
    auditor: "OpenZeppelin",
    tvl: "N/A",
    category: "governance",
    icon: Vote,
    functions: ["propose()", "vote()", "execute()", "delegate()"],
    lastUpgrade: "90 days ago",
    chain: "Ethereum",
  },
  {
    name: "Treasury",
    address: "0x4e2f...b193",
    description: "Protocol treasury for fee collection and DAO-controlled spending.",
    version: "1.1.0",
    audited: true,
    auditor: "Certik",
    tvl: "$2.1M",
    category: "treasury",
    icon: Wallet,
    functions: ["collectFees()", "distribute()", "requestFunding()"],
    lastUpgrade: "120 days ago",
    chain: "Ethereum",
  },
  {
    name: "PerformanceOracle",
    address: "0x8b7d...9a42",
    description: "Reports agent performance metrics from off-chain intelligence layer.",
    version: "1.4.0",
    audited: false,
    auditor: null,
    tvl: "N/A",
    category: "oracle",
    icon: Activity,
    functions: ["reportPerformance()", "getAgentSharpe()", "getDrawdown()"],
    lastUpgrade: "14 days ago",
    chain: "Ethereum",
  },
]

const auditReports = [
  { auditor: "Trail of Bits", date: "Jan 2024", scope: "CapitalVault, RiskPoolManager", issues: "2 Medium, 4 Low", status: "Resolved" },
  { auditor: "OpenZeppelin", date: "Dec 2023", scope: "AllocationEngine, GovernanceDAO", issues: "1 High, 3 Medium", status: "Resolved" },
  { auditor: "Certik", date: "Nov 2023", scope: "AgentRegistry, Treasury", issues: "5 Low", status: "Resolved" },
]

export default function ContractsPage() {
  return (
    <div className="min-h-screen bg-transparent">
      <div className="max-w-[1800px] mx-auto px-4 md:px-6 py-8">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
          <SectionHeader
            eyebrow="Smart Contracts"
            title="Protocol Infrastructure"
            description="On-chain smart contract architecture powering DACAP protocol."
            className="mb-0"
          />
          <div className="flex items-center gap-3">
            <Button variant="outline" size="sm">
              <ExternalLink className="w-4 h-4 mr-2" />
              View on Etherscan
            </Button>
            <Button variant="outline" size="sm">
              <FileCode className="w-4 h-4 mr-2" />
              GitHub
            </Button>
          </div>
        </div>

        {/* Security Overview */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <div className="glass rounded-xl p-6 border border-border/30">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-10 h-10 rounded-lg bg-accent/20 flex items-center justify-center">
                <CheckCircle className="w-5 h-5 text-accent" />
              </div>
              <div>
                <div className="text-2xl font-bold text-foreground">6/7</div>
                <div className="text-sm text-muted-foreground">Audited</div>
              </div>
            </div>
          </div>
          <div className="glass rounded-xl p-6 border border-border/30">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-10 h-10 rounded-lg bg-primary/20 flex items-center justify-center">
                <Shield className="w-5 h-5 text-primary" />
              </div>
              <div>
                <div className="text-2xl font-bold text-foreground">3</div>
                <div className="text-sm text-muted-foreground">Audit Firms</div>
              </div>
            </div>
          </div>
          <div className="glass rounded-xl p-6 border border-border/30">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-10 h-10 rounded-lg bg-chart-3/20 flex items-center justify-center">
                <Lock className="w-5 h-5 text-chart-3" />
              </div>
              <div>
                <div className="text-2xl font-bold text-foreground">$49.3M</div>
                <div className="text-sm text-muted-foreground">TVL Secured</div>
              </div>
            </div>
          </div>
          <div className="glass rounded-xl p-6 border border-border/30">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-10 h-10 rounded-lg bg-accent/20 flex items-center justify-center">
                <Activity className="w-5 h-5 text-accent" />
              </div>
              <div>
                <div className="text-2xl font-bold text-foreground">0</div>
                <div className="text-sm text-muted-foreground">Security Incidents</div>
              </div>
            </div>
          </div>
        </div>

        {/* Contracts Grid */}
        <Tabs defaultValue="all" className="mb-8">
          <TabsList className="mb-6">
            <TabsTrigger value="all">All Contracts</TabsTrigger>
            <TabsTrigger value="core">Core</TabsTrigger>
            <TabsTrigger value="agents">Agents</TabsTrigger>
            <TabsTrigger value="risk">Risk</TabsTrigger>
            <TabsTrigger value="governance">Governance</TabsTrigger>
          </TabsList>

          <TabsContent value="all">
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
              {contracts.map((contract) => (
                <ContractCard key={contract.address} contract={contract} />
              ))}
            </div>
          </TabsContent>

          <TabsContent value="core">
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
              {contracts.filter(c => c.category === "core").map((contract) => (
                <ContractCard key={contract.address} contract={contract} />
              ))}
            </div>
          </TabsContent>

          <TabsContent value="agents">
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
              {contracts.filter(c => c.category === "agents").map((contract) => (
                <ContractCard key={contract.address} contract={contract} />
              ))}
            </div>
          </TabsContent>

          <TabsContent value="risk">
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
              {contracts.filter(c => c.category === "risk").map((contract) => (
                <ContractCard key={contract.address} contract={contract} />
              ))}
            </div>
          </TabsContent>

          <TabsContent value="governance">
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
              {contracts.filter(c => c.category === "governance" || c.category === "treasury").map((contract) => (
                <ContractCard key={contract.address} contract={contract} />
              ))}
            </div>
          </TabsContent>
        </Tabs>

        {/* Audit Reports */}
        <div className="glass rounded-xl p-6 border border-border/30">
          <h3 className="text-lg font-semibold text-foreground mb-6 flex items-center gap-2">
            <Shield className="w-5 h-5 text-primary" />
            Security Audit Reports
          </h3>

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border/30">
                  <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Auditor</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Date</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Scope</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Issues Found</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Status</th>
                  <th className="text-right py-3 px-4 text-sm font-medium text-muted-foreground">Report</th>
                </tr>
              </thead>
              <tbody>
                {auditReports.map((report, i) => (
                  <tr key={i} className="border-b border-border/20 last:border-0">
                    <td className="py-4 px-4">
                      <span className="text-sm font-medium text-foreground">{report.auditor}</span>
                    </td>
                    <td className="py-4 px-4">
                      <span className="text-sm text-muted-foreground">{report.date}</span>
                    </td>
                    <td className="py-4 px-4">
                      <span className="text-sm text-muted-foreground">{report.scope}</span>
                    </td>
                    <td className="py-4 px-4">
                      <span className="text-sm text-muted-foreground">{report.issues}</span>
                    </td>
                    <td className="py-4 px-4">
                      <Badge variant="outline" className="bg-accent/10 text-accent border-accent/30">
                        {report.status}
                      </Badge>
                    </td>
                    <td className="py-4 px-4 text-right">
                      <Button variant="ghost" size="sm">
                        <ExternalLink className="w-4 h-4" />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
