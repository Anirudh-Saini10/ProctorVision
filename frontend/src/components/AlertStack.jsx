import { AnimatePresence, motion } from 'framer-motion'
import { AlertTriangle, ShieldAlert, Eye } from 'lucide-react'

const tone = {
  low: { color: 'text-risk-low', bar: 'bg-risk-low', icon: Eye, label: 'INFO' },
  medium: { color: 'text-risk-medium', bar: 'bg-risk-medium', icon: AlertTriangle, label: 'WARN' },
  high: { color: 'text-risk-high', bar: 'bg-risk-high', icon: ShieldAlert, label: 'CRIT' },
}

/**
 * Stack of slide-in alerts. Newest on top.
 * Caller controls the alert list; alerts auto-disappear after their TTL.
 */
export default function AlertStack({ alerts = [] }) {
  return (
    <div className="pointer-events-none fixed bottom-6 right-6 z-30 flex w-[320px] flex-col gap-2">
      <AnimatePresence>
        {alerts.map((a) => {
          const t = tone[a.severity] ?? tone.medium
          const Icon = t.icon
          return (
            <motion.div
              key={a.id}
              layout
              initial={{ opacity: 0, x: 24, scale: 0.98 }}
              animate={{ opacity: 1, x: 0, scale: 1 }}
              exit={{ opacity: 0, x: 24, scale: 0.96 }}
              transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
              className="pointer-events-auto relative overflow-hidden rounded border border-border bg-surface-2"
            >
              <div className={`absolute inset-y-0 left-0 w-0.5 ${t.bar}`} />
              <div className="flex gap-3 p-3 pl-4">
                <Icon size={14} strokeWidth={1.75} className={`mt-0.5 ${t.color}`} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <span className={`font-mono text-[10px] uppercase tracking-eyebrow ${t.color}`}>
                      {t.label}
                    </span>
                    <span className="font-mono text-[10px] text-text-muted">
                      {a.timestamp}
                    </span>
                  </div>
                  <p className="mt-1 text-[12px] text-text-primary">{a.title}</p>
                  {a.detail && (
                    <p className="mt-0.5 text-[11px] text-text-muted">{a.detail}</p>
                  )}
                </div>
              </div>
            </motion.div>
          )
        })}
      </AnimatePresence>
    </div>
  )
}
