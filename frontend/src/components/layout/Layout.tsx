import { useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'
import Topbar from './Topbar'
import Dashboard from '../../pages/Dashboard'
import Agents from '../../pages/Agents'
import AgentDetail from '../../pages/AgentDetail'
import RiskPools from '../../pages/RiskPools'
import AllocationEngine from '../../pages/AllocationEngine'
import Analytics from '../../pages/Analytics'
import Governance from '../../pages/Governance'
import Contracts from '../../pages/Contracts'
import WorldMonitor from '../../pages/WorldMonitor'
import AgentSocial from '../../pages/AgentSocial'

const KEEP_ALIVE_PAGES = [
  { path: '/dashboard',  Component: Dashboard },
  { path: '/agents',     Component: Agents },
  { path: '/pools',      Component: RiskPools },
  { path: '/allocation', Component: AllocationEngine },
  { path: '/analytics',  Component: Analytics },
  { path: '/governance', Component: Governance },
  { path: '/contracts',  Component: Contracts },
  { path: '/world',      Component: WorldMonitor },
  { path: '/social',     Component: AgentSocial },
]

export default function Layout() {
  const location = useLocation()
  const currentPath = location.pathname

  const isAgentDetail = currentPath.startsWith('/agents/')

  return (
    <div className="flex h-screen overflow-hidden bg-bg">
      <Sidebar />
      <div className="flex flex-col flex-1 overflow-hidden">
        <Topbar />
        <main className="flex-1 overflow-y-auto p-6">
          {}
          {KEEP_ALIVE_PAGES.map(({ path, Component }) => (
            <div
              key={path}
              style={{ display: currentPath === path && !isAgentDetail ? 'block' : 'none' }}
            >
              <Component />
            </div>
          ))}

          {}
          {isAgentDetail && <AgentDetail />}
        </main>
      </div>
    </div>
  )
}
