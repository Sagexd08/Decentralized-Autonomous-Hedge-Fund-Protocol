import { Routes, Route } from 'react-router-dom'
import Layout from './components/layout/Layout'
import Index from './pages/Index'
import Dashboard from './pages/Dashboard'
import Agents from './pages/Agents'
import AgentDetail from './pages/AgentDetail'
import RiskPools from './pages/RiskPools'
import AllocationEngine from './pages/AllocationEngine'
import Governance from './pages/Governance'
import Analytics from './pages/Analytics'
import Contracts from './pages/Contracts'
import WorldMonitor from './pages/WorldMonitor'
import AgentSocial from './pages/AgentSocial'
import PnLHistory from './pages/PnLHistory'
import Intelligence from './pages/Intelligence'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Index />} />
      <Route element={<Layout />}>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/agents" element={<Agents />} />
        <Route path="/agents/:id" element={<AgentDetail />} />
        <Route path="/pools" element={<RiskPools />} />
        <Route path="/allocation" element={<AllocationEngine />} />
        <Route path="/intelligence" element={<Intelligence />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route path="/governance" element={<Governance />} />
        <Route path="/contracts" element={<Contracts />} />
        <Route path="/world" element={<WorldMonitor />} />
        <Route path="/social" element={<AgentSocial />} />
        <Route path="/pnl-history" element={<PnLHistory />} />
      </Route>
    </Routes>
  )
}
