import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { ArrowLeft, Flag, Pause, StopCircle, X } from 'lucide-react'
import PageShell from '../components/PageShell.jsx'
import RiskGauge from '../components/RiskGauge.jsx'
import LiveDot from '../components/LiveDot.jsx'
import useProctorSocket from '../hooks/useProctorSocket.js'
import { getSession as getMockSession, getEvents as getMockEvents } from '../lib/mockSessions.js'

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
  const {
    status,
    activeSessions,
    subscribed,
    latestSnapshot,
    liveRisk,
    events: liveEvents,
    evidenceSnapshots,
    subscribe,
    manualFlag,
    forceEnd,
  } = useProctorSocket()
  const sessionEnded = Boolean(subscribed?.ended)
  // Lightbox state for clicking on an evidence thumbnail.
  const [lightbox, setLightbox] = useState(null)

  // Find the session in the activeSessions list (which now includes
  // both live and ended). `isReal` covers both — we want to subscribe
  // (or replay-subscribe) the backend in either case. `isLive` is just
  // the live subset, used to gate the action buttons.
  const sessionRow = useMemo(
    () => activeSessions.find((s) => s.session_id === id),
    [activeSessions, id]
  )
  const isReal = Boolean(sessionRow)
  const isLive = sessionRow?.status === 'live'
  useEffect(() => {
    if (isReal && status === 'open') subscribe(id)
  }, [isReal, status, id, subscribe])

  // Mock fallback only when the session id isn't known to the backend
  // at all (e.g. someone hits a hardcoded demo URL).
  const mock = useMemo(() => (isReal ? null : getMockSession(id)), [id, isReal])
  const mockEvents = useMemo(
    () => (isReal ? null : getMockEvents(id ?? 'X', 18)),
    [id, isReal]
  )

  const candidate = isReal
    ? subscribed?.candidate ?? sessionRow?.candidate ?? '...'
    : mock?.candidate
  const strictness = isReal
    ? subscribed?.strictness ?? sessionRow?.strictness ?? '—'
    : mock?.strictness
  const durationMin = isReal
    ? Math.round((sessionRow?.duration_sec ?? 0) / 60)
    : mock?.durationMin ?? 0

  const risk = isReal ? liveRisk : mock?.risk ?? 0
  const events = isReal
    ? liveEvents
    : (mockEvents ?? []).map((e) => ({
        id: e.id,
        kind: e.kind,
        severity: e.severity,
        detail: e.detail,
        stamp: `+${Math.floor(e.atSec / 60)}:${String(e.atSec % 60).padStart(2, '0')}`,
      }))

  if (!isReal && !mock) {
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

  return (
    <PageShell>
      <section className="mx-auto max-w-7xl px-6 pt-10 pb-16">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <Link
              to="/proctor"
              className="inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-eyebrow text-text-muted hover:text-text-secondary"
            >
              <ArrowLeft size={11} strokeWidth={2} /> sessions
            </Link>
            <h1 className="mt-2 text-2xl font-medium tracking-tightest text-text-primary">
              {candidate}
              {!isReal && (
                <span className="ml-2 font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
                  demo
                </span>
              )}
            </h1>
            <div className="mt-1 flex items-center gap-3 font-mono text-[11px] text-text-muted">
              <span className="tracking-wider">{id?.slice(0, 12)}</span>
              <span>·</span>
              <span>{durationMin}m elapsed</span>
              <span>·</span>
              <span>strictness {strictness}</span>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="btn-secondary disabled:opacity-40"
              disabled={!isLive || sessionEnded}
              onClick={() => {
                if (!isLive || sessionEnded) return
                const note = window.prompt(
                  'Add a note for this manual flag (optional):',
                  ''
                )
                // null = cancel; '' = OK with empty
                if (note === null) return
                manualFlag(note)
              }}
              title={
                !isLive
                  ? 'Not available for replay sessions'
                  : sessionEnded
                  ? 'Session already ended'
                  : 'Add a manual flag with optional note'
              }
            >
              <Flag size={13} strokeWidth={2} /> Manual flag
            </button>
            <button
              type="button"
              className="btn-secondary disabled:opacity-40"
              disabled
              title="Pause is not implemented in this build"
            >
              <Pause size={13} strokeWidth={2} /> Pause
            </button>
            <button
              type="button"
              disabled={!isLive || sessionEnded}
              onClick={() => {
                if (!isLive || sessionEnded) return
                const ok = window.confirm(
                  `End ${candidate}'s session now? They will be moved to the summary page immediately.`
                )
                if (ok) forceEnd('Ended by proctor')
              }}
              className="inline-flex items-center justify-center gap-2 rounded border border-border bg-surface-3 px-4 py-2 text-[13px] font-medium text-risk-high transition-colors hover:bg-risk-high hover:text-white disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-surface-3 disabled:hover:text-risk-high"
            >
              <StopCircle size={13} strokeWidth={2} /> End session
            </button>
            {sessionEnded && (
              <a
                href={`/api/report/${id}`}
                target="_blank"
                rel="noreferrer"
                className="btn-secondary"
              >
                Open report ↗
              </a>
            )}
          </div>
        </div>

        <div className="mt-8 grid grid-cols-12 gap-6">
          <div className="col-span-12 lg:col-span-8">
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
              className="overflow-hidden rounded border border-border bg-surface-1"
            >
              <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
                <div className="flex items-center gap-3">
                  {sessionEnded ? (
                    <span className="font-mono text-[10px] uppercase tracking-eyebrow text-risk-high">
                      ● session ended
                    </span>
                  ) : isLive ? (
                    <LiveDot variant="online" label="snapshot live" />
                  ) : (
                    <span className="font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
                      replay (mock)
                    </span>
                  )}
                </div>
                <span className="font-mono text-[10px] text-text-muted">
                  ~1 fps · jpeg · server-relayed
                </span>
              </div>
              <div className="relative aspect-video">
                {isReal ? (
                  <SnapshotLive snapshot={latestSnapshot} candidate={candidate} />
                ) : (
                  <SnapshotMock candidate={candidate} />
                )}
              </div>
              <Timeline
                events={
                  isReal
                    ? liveEvents.map((e, i) => ({
                        id: e.id,
                        atSec: i * 13 + 5,
                        severity: e.severity,
                        kind: e.kind,
                      }))
                    : (mockEvents ?? [])
                }
                duration={Math.max(60, durationMin * 60)}
              />
            </motion.div>

            {isReal && (
              <EvidenceGallery
                snapshots={evidenceSnapshots}
                onOpen={(s) => setLightbox(s)}
              />
            )}
          </div>

          <aside className="col-span-12 flex flex-col gap-4 lg:col-span-4">
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.05, ease: [0.16, 1, 0.3, 1] }}
              className="card flex items-center gap-5"
            >
              <RiskGauge
                value={Math.round(risk)}
                label={sessionEnded ? 'Peak risk' : 'Live risk'}
              />
              <div>
                <p className="label">
                  {sessionEnded ? 'Final verdict' : 'Verdict'}
                </p>
                <p className="mt-1 text-[13px] text-text-secondary">
                  {risk >= 70
                    ? sessionEnded
                      ? 'High concern. Recommend review before passing.'
                      : 'High concern. Consider intervention.'
                    : risk >= 35
                    ? sessionEnded
                      ? 'Moderate signal. Review flagged events.'
                      : 'Moderate signal. Continue monitoring.'
                    : sessionEnded
                    ? 'Clean session. No significant signals.'
                    : 'Within expected range.'}
                </p>
                {sessionEnded && subscribed?.summary && (
                  <p className="mt-1 font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
                    {subscribed.summary.total_violations ?? events.length} events ·{' '}
                    integrity {subscribed.summary.integrity_score ?? '—'}/100 ·{' '}
                    {subscribed.summary.duration_formatted ?? '—'}
                  </p>
                )}
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
                  {events.length} events
                </span>
              </div>
              <ul className="max-h-[420px] divide-y divide-border overflow-y-auto">
                <AnimatePresence initial={false}>
                  {events.map((e) => (
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
                        className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${SEV_BG[e.severity] ?? SEV_BG.medium}`}
                      />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-[12px] text-text-primary">
                            {e.kind}
                          </span>
                          <span className="font-mono text-[10px] text-text-muted">
                            {e.stamp}
                          </span>
                        </div>
                        {e.detail && (
                          <p
                            className={`mt-0.5 font-mono text-[10px] uppercase tracking-eyebrow ${SEV_TONE[e.severity] ?? SEV_TONE.medium}`}
                          >
                            {e.severity} · {e.detail}
                          </p>
                        )}
                      </div>
                    </motion.li>
                  ))}
                </AnimatePresence>
                {events.length === 0 && (
                  <li className="px-4 py-10 text-center font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
                    awaiting events
                  </li>
                )}
              </ul>
            </motion.div>
          </aside>
        </div>
      </section>

      <AnimatePresence>
        {lightbox && (
          <EvidenceLightbox
            snapshot={lightbox}
            onClose={() => setLightbox(null)}
          />
        )}
      </AnimatePresence>
    </PageShell>
  )
}

function EvidenceGallery({ snapshots, onOpen }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.15, ease: [0.16, 1, 0.3, 1] }}
      className="mt-6 overflow-hidden rounded border border-border bg-surface-1"
    >
      <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
        <span className="font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
          evidence wall · violation snapshots
        </span>
        <span className="font-mono text-[10px] text-text-muted">
          {snapshots.length} {snapshots.length === 1 ? 'frame' : 'frames'}
        </span>
      </div>
      {snapshots.length === 0 ? (
        <div className="px-4 py-10 text-center font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
          no violation evidence yet
        </div>
      ) : (
        <ul className="grid grid-cols-2 gap-2 p-3 sm:grid-cols-3 md:grid-cols-4">
          {snapshots.map((s) => (
            <li key={s.id}>
              <button
                type="button"
                onClick={() => onOpen(s)}
                className="group relative block w-full overflow-hidden rounded border border-border bg-surface-2 transition-colors hover:border-border-strong"
                title={`${s.violation_type ?? 'violation'} — click to enlarge`}
              >
                <div className="aspect-video">
                  <img
                    src={`data:image/jpeg;base64,${s.data}`}
                    alt={`evidence for ${s.violation_type}`}
                    className="h-full w-full -scale-x-100 object-cover"
                  />
                </div>
                <div className="absolute inset-x-0 bottom-0 flex items-center justify-between gap-2 bg-gradient-to-t from-black/80 to-transparent px-2 py-1.5">
                  <span className="truncate font-mono text-[10px] uppercase tracking-eyebrow text-text-primary">
                    {s.violation_type ?? 'violation'}
                  </span>
                  {typeof s.risk === 'number' && (
                    <span className="font-mono text-[10px] text-risk-medium">
                      risk {Math.round(s.risk)}
                    </span>
                  )}
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </motion.div>
  )
}

function EvidenceLightbox({ snapshot, onClose }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.18 }}
      onClick={onClose}
      className="fixed inset-0 z-50 grid place-items-center bg-black/85 p-6"
    >
      <motion.div
        initial={{ scale: 0.96, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.98, opacity: 0 }}
        transition={{ duration: 0.18 }}
        onClick={(e) => e.stopPropagation()}
        className="relative max-h-[90vh] w-full max-w-4xl overflow-hidden rounded border border-border bg-surface-1"
      >
        <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
          <div className="flex items-center gap-3 font-mono text-[11px] text-text-secondary">
            <span className="uppercase tracking-eyebrow text-text-muted">
              evidence
            </span>
            <span>{snapshot.violation_type ?? 'violation'}</span>
            {typeof snapshot.risk === 'number' && (
              <span className="text-risk-medium">
                · risk {Math.round(snapshot.risk)}
              </span>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-text-muted hover:bg-surface-3 hover:text-text-primary"
            aria-label="Close"
          >
            <X size={16} strokeWidth={2} />
          </button>
        </div>
        <img
          src={`data:image/jpeg;base64,${snapshot.data}`}
          alt={`evidence for ${snapshot.violation_type}`}
          className="max-h-[80vh] w-full -scale-x-100 object-contain"
        />
      </motion.div>
    </motion.div>
  )
}

function SnapshotLive({ snapshot, candidate }) {
  if (!snapshot) {
    return (
      <div className="absolute inset-0 grid place-items-center font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
        awaiting first frame…
      </div>
    )
  }
  return (
    <div className="absolute inset-0 overflow-hidden">
      <img
        src={`data:image/jpeg;base64,${snapshot.data}`}
        alt={`${candidate} live snapshot`}
        className="h-full w-full -scale-x-100 object-cover"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-15 mix-blend-overlay"
        style={{
          backgroundImage:
            'repeating-linear-gradient(0deg, rgba(255,255,255,0.06) 0 1px, transparent 1px 3px)',
        }}
      />
      <div className="absolute bottom-3 left-3 font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
        frame {String(snapshot.frame).padStart(4, '0')}
        {!snapshot.face_detected && (
          <span className="ml-2 text-risk-medium">· no face</span>
        )}
      </div>
    </div>
  )
}

function SnapshotMock({ candidate = '?' }) {
  const seed = candidate.charCodeAt(0)
  const hueA = (seed * 13) % 360
  const hueB = (seed * 29) % 360
  return (
    <div className="absolute inset-0 grid place-items-center overflow-hidden">
      <div
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
          mock snapshot · no live session
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
              <div className={`h-2 w-2 rotate-45 ${SEV_BG[e.severity] ?? SEV_BG.medium}`} />
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
