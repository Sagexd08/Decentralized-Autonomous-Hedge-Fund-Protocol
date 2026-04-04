"use client"

import { useEffect, useRef } from "react"

export function AnimatedCircuit({ className = "" }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext("2d")
    if (!ctx) return

    let animationId: number
    let time = 0

    interface PathSegment {
      points: { x: number; y: number }[]
      color: string
      pulseOffset: number
    }

    const paths: PathSegment[] = []

    const resize = () => {
      const dpr = window.devicePixelRatio || 1
      const rect = canvas.getBoundingClientRect()
      canvas.width = rect.width * dpr
      canvas.height = rect.height * dpr
      ctx.scale(dpr, dpr)

      // Generate circuit paths
      paths.length = 0
      const width = rect.width
      const height = rect.height
      const gridSize = 20
      const colors = ["#00E5CC", "#F59E0B", "#3B82F6"]

      for (let i = 0; i < 15; i++) {
        const points: { x: number; y: number }[] = []
        let x = Math.floor(Math.random() * (width / gridSize)) * gridSize
        let y = Math.floor(Math.random() * (height / gridSize)) * gridSize
        points.push({ x, y })

        const segmentCount = Math.floor(Math.random() * 6) + 3
        for (let j = 0; j < segmentCount; j++) {
          const direction = Math.floor(Math.random() * 4)
          const length = (Math.floor(Math.random() * 4) + 2) * gridSize

          switch (direction) {
            case 0:
              x = Math.min(width, x + length)
              break
            case 1:
              x = Math.max(0, x - length)
              break
            case 2:
              y = Math.min(height, y + length)
              break
            case 3:
              y = Math.max(0, y - length)
              break
          }
          points.push({ x, y })
        }

        paths.push({
          points,
          color: colors[Math.floor(Math.random() * colors.length)],
          pulseOffset: Math.random() * Math.PI * 2,
        })
      }
    }

    resize()
    window.addEventListener("resize", resize)

    const draw = () => {
      const width = canvas.width / (window.devicePixelRatio || 1)
      const height = canvas.height / (window.devicePixelRatio || 1)

      ctx.clearRect(0, 0, width, height)

      // Draw grid dots
      const gridSize = 20
      for (let x = 0; x < width; x += gridSize) {
        for (let y = 0; y < height; y += gridSize) {
          ctx.beginPath()
          ctx.arc(x, y, 1, 0, Math.PI * 2)
          ctx.fillStyle = "rgba(0, 229, 204, 0.1)"
          ctx.fill()
        }
      }

      // Helper function to convert hex to rgba
      const hexToRgba = (hex: string, alpha: number) => {
        const r = parseInt(hex.slice(1, 3), 16)
        const g = parseInt(hex.slice(3, 5), 16)
        const b = parseInt(hex.slice(5, 7), 16)
        return `rgba(${r}, ${g}, ${b}, ${alpha})`
      }

      // Draw paths
      paths.forEach((path) => {
        if (path.points.length < 2) return

        // Draw base path
        ctx.beginPath()
        ctx.moveTo(path.points[0].x, path.points[0].y)
        for (let i = 1; i < path.points.length; i++) {
          ctx.lineTo(path.points[i].x, path.points[i].y)
        }
        ctx.strokeStyle = hexToRgba(path.color, 0.19)
        ctx.lineWidth = 2
        ctx.stroke()

        // Draw nodes at corners
        path.points.forEach((point, i) => {
          const pulse = Math.sin(time * 2 + path.pulseOffset + i * 0.5) * 0.3 + 1

          if (i === 0 || i === path.points.length - 1) {
            // Terminal nodes
            ctx.beginPath()
            ctx.arc(point.x, point.y, 4 * pulse, 0, Math.PI * 2)
            ctx.fillStyle = path.color
            ctx.fill()

            // Glow
            const glow = ctx.createRadialGradient(point.x, point.y, 0, point.x, point.y, 12)
            glow.addColorStop(0, hexToRgba(path.color, 0.38))
            glow.addColorStop(1, "transparent")
            ctx.fillStyle = glow
            ctx.beginPath()
            ctx.arc(point.x, point.y, 12, 0, Math.PI * 2)
            ctx.fill()
          } else {
            // Corner nodes
            ctx.beginPath()
            ctx.arc(point.x, point.y, 2, 0, Math.PI * 2)
            ctx.fillStyle = hexToRgba(path.color, 0.5)
            ctx.fill()
          }
        })

        // Animated pulse along path
        const totalLength = path.points.reduce((acc, point, i) => {
          if (i === 0) return 0
          const prev = path.points[i - 1]
          return acc + Math.sqrt(Math.pow(point.x - prev.x, 2) + Math.pow(point.y - prev.y, 2))
        }, 0)

        const pulsePos = ((time * 50 + path.pulseOffset * 100) % totalLength) / totalLength
        let accumulated = 0

        for (let i = 1; i < path.points.length; i++) {
          const prev = path.points[i - 1]
          const curr = path.points[i]
          const segmentLength = Math.sqrt(Math.pow(curr.x - prev.x, 2) + Math.pow(curr.y - prev.y, 2))
          const segmentStart = accumulated / totalLength
          const segmentEnd = (accumulated + segmentLength) / totalLength

          if (pulsePos >= segmentStart && pulsePos <= segmentEnd) {
            const t = (pulsePos - segmentStart) / (segmentEnd - segmentStart)
            const px = prev.x + (curr.x - prev.x) * t
            const py = prev.y + (curr.y - prev.y) * t

            // Pulse glow
            const pulseGlow = ctx.createRadialGradient(px, py, 0, px, py, 8)
            pulseGlow.addColorStop(0, path.color)
            pulseGlow.addColorStop(0.5, hexToRgba(path.color, 0.38))
            pulseGlow.addColorStop(1, "transparent")
            ctx.fillStyle = pulseGlow
            ctx.beginPath()
            ctx.arc(px, py, 8, 0, Math.PI * 2)
            ctx.fill()

            ctx.beginPath()
            ctx.arc(px, py, 3, 0, Math.PI * 2)
            ctx.fillStyle = "#fff"
            ctx.fill()
          }

          accumulated += segmentLength
        }
      })

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
