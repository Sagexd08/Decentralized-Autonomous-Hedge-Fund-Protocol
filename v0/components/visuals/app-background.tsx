"use client"

import BorderGlow from "@/components/BorderGlow"

export function AppBackground() {
  return (
    <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden opacity-[0.16]">
      <div className="absolute inset-0">
        <BorderGlow
          edgeSensitivity={14}
          glowColor="40 80 80"
          backgroundColor="#060010"
          borderRadius={23}
          glowRadius={24}
          glowIntensity={1}
          coneSpread={25}
          animated={false}
          colors={["#c084fc", "#f472b6", "#38bdf8"]}
          fillOpacity={0.24}
          className="h-full w-full"
        >
          <div className="h-full w-full" />
        </BorderGlow>
      </div>
    </div>
  )
}
