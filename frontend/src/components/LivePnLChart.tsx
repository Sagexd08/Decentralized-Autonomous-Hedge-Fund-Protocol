import { useEffect, useRef, useState } from 'react'
import { AreaChart, Area, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { TradeExecutedMessage, WebSocketStatus } from '../hooks/useWebSocket'

interface ChartPoint {
  x:   number
  pnl: number
}

interface Props {
  messages: TradeExecutedMessage[]
  status:   WebSocketStatus
}

const TOKEN_PRICE_ETH: Record<string, number> = {
  WBTC: 15.0,
  USDC: 0.0005,
  LINK: 0.0075,
  UNI:  0.004,
  WETH: 1.0,
}

const MAX_CHART_POINTS = 100

function ConnectionBadge({ status }: { status: WebSocketStatus }) {
  const isLive = status === 'connected'
  return (
    <span
      className={`inline-flex items-center gap-1.5 text-xs font-medium px-2 py-0.5 rounded-full ${
        isLive
          ? 'bg-green/10 text-green'
          : 'bg-gold/10 text-gold'
      }`}
    >
      <span
        className={`w-1.5 h-1.5 rounded-full ${isLive ? 'bg-green animate-pulse' : 'bg-gold'}`}
      />
      {isLive ? 'LIVE' : 'RECONNECTING'}
    </span>
  )
}

export default function LivePnLChart({ messages, status }: Props) {
  const [chartData, setChartData] = useState<ChartPoint[]>([])
  const cumulativePnLRef = useRef(0)
  const processedCountRef = useRef(0)

  useEffect(() => {
    const newMessages = messages.slice(processedCountRef.current)
    if (newMessages.length === 0) return

    setChartData(prev => {
      let updated = [...prev]
      let cumPnL = cumulativePnLRef.current

      for (const msg of newMessages) {
        const ethSpent = BigInt(msg.amountIn || '0')
        const amountOut = BigInt(msg.amountOut || '0')
        const priceEth = TOKEN_PRICE_ETH[msg.token] ?? 0

        const tokenValueEth = Number(amountOut) * priceEth / 1e18
        const ethSpentEth = Number(ethSpent) / 1e18
        cumPnL += tokenValueEth - ethSpentEth

        updated.push({ x: updated.length, pnl: cumPnL })
        if (updated.length > MAX_CHART_POINTS) {
          updated = updated.slice(updated.length - MAX_CHART_POINTS)
        }
      }

      cumulativePnLRef.current = cumPnL
      return updated
    })

    processedCountRef.current = messages.length
  }, [messages])

  const pnlColor = (cumulativePnLRef.current ?? 0) >= 0 ? '#10b981' : '#ef4444'

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-white">Live Agent PnL</h3>
          <p className="text-xs text-slate-500">Cumulative across all trades</p>
        </div>
        <ConnectionBadge status={status} />
      </div>

      {chartData.length === 0 ? (
        <div className="flex items-center justify-center h-[180px] text-slate-500 text-sm">
          Waiting for trade data...
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={180}>
          <AreaChart data={chartData}>
            <defs>
              <linearGradient id="pnlGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={pnlColor} stopOpacity={0.2} />
                <stop offset="95%" stopColor={pnlColor} stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="x" hide />
            <YAxis hide />
            <Tooltip
              contentStyle={{
                background: '#111827',
                border: '1px solid #1f2937',
                borderRadius: 8,
                fontSize: 11,
              }}
              formatter={(value: number) => [`${value.toFixed(6)} ETH`, 'PnL']}
            />
            <Area
              type="monotone"
              dataKey="pnl"
              stroke={pnlColor}
              strokeWidth={2}
              fill="url(#pnlGrad)"
              dot={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
