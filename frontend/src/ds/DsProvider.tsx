import type { ReactNode } from 'react'
import { MotionConfig } from 'motion/react'
import { IconDefs } from './icons/Icon'
import { Announcer, BountyLayer } from './motion/Layers'
import { TooltipProvider } from './primitives/Tooltip'
import { useIdleAttribute } from './hooks'

/**
 * Mount once at the root of every page. Provides icon gradients, the bounty and
 * announcement layers, tooltip timing, reduced-motion handling and the idle pause.
 */
export function DsProvider({ children }: { children: ReactNode }) {
  useIdleAttribute()
  return (
    <MotionConfig reducedMotion="user">
      <TooltipProvider delayDuration={300} skipDelayDuration={200}>
        <IconDefs />
        {children}
        <Announcer />
        <BountyLayer />
      </TooltipProvider>
    </MotionConfig>
  )
}
