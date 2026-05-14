import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Square, Mic, MicOff } from 'lucide-react'
import PageShell from '../components/PageShell.jsx'
import WebcamFeed from '../components/WebcamFeed.jsx'
import RiskGauge from '../components/RiskGauge.jsx'
import AlertStack from '../components/AlertStack.jsx'
import LiveDot from '../components/LiveDot.jsx'
import { useSession } from '../state/SessionContext.jsx'
import { useWS } from '../state/WebSocketContext.jsx'
import useFrameStreamer from '../hooks/useFrameStreamer.js'
import useTabMonitor from '../hooks/useTabMonitor.js'
import useAudioActivity from '../hooks/useAudioActivity.js'
import { attemptsApi } from '../lib/api.js'

/**
 * Maps backend violation types to display strings + severity tier for AlertStack.
 */
const VIOLATION_META = {
  gaze_off_screen: { title: 'Gaze drift', severity: 'medium' },
  prolonged_gaze_aversion: { title: 'Prolonged gaze aversion', severity: 'high' },
  head_turn: { title: 'Head turn', severity: 'medium' },
  head_down: { title: 'Looking down', severity: 'medium' },
  lip_movement: { title: 'Lip movement', severity: 'medium' },
  multiple_faces: { title: 'Multiple faces detected', severity: 'high' },
  no_face: { title: 'No face in frame', severity: 'high' },
  phone_detected: { title: 'Phone detected', severity: 'high' },
  book_detected: { title: 'Book detected', severity: 'medium' },
  laptop_detected: { title: 'Secondary device', severity: 'high' },
  earpiece_detected: { title: 'Possible earpiece', severity: 'medium' },
  tab_switch: { title: 'Tab / focus lost', severity: 'high' },
}

function fmtTimestampMs(ms) {
  const d = new Date(ms)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}`
}

export default function Exam() {
  const navigate = useNavigate()
  const { name, code, strictness, exam, attemptId } = useSession()
  const {
    sessionId,
    riskScore,
    violations,
    sendFrame,
    sendTabSwitch,
    sendAudioActivity,
    endSession,
    lastFrameInfo,
    forceEndedReason,
  } = useWS()

  // When the proctor ends the session, navigate to /student/done.
  // WebSocketContext already dispatched `session_end` for us so the
  // backend will produce a real summary; the Done page reads it from
  // context.
  useEffect(() => {
    if (forceEndedReason) {
      navigate('/student/done', { replace: true })
    }
  }, [forceEndedReason, navigate])

  // NOTE: An earlier version of this file dispatched `endSession()`
  // from a useEffect cleanup as a "safety net" for in-app navigation
  // away from the Exam page. That was a bug: React StrictMode in dev
  // (and any dependency-change re-run of the effect) fires the
  // cleanup spuriously, which ended sessions seconds after the
  // candidate's exam began — they would still be answering Question 1
  // while the proctor dashboard already marked the session ENDED.
  //
  // We rely on these mechanisms instead, in order of preference:
  //   1. The explicit "End Session" button (`onEnd` below).
  //   2. Proctor force-end → `force_end` WS message → handled in
  //      WebSocketContext, surfaces via `forceEndedReason` above.
  //   3. Tab / window close → WebSocket `onclose` fires on the server,
  //      which runs the disconnect cleanup and archives the session.
  //   4. In-app navigation away without ending → backend's 15s
  //      stale-sweep (`_sweep_stale_sessions`) archives it shortly.
  //
  // No unmount-time `endSession()` call. Do NOT re-add one without
  // a StrictMode-safe guard (e.g. a module-level "already ended" set
  // keyed by session_id).

  const camRef = useRef(null)
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

  // stream frames at 5 FPS
  useFrameStreamer({
    getVideo: () => camRef.current?.video ?? null,
    active: !!sessionId,
    fps: 5,
    onFrame: sendFrame,
  })

  // tab/visibility monitor
  useTabMonitor({
    active: !!sessionId,
    onSwitch: sendTabSwitch,
  })

  // Audio-based talking detection is a STRICT-ONLY feature. Moderate
  // and lenient sessions tolerate the candidate explaining a question
  // to themselves out loud. Passing `active: false` keeps the hook a
  // no-op (no mic permission prompt, no AudioContext, no listener).
  const audioEnabled = strictness?.id === 'strict'
  const { status: micStatus, level: micLevel } = useAudioActivity({
    active: !!sessionId && audioEnabled,
    onSpeaking: sendAudioActivity,
  })

  // Ephemeral toast list: each new violation creates a toast that auto-removes
  // after 5s. We track which violation ids have already been toasted so the
  // list growing in WebSocketContext doesn't keep re-creating toasts.
  const [toasts, setToasts] = useState([])
  const seenIdsRef = useRef(new Set())

  useEffect(() => {
    if (!violations.length) return
    const fresh = []
    for (const v of violations) {
      if (seenIdsRef.current.has(v.id)) continue
      seenIdsRef.current.add(v.id)
      const meta = VIOLATION_META[v.violation_type] ?? {
        title: v.violation_type.replace(/_/g, ' '),
        severity: 'medium',
      }
      fresh.push({
        id: v.id,
        severity: meta.severity,
        title: meta.title,
        detail: v.confidence ? `confidence ${v.confidence.toFixed(2)}` : undefined,
        timestamp: fmtTimestampMs(v.timestamp ?? Date.now()),
      })
    }
    if (!fresh.length) return
    setToasts((prev) => [...fresh.slice(-4), ...prev].slice(0, 4))
    // Schedule removal. Intentionally NOT clearing these timers on effect
    // re-run — doing so would cancel pending dismissals every time a new
    // violation arrived, which is exactly why toasts were piling up forever.
    const ttl = 3000
    fresh.forEach((t) => {
      setTimeout(() => {
        setToasts((prev) => prev.filter((x) => x.id !== t.id))
      }, ttl)
    })
  }, [violations])

  const onEnd = async () => {
    await endSession()
    navigate('/student/done', { replace: true })
  }

  const faceLost = lastFrameInfo && !lastFrameInfo.face_detected

  return (
    <PageShell className="!flex-none">
      {/* dense status strip */}
      <div className="border-b border-border bg-surface-1/50 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-6 px-6 py-2.5">
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
            <LiveDot variant={faceLost ? 'warn' : 'online'} label={faceLost ? 'no face' : 'recording'} />
            {audioEnabled && <MicChip status={micStatus} level={micLevel} />}
            <Stat label="elapsed" value={elapsedStr} mono />
            <Stat label="candidate" value={name || '—'} />
            <Stat label="session" value={code} mono />
            <Stat label="strictness" value={strictness.label.toUpperCase()} mono />
            {sessionId && (
              <Stat label="sid" value={sessionId.slice(0, 8)} mono />
            )}
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
        <div className="col-span-12 lg:col-span-8">
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
            className="aspect-[4/3] w-full rounded border border-border bg-surface-1"
          >
            <QuizRunner
              exam={exam}
              attemptId={attemptId}
              sessionId={sessionId}
              onSubmitted={() => {
                /* keep proctoring stream running until they click End */
              }}
            />
          </motion.div>
        </div>

        <aside className="col-span-12 flex flex-col gap-4 lg:col-span-4">
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.05, ease: [0.16, 1, 0.3, 1] }}
            className="overflow-hidden rounded border border-border"
          >
            <WebcamFeed ref={camRef} className="aspect-video w-full" />
            <div className="flex items-center justify-between border-t border-border bg-surface-2 px-3 py-2">
              <span className="font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
                you · live
              </span>
              <LiveDot variant={faceLost ? 'warn' : 'online'} />
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
            className="card flex items-center gap-5"
          >
            <RiskGauge value={riskScore} />
            <div className="min-w-0 flex-1">
              <p className="label">Behavioral risk</p>
              <p className="mt-1 text-[13px] text-text-secondary">
                Composite of gaze, head pose, lip motion and detected objects,
                weighted to your baseline.
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
              <li>· Do not leave the frame or switch tabs.</li>
            </ul>
          </motion.div>
        </aside>
      </section>

      <AlertStack alerts={toasts} />
    </PageShell>
  )
}

function MicChip({ status, level }) {
  const denied = status === 'denied' || status === 'error'
  const active = status === 'active'
  const speaking = active && level > 0.025
  const Icon = denied ? MicOff : Mic
  const color = denied
    ? 'text-risk-high'
    : speaking
    ? 'text-risk-med'
    : active
    ? 'text-risk-low'
    : 'text-text-muted'
  const label = denied
    ? 'mic blocked'
    : status === 'requesting'
    ? 'mic …'
    : active
    ? speaking
      ? 'speaking'
      : 'mic on'
    : 'mic off'
  return (
    <div className={`flex items-center gap-1.5 ${color}`} title={`audio status: ${status}`}>
      <Icon size={12} strokeWidth={2.25} />
      <span className="font-mono text-[10px] uppercase tracking-eyebrow">{label}</span>
    </div>
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

/**
 * Real quiz runner. Drives off the candidate-facing exam payload
 * (questions, no correct answers). Submits to /api/attempts/{id}/submit
 * and links the proctoring session id so the backend can stitch the
 * integrity summary onto the same row.
 *
 * Falls back to a friendly empty state when ``exam`` is null — that
 * happens for the legacy demo flow (login via /login, not /join),
 * where no exam was loaded. In that mode the page is still useful as
 * a proctoring demo without a quiz behind it.
 */
function QuizRunner({ exam, attemptId, sessionId, onSubmitted }) {
  const questions = exam?.questions || []
  const total = questions.length
  const [idx, setIdx] = useState(0)
  const [answers, setAnswers] = useState({}) // {question_id: {selected_index?, text?}}
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState(null) // {auto_score, max_auto_score}
  const [error, setError] = useState('')

  if (!exam || total === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
        <p className="font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
          proctoring demo mode
        </p>
        <p className="max-w-md text-[13px] text-text-secondary">
          No exam attached to this session. The proctoring pipeline is
          fully live — your webcam, gaze, head pose and object detectors
          are being streamed and analyzed. Use the right column to watch
          the risk score and end the session when you're done.
        </p>
      </div>
    )
  }

  if (result) {
    const pct = result.max_auto_score
      ? Math.round((result.auto_score / result.max_auto_score) * 100)
      : null
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
        <p className="font-mono text-[10px] uppercase tracking-eyebrow text-risk-low">
          answers submitted
        </p>
        <h2 className="text-2xl font-medium tracking-tightest text-text-primary">
          {result.max_auto_score > 0 ? (
            <>
              Auto-graded: {result.auto_score} / {result.max_auto_score}
              {pct !== null && <span className="ml-2 text-text-muted">({pct}%)</span>}
            </>
          ) : (
            <>All {total} answers saved.</>
          )}
        </h2>
        <p className="max-w-md text-[13px] text-text-secondary">
          Short-answer questions (if any) will be reviewed by your proctor.
          Press <span className="font-mono text-text-primary">End session</span> at the
          top of the page to finalize your integrity report.
        </p>
      </div>
    )
  }

  const current = questions[idx]
  const isLast = idx === total - 1
  const currentAnswer = answers[current.id]
  const canAdvance =
    current.kind === 'mcq'
      ? currentAnswer?.selected_index !== undefined
      : (currentAnswer?.text || '').trim().length > 0

  const setMcq = (selected_index) =>
    setAnswers((a) => ({ ...a, [current.id]: { selected_index } }))
  const setText = (text) =>
    setAnswers((a) => ({ ...a, [current.id]: { text } }))

  const next = async () => {
    if (!isLast) {
      setIdx((i) => i + 1)
      return
    }
    // Submit
    setSubmitting(true)
    setError('')
    try {
      const payload = {
        proctor_session_id: sessionId || null,
        answers: questions.map((q) => {
          const a = answers[q.id] || {}
          return {
            question_id: q.id,
            selected_index: a.selected_index ?? null,
            text: a.text ?? null,
          }
        }),
      }
      const res = await attemptsApi.submit(attemptId, payload)
      setResult(res)
      onSubmitted?.(res)
    } catch (e) {
      setError(e.message || 'Failed to submit. Try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex h-full flex-col p-8">
      <p className="font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
        {exam.title}
      </p>
      <h2 className="mt-3 text-2xl font-medium tracking-tightest text-text-primary">
        Question {idx + 1} of {total}
      </h2>
      <p className="mt-4 max-w-prose text-[14px] leading-relaxed text-text-secondary">
        {current.prompt}
      </p>

      <div className="mt-6 grid gap-2">
        {current.kind === 'mcq' &&
          (current.options || []).map((opt, i) => {
            const selected = currentAnswer?.selected_index === i
            return (
              <label
                key={i}
                className={`flex cursor-pointer items-center gap-3 rounded border px-4 py-3 text-[13px] transition-colors ${
                  selected
                    ? 'border-accent bg-surface-3 text-text-primary'
                    : 'border-border bg-surface-2 text-text-secondary hover:border-border-strong hover:text-text-primary'
                }`}
              >
                <input
                  type="radio"
                  name={`q-${current.id}`}
                  className="accent-accent"
                  checked={selected}
                  onChange={() => setMcq(i)}
                />
                {opt}
              </label>
            )
          })}
        {current.kind === 'short' && (
          <textarea
            className="input w-full"
            rows={5}
            placeholder="Type your answer…"
            value={currentAnswer?.text || ''}
            onChange={(e) => setText(e.target.value)}
          />
        )}
      </div>

      {error && (
        <p className="mt-3 text-[12px] text-risk-high">{error}</p>
      )}

      <div className="mt-auto flex items-center justify-between gap-3 pt-6">
        <button
          type="button"
          onClick={() => setIdx((i) => Math.max(0, i - 1))}
          disabled={idx === 0}
          className="rounded border border-border bg-surface-2 px-4 py-2 text-[13px] text-text-secondary transition-colors hover:border-border-strong hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-40"
        >
          Previous
        </button>
        <span className="font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
          {Object.keys(answers).length} / {total} answered
        </span>
        <button
          type="button"
          onClick={next}
          disabled={!canAdvance || submitting}
          className="rounded border border-accent bg-accent px-4 py-2 text-[13px] font-medium text-bg-base transition-colors hover:bg-accent/90 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {submitting ? 'Submitting…' : isLast ? 'Submit answers' : 'Next question'}
        </button>
      </div>
    </div>
  )
}
