"use client"

import { useEffect, useRef } from "react"

export function AnimatedGauge({ className = "" }: { className?: string }) {
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
      const maxRadius = Math.min(width, height) * 0.4

      // Draw concentric rings
      const rings = [
        { radius: maxRadius * 0.95, color: "#F59E0B", width: 8, speed: 0.5, opacity: 0.6 },
        { radius: maxRadius * 0.85, color: "#F59E0B", width: 4, speed: -0.3, opacity: 0.4 },
        { radius: maxRadius * 0.7, color: "#3B82F6", width: 8, speed: 0.4, opacity: 0.6 },
        { radius: maxRadius * 0.6, color: "#3B82F6", width: 4, speed: -0.25, opacity: 0.4 },
        { radius: maxRadius * 0.45, color: "#3B82F6", width: 6, speed: 0.35, opacity: 0.5 },
        { radius: maxRadius * 0.3, color: "#00E5CC", width: 4, speed: -0.2, opacity: 0.6 },
      ]

      // Helper function to convert hex to rgba
      const hexToRgba = (hex: string, alpha: number) => {
        const r = parseInt(hex.slice(1, 3), 16)
        const g = parseInt(hex.slice(3, 5), 16)
        const b = parseInt(hex.slice(5, 7), 16)
        return `rgba(${r}, ${g}, ${b}, ${alpha})`
      }

      rings.forEach((ring) => {
        const rotation = time * ring.speed

        // Draw segmented arc
        const segments = 8
        const gapAngle = 0.1
        const segmentAngle = (Math.PI * 2) / segments - gapAngle

        for (let i = 0; i < segments; i++) {
          const startAngle = rotation + (i * Math.PI * 2) / segments
          const endAngle = startAngle + segmentAngle

          ctx.beginPath()
          ctx.arc(centerX, centerY, ring.radius, startAngle, endAngle)
          ctx.strokeStyle = hexToRgba(ring.color, ring.opacity)
          ctx.lineWidth = ring.width
          ctx.lineCap = "round"
          ctx.stroke()
        }
      })

      // Draw tick marks
      const tickCount = 36
      for (let i = 0; i < tickCount; i++) {
        const angle = (i / tickCount) * Math.PI * 2 - Math.PI / 2
        const innerRadius = maxRadius * 0.15
        const outerRadius = maxRadius * 0.2

        const x1 = centerX + Math.cos(angle) * innerRadius
        const y1 = centerY + Math.sin(angle) * innerRadius
        const x2 = centerX + Math.cos(angle) * outerRadius
        const y2 = centerY + Math.sin(angle) * outerRadius

        ctx.beginPath()
        ctx.moveTo(x1, y1)
        ctx.lineTo(x2, y2)
        ctx.strokeStyle = i % 3 === 0 ? "rgba(0, 229, 204, 0.6)" : "rgba(0, 229, 204, 0.2)"
        ctx.lineWidth = i % 3 === 0 ? 2 : 1
        ctx.stroke()
      }

      // Center dot
      const centerGlow = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, 15)
      centerGlow.addColorStop(0, "#00E5CC")
      centerGlow.addColorStop(0.5, "rgba(0, 229, 204, 0.3)")
      centerGlow.addColorStop(1, "transparent")
      ctx.fillStyle = centerGlow
      ctx.beginPath()
      ctx.arc(centerX, centerY, 15, 0, Math.PI * 2)
      ctx.fill()

      ctx.beginPath()
      ctx.arc(centerX, centerY, 4, 0, Math.PI * 2)
      ctx.fillStyle = "#00E5CC"
      ctx.fill()

      // Animated scanner line
      const scanAngle = time * 1.5
      ctx.beginPath()
      ctx.moveTo(centerX, centerY)
      ctx.lineTo(
        centerX + Math.cos(scanAngle) * maxRadius * 0.95,
        centerY + Math.sin(scanAngle) * maxRadius * 0.95
      )
      const scanGradient = ctx.createLinearGradient(
        centerX,
        centerY,
        centerX + Math.cos(scanAngle) * maxRadius,
        centerY + Math.sin(scanAngle) * maxRadius
      )
      scanGradient.addColorStop(0, "rgba(0, 229, 204, 0.8)")
      scanGradient.addColorStop(1, "transparent")
      ctx.strokeStyle = scanGradient
      ctx.lineWidth = 2
      ctx.stroke()

      // Scanner sweep gradient
      ctx.beginPath()
      ctx.moveTo(centerX, centerY)
      ctx.arc(centerX, centerY, maxRadius * 0.95, scanAngle - 0.5, scanAngle, false)
      ctx.closePath()
      const sweepGradient = ctx.createConicGradient(scanAngle - 0.5, centerX, centerY)
      sweepGradient.addColorStop(0, "transparent")
      sweepGradient.addColorStop(0.8, "rgba(0, 229, 204, 0.1)")
      sweepGradient.addColorStop(1, "rgba(0, 229, 204, 0.05)")
      ctx.fillStyle = sweepGradient
      ctx.fill()

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
