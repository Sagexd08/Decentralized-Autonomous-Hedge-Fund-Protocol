import { BellRing, CalendarDays, Globe2, Radar, Sparkles } from 'lucide-react'

import { cn } from '@/lib/utils'
import { Calendar } from '@/components/ui/calendar'
import AnimatedBeamMultipleOutputDemo from '@/registry/example/animated-beam-multiple-outputs'
import AnimatedListDemo from '@/registry/example/animated-list-demo'
import { BentoCard, BentoGrid } from '@/registry/magicui/bento-grid'
import { Marquee } from '@/registry/magicui/marquee'
import Globe3DDemo from '@/components/Globe3DDemo'

const intelligenceFeed = [
  { label: 'Regime', value: 'High-vol breakout' },
  { label: 'Spread', value: '42 bps widening' },
  { label: 'Confidence', value: '0.87' },
]

const signalPills = ['Routing', 'Inference', 'Risk Engine', 'Execution']

export default function BentoDemo() {
  return (
    <BentoGrid className="auto-rows-[18rem]">
      <BentoCard
        name="Signal Topology"
        description="Cross-agent routing and decision fan-out."
        className="md:col-span-2"
        icon={<Radar className="size-5" />}
        background={
          <div className="absolute inset-0 p-6">
            <AnimatedBeamMultipleOutputDemo className="h-full w-full opacity-70" />
          </div>
        }
      />
      <BentoCard
        name="Decision Queue"
        description="Fresh events ranked by urgency and edge."
        icon={<BellRing className="size-5" />}
        background={
          <div className="absolute inset-0 p-6 pt-16">
            <AnimatedListDemo items={intelligenceFeed} />
          </div>
        }
      />
      <BentoCard
        name="Global Reach"
        description="Visual coverage of the capital network."
        icon={<Globe2 className="size-5" />}
        className="md:row-span-2"
        background={
          <div className="absolute inset-0 overflow-hidden rounded-[2rem] opacity-80">
            <Globe3DDemo />
          </div>
        }
      />
      <BentoCard
        name="Ops Calendar"
        description="Strategy windows and scheduled rebalance moments."
        icon={<CalendarDays className="size-5" />}
        background={
          <div className="absolute inset-0 p-6 pt-16">
            <Calendar className="rounded-3xl border border-white/10 bg-black/20 p-4 text-white/70" />
          </div>
        }
      />
      <BentoCard
        name="Streaming Tags"
        description="Subsystems broadcasting in parallel."
        icon={<Sparkles className="size-5" />}
        className="md:col-span-2"
        background={
          <div className="absolute inset-x-0 top-1/2 -translate-y-1/2">
            <Marquee>
              {signalPills.map((pill) => (
                <span
                  key={pill}
                  className={cn(
                    'mx-2 inline-flex rounded-full border border-white/10 bg-white/5 px-4 py-2',
                    'text-xs uppercase tracking-[0.28em] text-white/60',
                  )}
                >
                  {pill}
                </span>
              ))}
            </Marquee>
          </div>
        }
      />
    </BentoGrid>
  )
}
