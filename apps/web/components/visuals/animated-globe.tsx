"use client"

import { useEffect, useRef } from "react"

export function AnimatedGlobe({ className = "" }: { className?: string }) {
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

    const draw = () => {
      const width = canvas.width / (window.devicePixelRatio || 1)
      const height = canvas.height / (window.devicePixelRatio || 1)

      ctx.clearRect(0, 0, width, height)

      const centerX = width / 2
      const centerY = height / 2
      const radius = Math.min(width, height) * 0.35

      // Globe glow
      const glowGradient = ctx.createRadialGradient(centerX, centerY, radius * 0.8, centerX, centerY, radius * 1.4)
      glowGradient.addColorStop(0, "rgba(0, 229, 204, 0.15)")
      glowGradient.addColorStop(0.5, "rgba(0, 229, 204, 0.05)")
      glowGradient.addColorStop(1, "transparent")
      ctx.fillStyle = glowGradient
      ctx.fillRect(0, 0, width, height)

      // Globe outline
      ctx.beginPath()
      ctx.arc(centerX, centerY, radius, 0, Math.PI * 2)
      ctx.strokeStyle = "rgba(0, 229, 204, 0.4)"
      ctx.lineWidth = 2
      ctx.stroke()

      // Inner glow
      const innerGlow = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, radius)
      innerGlow.addColorStop(0, "rgba(0, 229, 204, 0.1)")
      innerGlow.addColorStop(0.7, "rgba(0, 229, 204, 0.03)")
      innerGlow.addColorStop(1, "transparent")
      ctx.fillStyle = innerGlow
      ctx.fill()

      // Latitude lines
      for (let i = -3; i <= 3; i++) {
        const y = centerY + (i / 4) * radius * 0.9
        const latRadius = Math.sqrt(radius * radius - Math.pow(y - centerY, 2)) * 0.95

        if (latRadius > 0) {
          ctx.beginPath()
          ctx.ellipse(centerX, y, latRadius, latRadius * 0.15, 0, 0, Math.PI * 2)
          ctx.strokeStyle = `rgba(0, 229, 204, ${0.15 - Math.abs(i) * 0.02})`
          ctx.lineWidth = 1
          ctx.stroke()
        }
      }

      // Longitude lines (rotating)
      for (let i = 0; i < 8; i++) {
        const angle = (i / 8) * Math.PI + time * 0.3
        ctx.beginPath()
        ctx.save()
        ctx.translate(centerX, centerY)
        ctx.rotate(angle)

        ctx.ellipse(0, 0, radius * 0.1, radius, 0, 0, Math.PI * 2)
        ctx.strokeStyle = "rgba(0, 229, 204, 0.12)"
        ctx.lineWidth = 1
        ctx.stroke()
        ctx.restore()
      }

      // Animated connection points (capitals)
      const nodes = [
        { lat: 0.3, lon: time * 0.4 },
        { lat: -0.2, lon: time * 0.4 + 1 },
        { lat: 0.5, lon: time * 0.4 + 2 },
        { lat: -0.4, lon: time * 0.4 + 3 },
        { lat: 0.1, lon: time * 0.4 + 4 },
        { lat: -0.6, lon: time * 0.4 + 5 },
        { lat: 0.4, lon: time * 0.4 + 1.5 },
        { lat: -0.3, lon: time * 0.4 + 2.5 },
      ]

      // Draw connection lines between nodes
      ctx.strokeStyle = "rgba(0, 229, 204, 0.25)"
      ctx.lineWidth = 1
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          if (Math.random() > 0.7) continue
          const node1 = nodes[i]
          const node2 = nodes[j]

          const x1 = centerX + Math.cos(node1.lon) * radius * 0.85 * Math.cos(node1.lat * Math.PI / 2)
          const y1 = centerY + node1.lat * radius * 0.85
          const x2 = centerX + Math.cos(node2.lon) * radius * 0.85 * Math.cos(node2.lat * Math.PI / 2)
          const y2 = centerY + node2.lat * radius * 0.85

          ctx.beginPath()
          ctx.moveTo(x1, y1)
          const cpX = (x1 + x2) / 2
          const cpY = (y1 + y2) / 2 - 20
          ctx.quadraticCurveTo(cpX, cpY, x2, y2)
          ctx.stroke()
        }
      }

      // Draw nodes
      nodes.forEach((node, i) => {
        const x = centerX + Math.cos(node.lon) * radius * 0.85 * Math.cos(node.lat * Math.PI / 2)
        const y = centerY + node.lat * radius * 0.85
        const visible = Math.cos(node.lon) > -0.3

        if (visible) {
          // Glow
          const nodeGlow = ctx.createRadialGradient(x, y, 0, x, y, 12)
          nodeGlow.addColorStop(0, i % 2 === 0 ? "rgba(0, 229, 204, 0.8)" : "rgba(16, 185, 129, 0.8)")
          nodeGlow.addColorStop(0.5, i % 2 === 0 ? "rgba(0, 229, 204, 0.2)" : "rgba(16, 185, 129, 0.2)")
          nodeGlow.addColorStop(1, "transparent")
          ctx.fillStyle = nodeGlow
          ctx.beginPath()
          ctx.arc(x, y, 12, 0, Math.PI * 2)
          ctx.fill()

          // Core
          ctx.beginPath()
          ctx.arc(x, y, 3, 0, Math.PI * 2)
          ctx.fillStyle = i % 2 === 0 ? "#00E5CC" : "#10B981"
          ctx.fill()
        }
      })

      // Floating data panels (glass cards around globe)
      const drawPanel = (x: number, y: number, w: number, h: number, delay: number) => {
        const yOffset = Math.sin(time + delay) * 5
        ctx.fillStyle = "rgba(17, 17, 20, 0.6)"
        ctx.strokeStyle = "rgba(0, 229, 204, 0.3)"
        ctx.lineWidth = 1
        ctx.beginPath()
        ctx.roundRect(x, y + yOffset, w, h, 4)
        ctx.fill()
        ctx.stroke()

        // Mini chart lines
        ctx.strokeStyle = "rgba(0, 229, 204, 0.5)"
        ctx.lineWidth = 1
        ctx.beginPath()
        for (let i = 0; i < 4; i++) {
          const px = x + 8 + i * ((w - 16) / 3)
          const py = y + yOffset + h / 2 + Math.sin(time * 2 + i + delay) * 6
          if (i === 0) ctx.moveTo(px, py)
          else ctx.lineTo(px, py)
        }
        ctx.stroke()
      }

      drawPanel(centerX - radius - 80, centerY - 60, 60, 40, 0)
      drawPanel(centerX + radius + 20, centerY - 40, 60, 40, 1)
      drawPanel(centerX - radius - 60, centerY + 40, 50, 35, 2)
      drawPanel(centerX + radius + 30, centerY + 50, 55, 35, 3)

      time += 0.01
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
