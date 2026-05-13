import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { ArrowLeft, Flag, Pause, StopCircle } from 'lucide-react'
import PageShell from '../components/PageShell.jsx'
import RiskGauge from '../components/RiskGauge.jsx'
import LiveDot from '../components/LiveDot.jsx'
import { getSession, getEvents } from '../lib/mockSessions.js'

const SEV_TONE = {
  low: 'text-risk-low',
  medium: 'text-risk-medium',
  high: 'text-risk-high',
}
const SEV_BG = {
  low: 'bg-risk-low',
  medium: 'bg-risk-medium',
  high: 'bg-risk-high',
}

export default function ProctorMonitor() {
  const { id } = useParams()
  const session = useMemo(() => getSession(id), [id])
  const baseEvents = useMemo(() => getEvents(id ?? 'X', 18), [id])
  const [risk, setRisk] = useState(session?.risk ?? 20)
  const [stream, setStream] = useState(baseEvents.slice(0, 6).reverse())
  const [snapshotKey, setSnapshotKey] = useState(0)

  // simulate snapshot refresh + new events for live sessions
  useEffect(() => {
    if (!session || session.status !== 'live') return
    const id1 = setInterval(() => setSnapshotKey((k) => k + 1), 1500)
    const id2 = setInterval(() => {
      setRisk((r) => Math.max(2, Math.min(95, r + (Math.random() - 0.45) * 9)))
    }, 1200)
    const id3 = setInterval(() => {
      const next = baseEvents[Math.floor(Math.random() * baseEvents.length)]
      const ts = new Date()
      const stamp = `${String(ts.getHours()).padStart(2, '0')}:${String(ts.getMinutes()).padStart(2, '0')}:${String(ts.getSeconds()).padStart(2, '0')}`
      setStream((s) => [{ ...next, id: crypto.randomUUID(), stamp }, ...s].slice(0, 30))
    }, 3500)
    return () => {
      clearInterval(id1)
      clearInterval(id2)
      clearInterval(id3)
    }
  }, [session, baseEvents])

  if (!session) {
    return (
      <PageShell>
        <section className="mx-auto max-w-3xl px-6 py-20 text-center">
          <p className="font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
            404 / no session
          </p>
          <h1 className="mt-3 text-2xl text-text-primary">Session not found</h1>
          <Link to="/proctor" className="btn-secondary mt-6 inline-flex">
            <ArrowLeft size={14} strokeWidth={2} /> Back to dashboard
          </Link>
        </section>
      </PageShell>
    )
  }

  const live = session.status === 'live'

  return (
    <PageShell>
      <section className="mx-auto max-w-7xl px-6 pt-10 pb-16">
        {/* header */}
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <Link
              to="/proctor"
              className="inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-eyebrow text-text-muted hover:text-text-secondary"
            >
              <ArrowLeft size={11} strokeWidth={2} /> sessions
            </Link>
            <h1 className="mt-2 text-2xl font-medium tracking-tightest text-text-primary">
              {session.candidate}
            </h1>
            <div className="mt-1 flex items-center gap-3 font-mono text-[11px] text-text-muted">
              <span className="tracking-wider">{session.id}</span>
              <span>·</span>
              <span>{session.durationMin}m elapsed</span>
              <span>·</span>
              <span>strictness {session.strictness}</span>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="btn-secondary">
              <Flag size={13} strokeWidth={2} /> Manual flag
            </button>
            <button type="button" className="btn-secondary">
              <Pause size={13} strokeWidth={2} /> Pause
            </button>
            <button
              type="button"
              className="inline-flex items-center justify-center gap-2 rounded border border-border bg-surface-3 px-4 py-2 text-[13px] font-medium text-risk-high transition-colors hover:bg-risk-high hover:text-white"
            >
              <StopCircle size={13} strokeWidth={2} /> End session
            </button>
          </div>
        </div>

        <div className="mt-8 grid grid-cols-12 gap-6">
          {/* snapshot pane */}
          <div className="col-span-12 lg:col-span-8">
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
              className="overflow-hidden rounded border border-border bg-surface-1"
            >
              <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
                <div className="flex items-center gap-3">
                  {live && <LiveDot variant="online" label="snapshot live" />}
                  {!live && (
                    <span className="font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
                      replay
                    </span>
                  )}
                </div>
                <span className="font-mono text-[10px] text-text-muted">
                  ~1 fps · jpeg · server-relayed
                </span>
              </div>
              <div className="relative aspect-video">
                <SnapshotMock candidate={session.candidate} tick={snapshotKey} />
              </div>
              <Timeline events={baseEvents} duration={session.durationMin * 60} />
            </motion.div>
          </div>

          {/* right rail: gauge + event stream */}
          <aside className="col-span-12 flex flex-col gap-4 lg:col-span-4">
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.05, ease: [0.16, 1, 0.3, 1] }}
              className="card flex items-center gap-5"
            >
              <RiskGauge value={Math.round(risk)} label="Live risk" />
              <div>
                <p className="label">Verdict</p>
                <p className="mt-1 text-[13px] text-text-secondary">
                  {risk >= 70
                    ? 'High concern. Consider intervention.'
                    : risk >= 35
                    ? 'Moderate signal. Continue monitoring.'
                    : 'Within expected range.'}
                </p>
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
              className="overflow-hidden rounded border border-border bg-surface-1"
            >
              <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
                <span className="font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
                  event stream
                </span>
                <span className="font-mono text-[10px] text-text-muted">
                  {stream.length} events
                </span>
              </div>
              <ul className="max-h-[420px] divide-y divide-border overflow-y-auto">
                <AnimatePresence initial={false}>
                  {stream.map((e) => (
                    <motion.li
                      key={e.id}
                      layout
                      initial={{ opacity: 0, x: 12 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0 }}
                      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
                      className="flex items-start gap-3 px-4 py-2.5"
                    >
                      <span
                        className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${SEV_BG[e.severity]}`}
                      />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-[12px] text-text-primary">{e.kind}</span>
                          <span className="font-mono text-[10px] text-text-muted">
                            {e.stamp ?? `+${e.atSec}s`}
                          </span>
                        </div>
                        <p className={`mt-0.5 font-mono text-[10px] uppercase tracking-eyebrow ${SEV_TONE[e.severity]}`}>
                          {e.severity} · {e.detail}
                        </p>
                      </div>
                    </motion.li>
                  ))}
                </AnimatePresence>
              </ul>
            </motion.div>
          </aside>
        </div>
      </section>
    </PageShell>
  )
}

function SnapshotMock({ candidate, tick }) {
  // pseudo-random subtle hue per candidate so each session looks distinct
  const seed = candidate.charCodeAt(0)
  const hueA = (seed * 13) % 360
  const hueB = (seed * 29) % 360
  return (
    <div className="absolute inset-0 grid place-items-center overflow-hidden">
      {/* placeholder "video" — animated gradient + scanlines so it feels live */}
      <motion.div
        key={tick}
        initial={{ opacity: 0.85 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.6 }}
        className="absolute inset-0"
        style={{
          background: `radial-gradient(circle at 50% 40%, hsl(${hueA},20%,18%) 0%, hsl(${hueB},15%,8%) 70%)`,
        }}
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-20 mix-blend-overlay"
        style={{
          backgroundImage:
            'repeating-linear-gradient(0deg, rgba(255,255,255,0.06) 0 1px, transparent 1px 3px)',
        }}
      />
      <div className="relative z-10 flex flex-col items-center gap-3 text-center">
        <div className="grid h-20 w-20 place-items-center rounded-full border border-border-strong bg-surface-3 font-mono text-lg uppercase text-text-secondary">
          {candidate
            .split(' ')
            .map((n) => n[0])
            .join('')
            .slice(0, 2)}
        </div>
        <p className="font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
          snapshot · frame {tick.toString().padStart(4, '0')}
        </p>
      </div>
    </div>
  )
}

function Timeline({ events, duration }) {
  return (
    <div className="border-t border-border px-4 py-4">
      <div className="flex items-center justify-between font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
        <span>timeline</span>
        <span>{Math.round(duration / 60)}m window</span>
      </div>
      <div className="relative mt-3 h-12 rounded bg-surface-2">
        <div className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-border" />
        {events.map((e) => {
          const left = Math.min(98, (e.atSec / duration) * 100)
          return (
            <div
              key={e.id}
              className="group absolute top-1/2 -translate-x-1/2 -translate-y-1/2"
              style={{ left: `${left}%` }}
            >
              <div className={`h-2 w-2 rotate-45 ${SEV_BG[e.severity]}`} />
              <div className="pointer-events-none absolute bottom-full left-1/2 mb-2 hidden -translate-x-1/2 whitespace-nowrap rounded border border-border bg-surface-3 px-2 py-1 font-mono text-[10px] uppercase tracking-eyebrow text-text-primary group-hover:block">
                {e.kind} · {e.severity}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
