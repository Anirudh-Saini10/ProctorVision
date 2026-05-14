import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import PageShell from '../components/PageShell.jsx'
import WebcamFeed from '../components/WebcamFeed.jsx'
import { useSession } from '../state/SessionContext.jsx'
import { useWS } from '../state/WebSocketContext.jsx'
import useFrameStreamer from '../hooks/useFrameStreamer.js'

/**
 * Real-backend calibration:
 *  1. Open WS, send `session_start`.
 *  2. Stream frames at 5 FPS while the visual reticle dance plays.
 *  3. Backend runs its 10s calibration internally and emits
 *     `calibration_progress` updates and finally `calibration_complete`.
 *  4. On `calibration_complete`, navigate to /student/exam.
 */
const STEPS = [
  { id: 'p1', label: 'Look at the dot · center', x: 50, y: 50 },
  { id: 'p2', label: 'Look at the dot · top-left', x: 10, y: 12 },
  { id: 'p3', label: 'Look at the dot · top-right', x: 90, y: 12 },
  { id: 'p4', label: 'Look at the dot · bottom-right', x: 90, y: 88 },
  { id: 'p5', label: 'Look at the dot · bottom-left', x: 10, y: 88 },
  { id: 'neutral', label: 'Hold neutral head pose · look forward', x: 50, y: 50, hold: true },
]

export default function Calibrate() {
  const navigate = useNavigate()
  const { name, code, strictness, attemptId, setCalibrated } = useSession()
  const {
    status,
    sessionId,
    calibration,
    calibrationComplete,
    startSession,
    sendFrame,
    reset,
  } = useWS()

  const camRef = useRef(null)
  const [stepIdx, setStepIdx] = useState(0)
  const [streamActive, setStreamActive] = useState(false)

  // Kick off WS + session_start as soon as page mounts.
  // NOTE: depend on strictness.id (stable string), not the strictness object,
  // because `deriveStrictness()` returns a new object every render and would
  // otherwise infinite-loop this effect.
  const strictnessId = strictness.id
  useEffect(() => {
    startSession({
      candidate_name: name,
      code,
      strictness: strictnessId,
      attempt_id: attemptId,
    })
  }, [startSession, name, code, strictnessId, attemptId])

  // Once session is started, begin streaming frames
  useEffect(() => {
    if (sessionId) setStreamActive(true)
  }, [sessionId])

  // Visual reticle progression — 5 anchor points evenly distributed across the
  // 10s calibration window, then the neutral hold for the remainder.
  useEffect(() => {
    if (!sessionId) return
    const totalMs = 10_000
    const stepMs = (totalMs - 3000) / 5 // last 3s reserved for neutral hold
    let cancelled = false
    const advance = (i) => {
      if (cancelled) return
      setStepIdx(i)
      if (i < STEPS.length - 1) {
        setTimeout(() => advance(i + 1), i === STEPS.length - 2 ? stepMs : stepMs)
      }
    }
    advance(0)
    return () => {
      cancelled = true
    }
  }, [sessionId])

  // Stream frames while calibration is active
  useFrameStreamer({
    getVideo: () => camRef.current?.video ?? null,
    active: streamActive && !calibrationComplete,
    fps: 5,
    onFrame: sendFrame,
  })

  // When the backend reports calibration complete, we DON'T auto-redirect
  // anymore — instead we show an explicit "Continue / Recalibrate" gate so
  // a student who didn't follow the dots properly can redo their baseline.
  useEffect(() => {
    if (calibrationComplete) setCalibrated(true)
  }, [calibrationComplete, setCalibrated])

  const handleContinue = () => navigate('/student/exam', { replace: true })

  const handleRecalibrate = () => {
    // startSession() internally calls reset() which clears sessionId,
    // calibration, calibrationComplete etc. The sessionId→streamActive
    // effect will re-arm the frame streamer as soon as the new session
    // is registered, and the sessionId-keyed reticle effect will restart
    // the dot dance automatically.
    setCalibrated(false)
    setStepIdx(0)
    setStreamActive(false)
    startSession({
      candidate_name: name,
      code,
      strictness: strictnessId,
      attempt_id: attemptId,
    })
  }

  const step = STEPS[Math.min(stepIdx, STEPS.length - 1)]
  const pct = calibration?.progress != null ? calibration.progress : 0
  const remaining = calibration?.remaining
  const wsLabel =
    status === 'open'
      ? sessionId
        ? 'session active'
        : 'connecting session'
      : status === 'connecting'
      ? 'opening socket'
      : status === 'error'
      ? 'connection error'
      : 'idle'

  return (
    <PageShell>
      <section className="mx-auto flex max-w-6xl flex-col items-center px-6 py-6">
        <p className="font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
          calibration · {wsLabel}
        </p>
        <h1 className="mt-2 text-2xl font-medium tracking-tightest text-text-primary">
          {calibrationComplete ? 'Calibration complete.' : step.label}
        </h1>
        {!calibrationComplete && (
          <p className="mt-1 text-[12px] text-text-muted">
            Dot sequence: <span className="font-mono text-text-secondary">
              center → top-left → top-right → bottom-right → bottom-left → hold neutral
            </span>
          </p>
        )}

        {/* stage — capped at viewport height so instructions stay visible.
           Webcam preview is rendered OUTSIDE the stage so it doesn't obscure
           the bottom-right calibration dot. */}
        <div className="relative mt-4 w-full overflow-hidden rounded border border-border bg-surface-1" style={{ height: 'min(54vh, 480px)' }}>
          <div
            aria-hidden
            className="absolute inset-0 opacity-30"
            style={{
              backgroundImage:
                'linear-gradient(rgba(255,255,255,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.04) 1px, transparent 1px)',
              backgroundSize: '40px 40px',
            }}
          />

          <AnimatePresence>
            {!calibrationComplete && (
              <motion.div
                key={step.id}
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.6 }}
                transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
                className="absolute"
                style={{
                  left: `${step.x}%`,
                  top: `${step.y}%`,
                  transform: 'translate(-50%, -50%)',
                }}
              >
                <Reticle hold={!!step.hold} />
              </motion.div>
            )}
          </AnimatePresence>

          <AnimatePresence>
            {calibrationComplete && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.4 }}
                className="absolute inset-0 grid place-items-center bg-bg-base/80 backdrop-blur-sm"
              >
                <div className="flex max-w-md flex-col items-center gap-4 p-6 text-center">
                  <div className="font-mono text-[11px] uppercase tracking-eyebrow text-risk-low">
                    baseline captured
                  </div>
                  <h2 className="text-xl font-medium tracking-tightest text-text-primary">
                    Did the calibration go well?
                  </h2>
                  <p className="text-[13px] leading-relaxed text-text-secondary">
                    If your head moved a lot, you missed a dot, or you weren't
                    paying attention — <span className="font-semibold text-text-primary">recalibrate now</span>.
                    A bad baseline will incorrectly flag your natural gaze
                    throughout the entire exam.
                  </p>
                  <div className="mt-2 flex gap-3">
                    <button
                      type="button"
                      onClick={handleRecalibrate}
                      className="rounded border border-border bg-surface-2 px-4 py-2 text-[13px] text-text-secondary transition-colors hover:border-border-strong hover:text-text-primary"
                    >
                      Recalibrate
                    </button>
                    <button
                      type="button"
                      onClick={handleContinue}
                      className="rounded border border-accent bg-accent px-4 py-2 text-[13px] font-medium text-white transition-colors hover:bg-accent-hover"
                    >
                      Continue to exam
                    </button>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* preview strip below the stage — never overlaps a calibration dot */}
        <div className="mt-3 flex w-full items-center gap-3">
          <div className="h-16 w-24 flex-shrink-0 overflow-hidden rounded border border-border-strong">
            <WebcamFeed ref={camRef} />
          </div>
          <p className="text-[12px] text-text-muted">
            Keep your face centered in the preview. Move only your eyes between dots
            — your head should stay still.
          </p>
        </div>

        <div className="mt-4 w-full">
          <div className="h-px w-full bg-border">
            <motion.div
              animate={{ width: `${pct * 100}%` }}
              transition={{ duration: 0.2, ease: 'linear' }}
              className="h-px bg-accent"
            />
          </div>
          <div className="mt-2 flex justify-between font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
            <span>baseline capture</span>
            <span>
              {Math.round(pct * 100)}%
              {remaining != null && ` · ${remaining.toFixed(1)}s left`}
            </span>
          </div>
        </div>

      </section>
    </PageShell>
  )
}

function Reticle({ hold }) {
  return (
    <div className="relative">
      <div className="h-3 w-3 rounded-full bg-accent" />
      <motion.div
        animate={{ scale: [1, 2.2, 1], opacity: [0.6, 0, 0.6] }}
        transition={{ duration: hold ? 1.8 : 1.2, repeat: Infinity, ease: 'easeOut' }}
        className="absolute inset-0 rounded-full bg-accent"
      />
      {hold && (
        <motion.div
          initial={{ rotate: 0 }}
          animate={{ rotate: 360 }}
          transition={{ duration: 3, ease: 'linear' }}
          className="absolute -inset-4 rounded-full border border-accent/40 border-t-accent"
        />
      )}
    </div>
  )
}
