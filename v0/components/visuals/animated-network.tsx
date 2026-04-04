"use client"

import { useEffect, useRef } from "react"

export function AnimatedNetwork({ className = "" }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext("2d")
    if (!ctx) return

    let animationId: number
    let time = 0

    interface Node {
      x: number
      y: number
      vx: number
      vy: number
      radius: number
      color: string
      pulsePhase: number
    }

    const nodes: Node[] = []
    const colors = ["#00E5CC", "#10B981", "#3B82F6", "#F59E0B"]

    const resize = () => {
      const dpr = window.devicePixelRatio || 1
      const rect = canvas.getBoundingClientRect()
      canvas.width = rect.width * dpr
      canvas.height = rect.height * dpr
      ctx.scale(dpr, dpr)

      // Initialize nodes
      nodes.length = 0
      const width = rect.width
      const height = rect.height
      const nodeCount = 25

      for (let i = 0; i < nodeCount; i++) {
        nodes.push({
          x: Math.random() * width,
          y: Math.random() * height,
          vx: (Math.random() - 0.5) * 0.5,
          vy: (Math.random() - 0.5) * 0.5,
          radius: Math.random() * 3 + 2,
          color: colors[Math.floor(Math.random() * colors.length)],
          pulsePhase: Math.random() * Math.PI * 2,
        })
      }
    }

    resize()
    window.addEventListener("resize", resize)

    const draw = () => {
      const width = canvas.width / (window.devicePixelRatio || 1)
      const height = canvas.height / (window.devicePixelRatio || 1)

      ctx.clearRect(0, 0, width, height)

      // Update and draw connections
      const connectionDistance = 100

      for (let i = 0; i < nodes.length; i++) {
        const node = nodes[i]

        // Update position
        node.x += node.vx
        node.y += node.vy

        // Bounce off walls
        if (node.x < 0 || node.x > width) node.vx *= -1
        if (node.y < 0 || node.y > height) node.vy *= -1

        // Keep in bounds
        node.x = Math.max(0, Math.min(width, node.x))
        node.y = Math.max(0, Math.min(height, node.y))

        // Draw connections
        for (let j = i + 1; j < nodes.length; j++) {
          const other = nodes[j]
          const dx = other.x - node.x
          const dy = other.y - node.y
          const distance = Math.sqrt(dx * dx + dy * dy)

          if (distance < connectionDistance) {
            const alpha = (1 - distance / connectionDistance) * 0.4

            ctx.beginPath()
            ctx.moveTo(node.x, node.y)
            ctx.lineTo(other.x, other.y)
            ctx.strokeStyle = `rgba(0, 229, 204, ${alpha})`
            ctx.lineWidth = 1
            ctx.stroke()

            // Animate data packets along some connections
            if (distance < 60 && Math.random() > 0.99) {
              const packetPos = (time * 2) % 1
              const px = node.x + dx * packetPos
              const py = node.y + dy * packetPos

              ctx.beginPath()
              ctx.arc(px, py, 2, 0, Math.PI * 2)
              ctx.fillStyle = "#00E5CC"
              ctx.fill()
            }
          }
        }
      }

      // Helper function to convert hex to rgba
      const hexToRgba = (hex: string, alpha: number) => {
        const r = parseInt(hex.slice(1, 3), 16)
        const g = parseInt(hex.slice(3, 5), 16)
        const b = parseInt(hex.slice(5, 7), 16)
        return `rgba(${r}, ${g}, ${b}, ${alpha})`
      }

      // Draw nodes
      nodes.forEach((node) => {
        const pulse = Math.sin(time * 2 + node.pulsePhase) * 0.3 + 1

        // Glow
        const glow = ctx.createRadialGradient(node.x, node.y, 0, node.x, node.y, node.radius * 4 * pulse)
        glow.addColorStop(0, hexToRgba(node.color, 0.25))
        glow.addColorStop(1, "transparent")
        ctx.fillStyle = glow
        ctx.beginPath()
        ctx.arc(node.x, node.y, node.radius * 4 * pulse, 0, Math.PI * 2)
        ctx.fill()

        // Core
        ctx.beginPath()
        ctx.arc(node.x, node.y, node.radius * pulse, 0, Math.PI * 2)
        ctx.fillStyle = node.color
        ctx.fill()

        // Inner bright spot
        ctx.beginPath()
        ctx.arc(node.x - node.radius * 0.3, node.y - node.radius * 0.3, node.radius * 0.4, 0, Math.PI * 2)
        ctx.fillStyle = "rgba(255, 255, 255, 0.5)"
        ctx.fill()
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
