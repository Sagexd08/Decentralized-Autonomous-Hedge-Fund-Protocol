import dynamic from 'next/dynamic'

const NextAppRoot = dynamic(() => import('@/components/NextAppRoot'), {
  ssr: false,
})

export default function CatchAllRoutePage() {
  return <NextAppRoot />
}
