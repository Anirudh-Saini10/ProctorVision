import { motion, useMotionValue, useTransform, animate } from 'framer-motion'
import { useEffect, useState } from 'react'

/**
 * Circular risk gauge. 0-100. Color band shifts at thresholds.
 * Sweeps smoothly to new value with spring-like easing.
 */
export default function RiskGauge({ value = 0, size = 140, label = 'Risk' }) {
  const radius = size / 2 - 8
  const circumference = 2 * Math.PI * radius
  const mv = useMotionValue(0)
  const [display, setDisplay] = useState(0)

  useEffect(() => {
    const controls = animate(mv, value, {
      duration: 0.8,
      ease: [0.16, 1, 0.3, 1],
      onUpdate: (v) => setDisplay(Math.round(v)),
    })
    return controls.stop
  }, [value, mv])

  const dash = useTransform(mv, (v) => circumference * (1 - v / 100))

  const tone =
    display >= 70 ? 'text-risk-high' : display >= 35 ? 'text-risk-medium' : 'text-risk-low'
  const stroke =
    display >= 70 ? '#f87171' : display >= 35 ? '#facc15' : '#4ade80'

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth="2"
        />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={stroke}
          strokeWidth="2"
          strokeLinecap="round"
          style={{
            strokeDasharray: circumference,
            strokeDashoffset: dash,
            transition: 'stroke 0.4s ease',
          }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={`font-mono text-3xl tabular-nums ${tone}`}>
          {display}
        </span>
        <span className="font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
          {label} / 100
        </span>
      </div>
    </div>
  )
}
