"use client"

import { useEffect, useRef } from "react"

export function AnimatedDashboard({ className = "" }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext("2d")
    if (!ctx) return

    let animationId: number
    let time = 0

    const resize = () => {
      const dpr = window.devicePixelRatio || 1
      const rect = canvas.getBoundingClientRect()
      canvas.width = rect.width * dpr
      canvas.height = rect.height * dpr
      ctx.scale(dpr, dpr)
    }

    resize()
    window.addEventListener("resize", resize)

    const drawPanel = (
      x: number,
      y: number,
      w: number,
      h: number,
      title: string,
      chartType: "bar" | "line" | "area"
    ) => {
      // Panel background
      ctx.fillStyle = "rgba(17, 17, 20, 0.8)"
      ctx.strokeStyle = "rgba(0, 229, 204, 0.2)"
      ctx.lineWidth = 1
      ctx.beginPath()
      ctx.roundRect(x, y, w, h, 6)
      ctx.fill()
      ctx.stroke()

      // Title bar
      ctx.fillStyle = "rgba(0, 229, 204, 0.1)"
      ctx.beginPath()
      ctx.roundRect(x, y, w, 20, [6, 6, 0, 0])
      ctx.fill()

      // Title text representation (small bars)
      ctx.fillStyle = "rgba(240, 240, 242, 0.6)"
      ctx.fillRect(x + 8, y + 8, 40, 4)

      // Chart area
      const chartX = x + 10
      const chartY = y + 30
      const chartW = w - 20
      const chartH = h - 40

      if (chartType === "bar") {
        const barCount = 6
        const barWidth = chartW / barCount - 4
        for (let i = 0; i < barCount; i++) {
          const barHeight = (Math.sin(time + i * 0.5) * 0.3 + 0.7) * chartH * 0.8
          const barX = chartX + i * (barWidth + 4)
          const barY = chartY + chartH - barHeight

          const gradient = ctx.createLinearGradient(barX, barY + barHeight, barX, barY)
          gradient.addColorStop(0, "rgba(0, 229, 204, 0.3)")
          gradient.addColorStop(1, "rgba(0, 229, 204, 0.8)")
          ctx.fillStyle = gradient
          ctx.fillRect(barX, barY, barWidth, barHeight)
        }
      } else if (chartType === "line") {
        ctx.beginPath()
        const points = 10
        for (let i = 0; i <= points; i++) {
          const px = chartX + (i / points) * chartW
          const py = chartY + chartH / 2 + Math.sin(time * 2 + i * 0.8) * (chartH * 0.3)
          if (i === 0) ctx.moveTo(px, py)
          else ctx.lineTo(px, py)
        }
        ctx.strokeStyle = "#00E5CC"
        ctx.lineWidth = 2
        ctx.stroke()

        // Second line
        ctx.beginPath()
        for (let i = 0; i <= points; i++) {
          const px = chartX + (i / points) * chartW
          const py = chartY + chartH / 2 + Math.sin(time * 2 + i * 0.8 + 1) * (chartH * 0.25)
          if (i === 0) ctx.moveTo(px, py)
          else ctx.lineTo(px, py)
        }
        ctx.strokeStyle = "#F59E0B"
        ctx.lineWidth = 2
        ctx.stroke()
      } else if (chartType === "area") {
        ctx.beginPath()
        ctx.moveTo(chartX, chartY + chartH)
        const points = 10
        for (let i = 0; i <= points; i++) {
          const px = chartX + (i / points) * chartW
          const py = chartY + chartH * 0.3 + Math.sin(time * 1.5 + i * 0.6) * (chartH * 0.2)
          ctx.lineTo(px, py)
        }
        ctx.lineTo(chartX + chartW, chartY + chartH)
        ctx.closePath()

        const areaGradient = ctx.createLinearGradient(chartX, chartY, chartX, chartY + chartH)
        areaGradient.addColorStop(0, "rgba(16, 185, 129, 0.4)")
        areaGradient.addColorStop(1, "rgba(16, 185, 129, 0.05)")
        ctx.fillStyle = areaGradient
        ctx.fill()

        ctx.beginPath()
        for (let i = 0; i <= points; i++) {
          const px = chartX + (i / points) * chartW
          const py = chartY + chartH * 0.3 + Math.sin(time * 1.5 + i * 0.6) * (chartH * 0.2)
          if (i === 0) ctx.moveTo(px, py)
          else ctx.lineTo(px, py)
        }
        ctx.strokeStyle = "#10B981"
        ctx.lineWidth = 2
        ctx.stroke()
      }
    }

    const draw = () => {
      const width = canvas.width / (window.devicePixelRatio || 1)
      const height = canvas.height / (window.devicePixelRatio || 1)

      ctx.clearRect(0, 0, width, height)

      // Layout panels in a dashboard grid
      const padding = 10
      const panelGap = 8

      // Top row - 2 panels
      const topPanelWidth = (width - padding * 2 - panelGap) / 2
      const topPanelHeight = (height - padding * 2 - panelGap * 2) / 3

      drawPanel(padding, padding, topPanelWidth, topPanelHeight, "Performance", "line")
      drawPanel(padding + topPanelWidth + panelGap, padding, topPanelWidth, topPanelHeight, "Allocation", "bar")

      // Middle row - 1 wide panel
      drawPanel(padding, padding + topPanelHeight + panelGap, width - padding * 2, topPanelHeight, "Capital Flow", "area")

      // Bottom row - 3 small panels
      const bottomPanelWidth = (width - padding * 2 - panelGap * 2) / 3
      const bottomY = padding + topPanelHeight * 2 + panelGap * 2

      drawPanel(padding, bottomY, bottomPanelWidth, topPanelHeight, "Risk", "bar")
      drawPanel(padding + bottomPanelWidth + panelGap, bottomY, bottomPanelWidth, topPanelHeight, "Agents", "line")
      drawPanel(padding + bottomPanelWidth * 2 + panelGap * 2, bottomY, bottomPanelWidth, topPanelHeight, "Returns", "area")

      time += 0.016
      animationId = requestAnimationFrame(draw)
    }

    draw()

    return () => {
      window.removeEventListener("resize", resize)
      cancelAnimationFrame(animationId)
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      className={`w-full h-full ${className}`}
      style={{ background: "transparent" }}
    />
  )
}
