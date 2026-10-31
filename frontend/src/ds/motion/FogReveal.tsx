import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { DUR, FOG } from '../tokens'
import { cx } from '../util'
import s from './FogReveal.module.css'

/** CSS pixels per canvas pixel; the browser's upscale plus a light blur makes soft cloud. */
const SCALE = 5
const EDGE = 0.12
const HIDDEN = -0.2
const CLEAR = 1.2

interface Field { w: number; h: number; n: Float32Array; tone: Float32Array }

function mulberry32(seed: number) {
  return () => {
    seed |= 0
    seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const smooth = (t: number) => t * t * (3 - 2 * t)
const easeInOut = (t: number) => (t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2)

function makeField(w: number, h: number, origin: { x: number; y: number }): Field {
  const rand = mulberry32(1997)
  // Value noise; the grid has margin for the offset sampling of the wisp octave.
  const octave = (cell: number) => {
    const gw = Math.ceil((w + 64) / cell) + 2
    const gh = Math.ceil((h + 64) / cell) + 2
    const grid = Float32Array.from({ length: gw * gh }, rand)
    return (x: number, y: number) => {
      const gx = x / cell, gy = y / cell
      const x0 = Math.floor(gx), y0 = Math.floor(gy)
      const fx = smooth(gx - x0), fy = smooth(gy - y0)
      const i = y0 * gw + x0
      const top = grid[i] + (grid[i + 1] - grid[i]) * fx
      const bottom = grid[i + gw] + (grid[i + gw + 1] - grid[i + gw]) * fx
      return top + (bottom - top) * fy
    }
  }
  const coarse = octave(30), mid = octave(13), fine = octave(5), wisp = octave(18)
  const n = new Float32Array(w * h)
  const tone = new Float32Array(w * h)
  const ox = origin.x * w, oy = origin.y * h
  const reach = Math.hypot(Math.max(ox, w - ox), Math.max(oy, h - oy))
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = y * w + x
      const dist = Math.min(1, Math.hypot(x - ox, y - oy) / reach)
      const v = 0.5 * coarse(x, y) + 0.32 * mid(x, y) + 0.18 * fine(x, y)
      n[i] = 0.5 * v + 0.5 * dist
      tone[i] = wisp(x + 40, y + 17)
    }
  }
  return { w, h, n, tone }
}

function paint(canvas: HTMLCanvasElement, field: Field, p: number) {
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  const img = ctx.createImageData(field.w, field.h)
  const d = img.data
  const [br, bg, bb] = FOG.base
  const [wr, wg, wb] = FOG.wisp
  for (let i = 0, j = 0; i < field.n.length; i++, j += 4) {
    const t = Math.min(1, Math.max(0, (field.n[i] - (p - EDGE)) / (2 * EDGE)))
    const tone = field.tone[i]
    d[j] = br + tone * wr
    d[j + 1] = bg + tone * wg
    d[j + 2] = bb + tone * wb
    d[j + 3] = smooth(t) * 255
  }
  ctx.putImageData(img, 0, 0)
}

interface FogRevealProps {
  /** false: fully fogged. Switching to true dissolves the fog outward from `origin`. */
  revealed: boolean
  /** Where the fog clears first, as fractions of the area (default: top centre, under the clock). */
  origin?: { x: number; y: number }
  onRevealed?(): void
  /** Shown over the fog while it is not revealed, e.g. the waiting card. */
  children?: ReactNode
  className?: string
}

/**
 * Fog of war over its positioned parent. The one motion in the app that is not a direct
 * reply to a click: it plays once when the game connects. Unmounts its canvas when clear.
 */
export function FogReveal({ revealed, origin = { x: 0.5, y: 0 }, onRevealed, children, className }: FogRevealProps) {
  const [visible, setVisible] = useState(!revealed)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const fieldRef = useRef<Field | null>(null)
  const progress = useRef(revealed ? CLEAR : HIDDEN)
  const done = useRef(onRevealed)
  done.current = onRevealed

  useLayoutEffect(() => {
    if (!visible) return
    const canvas = canvasRef.current!
    const build = () => {
      const r = canvas.getBoundingClientRect()
      canvas.width = Math.max(16, Math.round(r.width / SCALE))
      canvas.height = Math.max(16, Math.round(r.height / SCALE))
      fieldRef.current = makeField(canvas.width, canvas.height, origin)
      paint(canvas, fieldRef.current, progress.current)
    }
    build()
    const ro = new ResizeObserver(build)
    ro.observe(canvas)
    return () => ro.disconnect()
  }, [visible, origin.x, origin.y])

  useEffect(() => {
    if (!revealed && !visible) {
      progress.current = CLEAR
      setVisible(true)
      return
    }
    if (!visible) return
    const target = revealed ? CLEAR : HIDDEN
    const from = progress.current
    if (from === target) return
    const dur = (revealed ? DUR.reveal : DUR.reveal * 0.6) * 1000
    const t0 = performance.now()
    let raf = 0
    const step = (now: number) => {
      const t = Math.min(1, (now - t0) / dur)
      progress.current = from + (target - from) * easeInOut(t)
      if (canvasRef.current && fieldRef.current) paint(canvasRef.current, fieldRef.current, progress.current)
      if (t < 1) raf = requestAnimationFrame(step)
      else if (revealed) {
        setVisible(false)
        done.current?.()
      }
    }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
  }, [revealed, visible])

  if (!visible) return null

  return (
    <div className={cx(s.fog, className)} data-revealed={revealed || undefined}>
      <canvas ref={canvasRef} className={s.canvas} aria-hidden="true" />
      <AnimatePresence>
        {!revealed && children && (
          <motion.div
            className={s.content}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0, transition: { duration: 0.25 } }}
          >
            {children}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
