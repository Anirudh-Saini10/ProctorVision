import { useMemo } from 'react'
import { useParams, Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Download, ArrowLeft } from 'lucide-react'
import PageShell from '../components/PageShell.jsx'
import RiskGauge from '../components/RiskGauge.jsx'
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

export default function Report() {
  const { id } = useParams()
  const reportId = id ?? 'PREVIEW'
  const session = useMemo(() => getSession(reportId), [reportId])
  const events = useMemo(() => getEvents(reportId, 24), [reportId])

  const candidate = session?.candidate ?? 'Demo Candidate'
  const finalRisk = session?.risk ?? 22
  const duration = session?.durationMin ?? 47
  const strictness = session?.strictness ?? 'Moderate'

  const counts = events.reduce(
    (acc, e) => {
      acc[e.severity] = (acc[e.severity] ?? 0) + 1
      return acc
    },
    { low: 0, medium: 0, high: 0 }
  )

  const verdict =
    finalRisk >= 70
      ? { label: 'High concern', tone: 'text-risk-high' }
      : finalRisk >= 35
      ? { label: 'Review recommended', tone: 'text-risk-medium' }
      : { label: 'Within expected range', tone: 'text-risk-low' }

  return (
    <PageShell>
      <section className="mx-auto max-w-6xl px-6 pt-10 pb-16">
        <Link
          to="/proctor"
          className="inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-eyebrow text-text-muted hover:text-text-secondary"
        >
          <ArrowLeft size={11} strokeWidth={2} /> back
        </Link>

        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          className="mt-4 flex flex-wrap items-end justify-between gap-4"
        >
          <div>
            <p className="font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
              session report · {reportId}
            </p>
            <h1 className="mt-2 text-3xl font-medium tracking-tightest text-text-primary">
              {candidate}
            </h1>
            <p className="mt-1 text-[13px] text-text-secondary">
              {duration} minutes · strictness {strictness} · {events.length} events logged
            </p>
          </div>
          <button type="button" className="btn-primary">
            <Download size={14} strokeWidth={2} /> Download PDF
          </button>
        </motion.div>

        {/* summary grid */}
        <div className="mt-8 grid gap-6 lg:grid-cols-12">
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.05, ease: [0.16, 1, 0.3, 1] }}
            className="card flex items-center gap-6 lg:col-span-5"
          >
            <RiskGauge value={finalRisk} size={150} label="Final" />
            <div className="min-w-0 flex-1">
              <p className="label">Verdict</p>
              <p className={`mt-1 text-[16px] ${verdict.tone}`}>{verdict.label}</p>
              <p className="mt-2 text-[12px] text-text-muted">
                Composite of gaze, head pose, lip motion and detected objects,
                weighted by configured strictness.
              </p>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
            className="card grid grid-cols-3 gap-4 lg:col-span-7"
          >
            <SevStat label="low" count={counts.low} tone="low" />
            <SevStat label="medium" count={counts.medium} tone="medium" />
            <SevStat label="high" count={counts.high} tone="high" />
          </motion.div>
        </div>

        {/* timeline strip */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.15, ease: [0.16, 1, 0.3, 1] }}
          className="mt-6 rounded border border-border bg-surface-1 p-5"
        >
          <div className="flex items-center justify-between">
            <p className="label">Risk over session</p>
            <span className="font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
              {duration}m window
            </span>
          </div>
          <RiskCurve events={events} duration={duration * 60} />
        </motion.div>

        {/* event table */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
          className="mt-6 overflow-hidden rounded border border-border bg-surface-1"
        >
          <div className="grid grid-cols-12 gap-4 border-b border-border bg-surface-2 px-4 py-2.5 font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
            <span className="col-span-2">at</span>
            <span className="col-span-2">severity</span>
            <span className="col-span-3">kind</span>
            <span className="col-span-5">detail</span>
          </div>
          <ul className="divide-y divide-border">
            {events.map((e) => (
              <li
                key={e.id}
                className="grid grid-cols-12 items-center gap-4 px-4 py-2.5 text-[13px]"
              >
                <span className="col-span-2 font-mono text-text-secondary">
                  +{Math.floor(e.atSec / 60)}:{String(e.atSec % 60).padStart(2, '0')}
                </span>
                <span
                  className={`col-span-2 font-mono text-[11px] uppercase tracking-eyebrow ${SEV_TONE[e.severity]}`}
                >
                  {e.severity}
                </span>
                <span className="col-span-3 text-text-primary">{e.kind}</span>
                <span className="col-span-5 font-mono text-[11px] text-text-muted">
                  {e.detail}
                </span>
              </li>
            ))}
          </ul>
        </motion.div>

        <p className="mt-8 font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
          generated by proctorvision · velour
        </p>
      </section>
    </PageShell>
  )
}

function SevStat({ label, count, tone }) {
  return (
    <div>
      <div className="flex items-center gap-2">
        <span className={`h-1.5 w-1.5 rounded-full ${SEV_BG[tone]}`} />
        <span className="label">{label}</span>
      </div>
      <p className={`mt-2 font-mono text-2xl tabular-nums ${SEV_TONE[tone]}`}>{count}</p>
    </div>
  )
}

function RiskCurve({ events, duration }) {
  // build a sparse risk-over-time curve from events: each event bumps risk, decays linearly
  const samples = 80
  const points = []
  let r = 5
  for (let i = 0; i < samples; i++) {
    const tSec = (i / samples) * duration
    const newEvts = events.filter(
      (e) => e.atSec <= tSec && e.atSec > tSec - duration / samples
    )
    for (const e of newEvts) {
      r += e.severity === 'high' ? 22 : e.severity === 'medium' ? 10 : 4
    }
    r = Math.max(2, r * 0.93)
    r = Math.min(100, r)
    points.push([(i / (samples - 1)) * 100, 100 - r])
  }
  const path = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p[0].toFixed(2)},${p[1].toFixed(2)}`).join(' ')
  return (
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="mt-4 h-32 w-full">
      <defs>
        <linearGradient id="riskfill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.30" />
          <stop offset="100%" stopColor="#3b82f6" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={`${path} L 100,100 L 0,100 Z`} fill="url(#riskfill)" />
      <path
        d={path}
        fill="none"
        stroke="#3b82f6"
        strokeWidth="1"
        strokeLinejoin="round"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  )
}
