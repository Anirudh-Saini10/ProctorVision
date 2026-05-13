import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Square } from 'lucide-react'
import PageShell from '../components/PageShell.jsx'
import WebcamFeed from '../components/WebcamFeed.jsx'
import RiskGauge from '../components/RiskGauge.jsx'
import AlertStack from '../components/AlertStack.jsx'
import LiveDot from '../components/LiveDot.jsx'
import { useSession } from '../state/SessionContext.jsx'

/**
 * Active proctored session.
 * Backend WS will be wired in a later phase. Right now: simulated risk + alerts
 * so the screen is fully alive for the design demo.
 */
export default function Exam() {
  const navigate = useNavigate()
  const { name, code, strictness } = useSession()
  const [risk, setRisk] = useState(8)
  const [alerts, setAlerts] = useState([])
  const startedAt = useRef(performance.now())
  const [elapsedStr, setElapsedStr] = useState('00:00')

  // elapsed clock
  useEffect(() => {
    const id = setInterval(() => {
      const t = Math.floor((performance.now() - startedAt.current) / 1000)
      const m = String(Math.floor(t / 60)).padStart(2, '0')
      const s = String(t % 60).padStart(2, '0')
      setElapsedStr(`${m}:${s}`)
    }, 500)
    return () => clearInterval(id)
  }, [])

  // ambient risk wobble (placeholder until WS is wired)
  useEffect(() => {
    const id = setInterval(() => {
      setRisk((r) => {
        const drift = (Math.random() - 0.5) * 6
        const next = Math.max(2, Math.min(95, r + drift))
        return Math.round(next)
      })
    }, 1400)
    return () => clearInterval(id)
  }, [])

  // demo alert injection — every ~12s a fake violation appears
  useEffect(() => {
    const samples = [
      { severity: 'low', title: 'Brief gaze drift', detail: 'Off-task for 2.1s' },
      { severity: 'medium', title: 'Head turn detected', detail: 'Yaw exceeded threshold' },
      { severity: 'medium', title: 'Lip movement', detail: 'Possible vocalization' },
      { severity: 'high', title: 'Phone-like object', detail: 'Confidence 0.84' },
    ]
    const id = setInterval(() => {
      const sample = samples[Math.floor(Math.random() * samples.length)]
      const ts = new Date()
      const stamp = `${String(ts.getHours()).padStart(2, '0')}:${String(ts.getMinutes()).padStart(2, '0')}:${String(ts.getSeconds()).padStart(2, '0')}`
      const alert = { id: crypto.randomUUID(), timestamp: stamp, ...sample }
      setAlerts((prev) => [alert, ...prev].slice(0, 4))
      // auto-dismiss after 6s
      setTimeout(() => {
        setAlerts((prev) => prev.filter((a) => a.id !== alert.id))
      }, 6000)
    }, 9000)
    return () => clearInterval(id)
  }, [])

  const onEnd = () => {
    navigate('/student/done', { replace: true })
  }

  return (
    <PageShell className="!flex-none">
      {/* dense status strip directly below TopNav */}
      <div className="border-b border-border bg-surface-1/50 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-6 px-6 py-2.5">
          <div className="flex items-center gap-6">
            <LiveDot variant="online" label="recording" />
            <Stat label="elapsed" value={elapsedStr} mono />
            <Stat label="candidate" value={name || '—'} />
            <Stat label="session" value={code} mono />
            <Stat label="strictness" value={strictness.label.toUpperCase()} mono />
          </div>
          <button
            type="button"
            onClick={onEnd}
            className="inline-flex items-center gap-2 rounded border border-border bg-surface-2 px-3 py-1.5 text-[12px] font-medium text-text-secondary transition-colors hover:border-risk-high hover:text-risk-high"
          >
            <Square size={11} strokeWidth={2.25} />
            End session
          </button>
        </div>
      </div>

      <section className="mx-auto grid max-w-7xl grid-cols-12 gap-6 px-6 py-6">
        {/* exam content */}
        <div className="col-span-12 lg:col-span-8">
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
            className="aspect-[4/3] w-full rounded border border-border bg-surface-1"
          >
            <ExamPlaceholder />
          </motion.div>
        </div>

        {/* side rail: webcam + risk + tips */}
        <aside className="col-span-12 flex flex-col gap-4 lg:col-span-4">
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.05, ease: [0.16, 1, 0.3, 1] }}
            className="overflow-hidden rounded border border-border"
          >
            <WebcamFeed className="aspect-video w-full" />
            <div className="flex items-center justify-between border-t border-border bg-surface-2 px-3 py-2">
              <span className="font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
                you · live
              </span>
              <LiveDot variant="online" />
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
            className="card flex items-center gap-5"
          >
            <RiskGauge value={risk} />
            <div className="min-w-0 flex-1">
              <p className="label">Behavioral risk</p>
              <p className="mt-1 text-[13px] text-text-secondary">
                A composite score from gaze, head pose, lip motion and detected
                objects. Calibrated to your baseline.
              </p>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.15, ease: [0.16, 1, 0.3, 1] }}
            className="card-elevated"
          >
            <p className="label">Tips</p>
            <ul className="mt-3 space-y-1.5 text-[12px] text-text-secondary">
              <li>· Keep your face centered.</li>
              <li>· Brief glances away are fine.</li>
              <li>· Do not leave the frame.</li>
            </ul>
          </motion.div>
        </aside>
      </section>

      <AlertStack alerts={alerts} />
    </PageShell>
  )
}

function Stat({ label, value, mono = false }) {
  return (
    <div className="flex items-baseline gap-2">
      <span className="font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
        {label}
      </span>
      <span
        className={`text-[13px] text-text-primary ${mono ? 'font-mono tracking-wider' : ''}`}
      >
        {value}
      </span>
    </div>
  )
}

function ExamPlaceholder() {
  return (
    <div className="flex h-full flex-col p-8">
      <p className="font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
        exam content · placeholder
      </p>
      <h2 className="mt-3 text-2xl font-medium tracking-tightest text-text-primary">
        Question 1 of 12
      </h2>
      <p className="mt-4 max-w-prose text-[14px] leading-relaxed text-text-secondary">
        Real exam questions would render here in production. This panel is
        intentionally minimal — the focus of ProctorVision is the proctoring
        layer, not exam delivery.
      </p>
      <div className="mt-8 grid gap-2">
        {['Computer vision', 'Behavioral analytics', 'Privacy by default', 'All of the above'].map(
          (opt, i) => (
            <label
              key={i}
              className="flex cursor-pointer items-center gap-3 rounded border border-border bg-surface-2 px-4 py-3 text-[13px] text-text-secondary transition-colors hover:border-border-strong hover:text-text-primary"
            >
              <input type="radio" name="q1" className="accent-accent" />
              {opt}
            </label>
          )
        )}
      </div>
      <div className="mt-auto flex items-center justify-between pt-6 font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
        <span>question 1 / 12</span>
        <span>autosave on</span>
      </div>
    </div>
  )
}
