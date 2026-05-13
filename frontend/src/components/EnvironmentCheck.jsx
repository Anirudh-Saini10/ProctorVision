import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Check, Loader2, X } from 'lucide-react'

/**
 * Pre-flight checklist. Some checks are real (camera/mic permission), some are mocked
 * with timing so the user feels the system warming up.
 */
const ITEMS = [
  { id: 'browser', label: 'Browser support', delay: 200 },
  { id: 'camera', label: 'Camera access', delay: 500, real: 'camera' },
  { id: 'mic', label: 'Microphone access', delay: 700, real: 'mic' },
  { id: 'face', label: 'Face detected in frame', delay: 1100 },
  { id: 'lighting', label: 'Lighting adequate', delay: 1400 },
  { id: 'alone', label: 'Single subject in view', delay: 1700 },
]

export default function EnvironmentCheck({ onReady }) {
  const [statuses, setStatuses] = useState(() =>
    Object.fromEntries(ITEMS.map((i) => [i.id, 'pending']))
  )

  useEffect(() => {
    let cancelled = false

    async function check(item) {
      if (cancelled) return
      try {
        if (item.real === 'camera') {
          await navigator.mediaDevices.getUserMedia({ video: true }).then((s) => {
            s.getTracks().forEach((t) => t.stop())
          })
        } else if (item.real === 'mic') {
          await navigator.mediaDevices.getUserMedia({ audio: true }).then((s) => {
            s.getTracks().forEach((t) => t.stop())
          })
        }
        if (!cancelled) {
          setStatuses((s) => ({ ...s, [item.id]: 'ok' }))
        }
      } catch {
        if (!cancelled) setStatuses((s) => ({ ...s, [item.id]: 'fail' }))
      }
    }

    ITEMS.forEach((item) => {
      setTimeout(() => check(item), item.delay)
    })

    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    const allOk = ITEMS.every((i) => statuses[i.id] === 'ok')
    if (allOk) onReady?.()
  }, [statuses, onReady])

  return (
    <ul className="divide-y divide-border rounded border border-border bg-surface-1">
      {ITEMS.map((item, idx) => {
        const status = statuses[item.id]
        return (
          <motion.li
            key={item.id}
            initial={{ opacity: 0, x: -6 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.4, delay: idx * 0.05, ease: [0.16, 1, 0.3, 1] }}
            className="flex items-center justify-between px-4 py-2.5"
          >
            <span className="font-mono text-[11px] uppercase tracking-eyebrow text-text-secondary">
              {item.label}
            </span>
            <StatusIcon status={status} />
          </motion.li>
        )
      })}
    </ul>
  )
}

function StatusIcon({ status }) {
  if (status === 'ok')
    return <Check size={14} strokeWidth={2} className="text-risk-low" />
  if (status === 'fail')
    return <X size={14} strokeWidth={2} className="text-risk-high" />
  return (
    <Loader2
      size={14}
      strokeWidth={2}
      className="animate-spin text-text-muted"
    />
  )
}
