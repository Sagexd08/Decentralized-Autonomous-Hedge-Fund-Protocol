import { DollarSign, TrendingUp, Users, Shield } from 'lucide-react'

const metrics = [
  { label: 'Total Portfolio Value', value: '$1,284,720', icon: DollarSign },
  { label: 'Unrealized PnL', value: '+$142,380', icon: TrendingUp },
  { label: 'Active Agents', value: '6 / 47', icon: Users },
  { label: 'Risk Score', value: '72 / 100', icon: Shield },
]

export default function Dashboard() {
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold text-white">Autonomous Capital Brain</h1>
        <p className="text-slate-500 text-sm mt-0.5">Real-time orchestration of agent intelligence, risk, and capital rotation</p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {metrics.map((m) => (
          <div key={m.label} className="card">
            <div className="flex items-center justify-between mb-3">
              <div className="w-8 h-8 rounded-lg bg-cyan/10 flex items-center justify-center">
                <m.icon size={14} className="text-cyan" />
              </div>
            </div>
            <div className="text-xl font-bold text-white">{m.value}</div>
            <div className="text-xs text-slate-500 mt-0.5">{m.label}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
