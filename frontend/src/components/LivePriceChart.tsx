import { useState } from 'react'
import { TokenPrices } from '../hooks/usePriceWebSocket'
import CandlestickChart, { useLiveOHLC, buildOHLC } from './CandlestickChart'

const TOKEN_COLORS: Record<string, string> = {
  WBTC: '#f59e0b', USDC: '#10b981', LINK: '#3b82f6', UNI: '#a855f7',
}
const TOKEN_BASE: Record<string, number> = {
  WBTC: 30000, USDC: 1.0, LINK: 15.0, UNI: 8.0,
}
const TOKEN_VOL: Record<string, number> = {
  WBTC: 0.012, USDC: 0.0004, LINK: 0.018, UNI: 0.020,
}

interface Props {
  prices: TokenPrices
  connected: boolean
}

// Per-token live chart — each token gets its own stable walk
function TokenChart({ sym, prices }: { sym: string; prices: TokenPrices }) {
  const liveData = useLiveOHLC(TOKEN_BASE[sym] ?? 100, TOKEN_VOL[sym] ?? 0.015)
  const hist = prices[sym]?.history ?? []
  const data = hist.length >= 8 ? buildOHLC(hist) : liveData
  return <CandlestickChart data={data} height={260} />
}

export default function LivePriceChart({ prices, connected }: Props) {
  const [selected, setSelected] = useState<string>('WBTC')

  return (
    <div className="card">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-white">Live Asset Prices</h3>
          <p className="text-xs text-slate-500">OHLC candlestick · 10s candles · continuous walk</p>
        </div>
        <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${
          connected ? 'bg-green/10 text-green' : 'bg-yellow-400/10 text-yellow-400'
        }`}>
          <span className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-green animate-pulse' : 'bg-yellow-400'}`} />
          {connected ? 'LIVE' : 'CONNECTING'}
        </span>
      </div>

      {/* Token selector */}
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        {Object.keys(TOKEN_BASE).map(sym => {
          const tp = prices[sym]
          const up = (tp?.change_pct ?? 0) >= 0
          const active = selected === sym
          return (
            <button key={sym} onClick={() => setSelected(sym)}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-xl border transition-all ${
                active ? '' : 'border-border hover:border-slate-600'
              }`}
              style={active ? {
                background: `${TOKEN_COLORS[sym]}15`,
                borderColor: `${TOKEN_COLORS[sym]}50`,
              } : {}}>
              <div className="text-left">
                <p className="text-xs font-semibold" style={{ color: active ? TOKEN_COLORS[sym] : '#94a3b8' }}>{sym}</p>
                <p className="text-xs font-mono text-white">
                  ${tp?.current?.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 4 }) ?? TOKEN_BASE[sym].toLocaleString()}
                </p>
              </div>
              <span className={`text-xs font-mono ${up ? 'text-green' : 'text-red-400'}`}>
                {up ? '+' : ''}{tp?.change_pct?.toFixed(3) ?? '0.000'}%
              </span>
            </button>
          )
        })}
      </div>

      {/* Chart — stable per-token, only re-renders when selected changes */}
      <TokenChart sym={selected} prices={prices} />
    </div>
  )
}
