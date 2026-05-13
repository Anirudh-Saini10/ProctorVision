import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import LiveDot from './LiveDot.jsx'

/**
 * Ambient "live preview" tile shown on the landing page.
 * Mocks the look of a real telemetry feed so the page feels alive.
 * Numbers nudge slightly every ~1.2s. No real data.
 */
export default function TelemetryTile() {
  const [tick, setTick] = useState(0)
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 1200)
    return () => clearInterval(id)
  }, [])

  // deterministic-ish jitter so it looks alive but stable
  const jitter = (seed) => {
    const v = Math.sin(tick * 0.9 + seed) * 0.5 + 0.5
    return v
  }

  const gaze = (jitter(1) * 0.08).toFixed(3)
  const yaw = (jitter(2) * 3 - 1.5).toFixed(2)
  const risk = Math.round(jitter(3) * 12 + 4)
  const fps = (jitter(4) * 4 + 26).toFixed(1)

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1], delay: 0.3 }}
      className="relative w-full overflow-hidden rounded border border-border bg-surface-1"
    >
      {/* top inner highlight */}
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-white/[0.05]" />

      {/* header */}
      <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
        <div className="flex items-center gap-3">
          <LiveDot variant="online" />
          <span className="font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
            live telemetry
          </span>
        </div>
        <span className="font-mono text-[10px] text-text-muted">
          session://preview
        </span>
      </div>

      {/* metrics row */}
      <div className="grid grid-cols-4 divide-x divide-border">
        <Metric label="gaze.dev" value={gaze} unit="" />
        <Metric label="head.yaw" value={yaw} unit="°" />
        <Metric label="risk" value={risk} unit="/100" tone={risk > 30 ? 'warn' : 'normal'} />
        <Metric label="fps" value={fps} unit="" />
      </div>

      {/* mock sparkline */}
      <div className="border-t border-border px-4 py-3">
        <Sparkline tick={tick} />
      </div>

      {/* shimmer overlay — extremely subtle */}
      <div
        className="pointer-events-none absolute inset-0 animate-shimmer opacity-[0.04]"
        style={{
          background:
            'linear-gradient(110deg, transparent 35%, rgba(255,255,255,0.6) 50%, transparent 65%)',
          backgroundSize: '200% 100%',
        }}
      />
    </motion.div>
  )
}

function Metric({ label, value, unit, tone = 'normal' }) {
  const color = tone === 'warn' ? 'text-risk-medium' : 'text-text-primary'
  return (
    <div className="px-4 py-3">
      <div className="font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
        {label}
      </div>
      <div className={`mt-1 font-mono text-lg tabular-nums ${color}`}>
        {value}
        <span className="ml-0.5 text-xs text-text-muted">{unit}</span>
      </div>
    </div>
  )
}

function Sparkline({ tick }) {
  const points = Array.from({ length: 40 }, (_, i) => {
    const x = (i / 39) * 100
    const phase = tick * 0.3 + i * 0.4
    const y = 50 + Math.sin(phase) * 18 + Math.sin(phase * 0.5) * 8
    return `${x.toFixed(2)},${y.toFixed(2)}`
  }).join(' ')
  return (
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="h-16 w-full">
      <defs>
        <linearGradient id="spark-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.25" />
          <stop offset="100%" stopColor="#3b82f6" stopOpacity="0" />
        </linearGradient>
      </defs>
      <polyline
        points={points}
        fill="none"
        stroke="#3b82f6"
        strokeWidth="1"
        strokeLinejoin="round"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
      />
      <polygon
        points={`0,100 ${points} 100,100`}
        fill="url(#spark-fill)"
      />
    </svg>
  )
}
