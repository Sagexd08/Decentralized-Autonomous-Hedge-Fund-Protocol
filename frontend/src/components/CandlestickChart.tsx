import { useState, useRef, useCallback, useEffect } from 'react'

export interface OHLCBar {
  time: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export function genSyntheticOHLC(base: number, count = 80, volatility = 0.015): OHLCBar[] {

  const bars: OHLCBar[] = []
  let price = base

  let seed = Math.floor(base * 1000) % 2147483647
  const rand = () => {
    seed = (seed * 1664525 + 1013904223) % 2147483647
    return seed / 2147483647
  }
  const now = Date.now()
  for (let i = 0; i < count; i++) {
    const open = price
    const drift = (rand() - 0.47) * volatility
    const noise = (rand() - 0.5) * volatility * 0.4
    const close = Math.max(open * (1 + drift + noise), open * 0.7)
    const wickUp = rand() * volatility * 0.5 * open
    const wickDown = rand() * volatility * 0.5 * open
    const high = Math.max(open, close) + wickUp
    const low = Math.min(open, close) - wickDown
    const volume = Math.floor(200 + rand() * 1200 + Math.abs(drift) * 5000)
    const ts = now - (count - i) * 10000
    const d = new Date(ts)
    const time = `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`
    bars.push({ time, open, high, low, close, volume })
    price = close
  }
  return bars
}

export function buildOHLC(prices: number[], intervalMs = 10000): OHLCBar[] {
  if (prices.length < 4) return []
  const step = Math.max(1, Math.floor(prices.length / 80))
  const bars: OHLCBar[] = []
  const now = Date.now()
  for (let i = 0; i + step <= prices.length; i += step) {
    const slice = prices.slice(i, i + step)
    const open = slice[0], close = slice[slice.length - 1]
    const high = Math.max(...slice) * (1 + Math.random() * 0.001)
    const low = Math.min(...slice) * (1 - Math.random() * 0.001)
    const volume = Math.floor(200 + Math.random() * 800)
    const ts = now - (prices.length - i) * intervalMs
    const d = new Date(ts)
    const time = `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`
    bars.push({ time, open, high, low, close, volume })
  }
  return bars
}

export function useLiveOHLC(base: number, volatility = 0.015, maxCandles = 80) {
  const [bars, setBars] = useState<OHLCBar[]>(() => genSyntheticOHLC(base, maxCandles, volatility))
  const lastPriceRef = useRef(bars[bars.length - 1]?.close ?? base)

  useEffect(() => {
    const interval = setInterval(() => {
      const open = lastPriceRef.current
      const drift = (Math.random() - 0.47) * volatility
      const noise = (Math.random() - 0.5) * volatility * 0.3
      const close = Math.max(open * (1 + drift + noise), open * 0.7)
      const wickUp = Math.random() * volatility * 0.4 * open
      const wickDown = Math.random() * volatility * 0.4 * open
      const high = Math.max(open, close) + wickUp
      const low = Math.min(open, close) - wickDown
      const volume = Math.floor(200 + Math.random() * 1000)
      const d = new Date()
      const time = `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`
      const newBar: OHLCBar = { time, open, high, low, close, volume }
      lastPriceRef.current = close
      setBars(prev => [...prev.slice(-(maxCandles - 1)), newBar])
    }, 10000)
    return () => clearInterval(interval)
  }, [base, volatility, maxCandles])

  return bars
}
interface TooltipState {
  x: number; y: number; bar: OHLCBar; visible: boolean
}

interface Props {
  data: OHLCBar[]
  height?: number
  title?: string
  subtitle?: string
}

const PAD = { top: 12, right: 56, bottom: 28, left: 8 }
const VOL_H = 48

export default function CandlestickChart({ data, height = 300, title, subtitle }: Props) {
  const svgRef = useRef<SVGSVGElement>(null)
  const [tooltip, setTooltip] = useState<TooltipState>({ x: 0, y: 0, bar: data[0], visible: false })
  const [svgW, setSvgW] = useState(600)

  useEffect(() => {
    const obs = new ResizeObserver(entries => {
      const w = entries[0]?.contentRect.width
      if (w) setSvgW(w)
    })
    if (svgRef.current?.parentElement) obs.observe(svgRef.current.parentElement)
    return () => obs.disconnect()
  }, [])

  if (data.length < 2) {
    return (
      <div className="flex items-center justify-center text-slate-500 text-xs" style={{ height }}>
        Collecting price data…
      </div>
    )
  }

  const chartH = height - VOL_H - 8
  const innerW = svgW - PAD.left - PAD.right
  const innerH = chartH - PAD.top - PAD.bottom
  const volInnerH = VOL_H - 16

  const minP = Math.min(...data.map(d => d.low))
  const maxP = Math.max(...data.map(d => d.high))
  const priceRange = maxP - minP || 1
  const py = (p: number) => PAD.top + innerH - ((p - minP) / priceRange) * innerH

  const maxVol = Math.max(...data.map(d => d.volume))
  const vy = (v: number) => volInnerH - (v / maxVol) * volInnerH

  const totalW = innerW
  const candleW = Math.max(2, totalW / data.length - 1)
  const cx = (i: number) => PAD.left + (i + 0.5) * (totalW / data.length)

  const yTicks = Array.from({ length: 5 }, (_, i) => minP + (priceRange * i) / 4)

  const xInterval = Math.max(1, Math.floor(data.length / 8))

  const handleMouseMove = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
    const rect = svgRef.current?.getBoundingClientRect()
    if (!rect) return
    const mx = e.clientX - rect.left - PAD.left
    const idx = Math.round(mx / (totalW / data.length) - 0.5)
    if (idx >= 0 && idx < data.length) {
      setTooltip({ x: e.clientX - rect.left, y: e.clientY - rect.top, bar: data[idx], visible: true })
    }
  }, [data, totalW])

  const totalSvgH = chartH + VOL_H + 8

  return (
    <div>
      {(title || subtitle) && (
        <div className="flex items-center justify-between mb-2">
          {title && <p className="text-sm font-semibold text-white">{title}</p>}
          {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
        </div>
      )}
      <div className="relative w-full" style={{ height: totalSvgH }}>
        <svg
          ref={svgRef}
          width="100%"
          height={totalSvgH}
          onMouseMove={handleMouseMove}
          onMouseLeave={() => setTooltip(t => ({ ...t, visible: false }))}
          style={{ display: 'block' }}
        >
          {}
          {yTicks.map((tick, i) => (
            <line key={i}
              x1={PAD.left} y1={py(tick)}
              x2={svgW - PAD.right} y2={py(tick)}
              stroke="#1e293b" strokeWidth={1} strokeDasharray="3 4"
            />
          ))}

          {}
          {yTicks.map((tick, i) => (
            <text key={i}
              x={svgW - PAD.right + 4} y={py(tick) + 3}
              fill="#64748b" fontSize={9} textAnchor="start">
              {tick.toFixed(2)}
            </text>
          ))}

          {}
          {data.map((bar, i) => i % xInterval === 0 && (
            <text key={i}
              x={cx(i)} y={chartH - 4}
              fill="#64748b" fontSize={9} textAnchor="middle">
              {bar.time}
            </text>
          ))}

          {}
          {data.map((bar, i) => {
            const bull = bar.close >= bar.open
            const color = bull ? '#10b981' : '#ef4444'
            const bodyTop = py(Math.max(bar.open, bar.close))
            const bodyBot = py(Math.min(bar.open, bar.close))
            const bodyH = Math.max(bodyBot - bodyTop, 1)
            const x = cx(i)
            const hw = candleW / 2

            return (
              <g key={i}>
                {}
                <line x1={x} y1={py(bar.high)} x2={x} y2={bodyTop}
                  stroke={color} strokeWidth={1} />
                {}
                <line x1={x} y1={bodyBot} x2={x} y2={py(bar.low)}
                  stroke={color} strokeWidth={1} />
                {}
                <rect
                  x={x - hw} y={bodyTop}
                  width={candleW} height={bodyH}
                  fill={bull ? '#10b98199' : '#ef444499'}
                  stroke={color}
                  strokeWidth={0.8}
                  rx={0.5}
                />
              </g>
            )
          })}

          {}
          <line
            x1={PAD.left} y1={chartH + 4}
            x2={svgW - PAD.right} y2={chartH + 4}
            stroke="#1e293b" strokeWidth={1}
          />

          {}
          {data.map((bar, i) => {
            const bull = bar.close >= bar.open
            const color = bull ? '#10b981' : '#ef4444'
            const barH = Math.max((bar.volume / maxVol) * volInnerH, 1)
            const x = cx(i)
            const hw = candleW / 2
            const yTop = chartH + 8 + (volInnerH - barH)
            return (
              <rect key={i}
                x={x - hw} y={yTop}
                width={candleW} height={barH}
                fill={color} fillOpacity={0.35}
                rx={0.5}
              />
            )
          })}

          {}
          {tooltip.visible && (
            <>
              <line x1={tooltip.x} y1={PAD.top} x2={tooltip.x} y2={chartH - PAD.bottom}
                stroke="#475569" strokeWidth={1} strokeDasharray="3 3" />
              <line x1={PAD.left} y1={tooltip.y} x2={svgW - PAD.right} y2={tooltip.y}
                stroke="#475569" strokeWidth={1} strokeDasharray="3 3" />
            </>
          )}
        </svg>

        {}
        {tooltip.visible && tooltip.bar && (
          <div
            className="absolute pointer-events-none z-10 bg-slate-900 border border-slate-700 rounded-xl p-3 text-xs shadow-2xl min-w-[150px]"
            style={{
              left: tooltip.x + 12 > svgW - 170 ? tooltip.x - 162 : tooltip.x + 12,
              top: Math.max(4, tooltip.y - 60),
            }}
          >
            <p className="text-slate-400 font-mono mb-2">{tooltip.bar.time}</p>
            {[
              ['O', tooltip.bar.open, tooltip.bar.close >= tooltip.bar.open ? '#10b981' : '#ef4444'],
              ['H', tooltip.bar.high, '#10b981'],
              ['L', tooltip.bar.low, '#ef4444'],
              ['C', tooltip.bar.close, tooltip.bar.close >= tooltip.bar.open ? '#10b981' : '#ef4444'],
            ].map(([label, val, color]) => (
              <div key={label as string} className="flex justify-between gap-6">
                <span className="text-slate-500">{label}</span>
                <span className="font-mono" style={{ color: color as string }}>
                  {(val as number).toFixed(4)}
                </span>
              </div>
            ))}
            <div className="flex justify-between gap-6 mt-1 pt-1 border-t border-slate-700/50">
              <span className="text-slate-500">Vol</span>
              <span className="font-mono text-slate-300">{tooltip.bar.volume.toLocaleString()}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
