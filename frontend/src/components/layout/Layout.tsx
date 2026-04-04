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

// Pages that should stay mounted (keep-alive) to preserve state
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

  // AgentDetail is dynamic — still use normal routing for it
  const isAgentDetail = currentPath.startsWith('/agents/')

  return (
    <div className="flex h-screen overflow-hidden bg-bg">
      <Sidebar />
      <div className="flex flex-col flex-1 overflow-hidden">
        <Topbar />
        <main className="flex-1 overflow-y-auto p-6">
          {/* Keep-alive pages: always mounted, shown/hidden via CSS */}
          {KEEP_ALIVE_PAGES.map(({ path, Component }) => (
            <div
              key={path}
              style={{ display: currentPath === path && !isAgentDetail ? 'block' : 'none' }}
            >
              <Component />
            </div>
          ))}

          {/* AgentDetail: normal mount/unmount (dynamic route) */}
          {isAgentDetail && <AgentDetail />}
        </main>
      </div>
    </div>
  )
}
