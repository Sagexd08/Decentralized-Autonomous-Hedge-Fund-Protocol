import { useState } from 'react'
import { Globe, ExternalLink, Maximize2 } from 'lucide-react'

const LOCAL_URL = 'http://localhost:3001/?lat=20.0000&lon=0.0000&zoom=1.00&view=global&timeRange=7d&layers=conflicts%2Cbases%2Cpipelines%2Chotspots%2Cais%2Cnuclear%2Cirradiators%2Csanctions%2Cweather%2Ceconomic%2Cwaterways%2Coutages%2Cdatacenters%2Cmilitary%2Cnatural%2Cspaceports%2Cminerals%2CtradeRoutes%2CiranAttacks%2CgpsJamming%2Csatellites'
const FINANCE_URL = 'http://localhost:3002/?lat=20.0000&lon=0.0000&zoom=1.00&view=global&timeRange=7d&layers=conflicts%2Cbases%2Cpipelines%2Chotspots%2Cais%2Cnuclear%2Cirradiators%2Csanctions%2Cweather%2Ceconomic%2Cwaterways%2Coutages%2Cdatacenters%2Cmilitary%2Cnatural%2Cspaceports%2Cminerals%2CtradeRoutes%2CiranAttacks%2CgpsJamming%2Csatellites'
const REMOTE_URL = 'https://www.worldmonitor.app/?lat=20.0000&lon=0.0000&zoom=1.00&view=global&timeRange=7d&layers=conflicts%2Cbases%2Cpipelines%2Chotspots%2Cais%2Cnuclear%2Cirradiators%2Csanctions%2Cweather%2Ceconomic%2Cwaterways%2Coutages%2Cdatacenters%2Cmilitary%2Cnatural%2Cspaceports%2Cminerals%2CtradeRoutes%2CiranAttacks%2CgpsJamming%2Csatellites'

export default function WorldMonitor() {
  const [mode, setMode] = useState<'local'|'finance'|'remote'>('local')
  const [fullscreen, setFullscreen] = useState(false)
  const [key, setKey] = useState(0)

  const src = mode === 'local' ? LOCAL_URL : mode === 'finance' ? FINANCE_URL : REMOTE_URL
  const switchTo = (m: typeof mode) => { setMode(m); setKey(k => k + 1) }

  return (
    <div className={`flex flex-col gap-3 ${fullscreen ? 'fixed inset-0 z-50 bg-bg p-4' : 'h-full'}`}>
      <div className="flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <Globe size={18} className="text-cyan" />
          <h1 className="text-lg font-bold text-white tracking-wider">World Monitor</h1>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 bg-surface border border-border rounded-lg p-0.5">
            <button onClick={() => switchTo('local')} className={`text-xs px-2 py-1 rounded-md transition-all ${mode === 'local' ? 'bg-cyan/10 text-cyan' : 'text-slate-500 hover:text-slate-300'}`}>
              Global :3001
            </button>
            <button onClick={() => switchTo('finance')} className={`text-xs px-2 py-1 rounded-md transition-all ${mode === 'finance' ? 'bg-cyan/10 text-cyan' : 'text-slate-500 hover:text-slate-300'}`}>
              Finance :3002
            </button>
          </div>
          <button
            onClick={() => setFullscreen(f => !f)}
            className="text-xs text-slate-400 hover:text-white border border-border px-2 py-1 rounded-lg transition-all flex items-center gap-1"
          >
            <Maximize2 size={11} />
            {fullscreen ? 'Exit' : 'Fullscreen'}
          </button>
          <a
            href={src}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-cyan bg-cyan/10 border border-cyan/20 px-2 py-1 rounded-lg hover:bg-cyan/20 transition-all flex items-center gap-1"
          >
            <ExternalLink size={11} /> Open ↗
          </a>
        </div>
      </div>

      <div className="flex-1 rounded-xl overflow-hidden border border-border" style={{ minHeight: '75vh' }}>
        <iframe
          key={key}
          src={src}
          className="w-full h-full"
          style={{ height: fullscreen ? 'calc(100vh - 80px)' : '75vh' }}
          title="World Monitor"
          allow="geolocation; fullscreen"
        />
      </div>
    </div>
  )
}
