import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import PageShell from '../components/PageShell.jsx'
import WebcamFeed from '../components/WebcamFeed.jsx'
import { useSession } from '../state/SessionContext.jsx'

/**
 * Calibration ritual:
 * 1. Look at five anchor points (center, TL, TR, BR, BL) — animated reticle moves.
 * 2. Hold neutral head pose for 3s.
 * 3. Done.
 */
const STEPS = [
  { id: 'p1', label: 'Look at the dot · center', x: 50, y: 50 },
  { id: 'p2', label: 'Look at the dot · top-left', x: 10, y: 12 },
  { id: 'p3', label: 'Look at the dot · top-right', x: 90, y: 12 },
  { id: 'p4', label: 'Look at the dot · bottom-right', x: 90, y: 88 },
  { id: 'p5', label: 'Look at the dot · bottom-left', x: 10, y: 88 },
  { id: 'neutral', label: 'Hold neutral head pose · look forward', x: 50, y: 50, hold: true },
]

const STEP_MS = 1800
const HOLD_MS = 3000

export default function Calibrate() {
  const navigate = useNavigate()
  const { setCalibrated } = useSession()
  const [stepIdx, setStepIdx] = useState(0)
  const [elapsed, setElapsed] = useState(0)
  const startedAt = useRef(performance.now())

  const step = STEPS[stepIdx]
  const duration = step?.hold ? HOLD_MS : STEP_MS

  // advance steps
  useEffect(() => {
    const id = setInterval(() => {
      setStepIdx((i) => Math.min(i + 1, STEPS.length))
    }, duration)
    return () => clearInterval(id)
  }, [duration, stepIdx])

  // smooth progress
  useEffect(() => {
    let raf
    const tick = () => {
      const t = performance.now() - startedAt.current
      setElapsed(t)
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [])

  // when finished
  useEffect(() => {
    if (stepIdx >= STEPS.length) {
      setCalibrated(true)
      const t = setTimeout(() => navigate('/student/exam', { replace: true }), 900)
      return () => clearTimeout(t)
    }
  }, [stepIdx, navigate, setCalibrated])

  const total = STEPS.reduce((acc, s) => acc + (s.hold ? HOLD_MS : STEP_MS), 0)
  const pct = Math.min(elapsed / total, 1)
  const done = stepIdx >= STEPS.length

  return (
    <PageShell>
      <section className="mx-auto flex max-w-6xl flex-col items-center px-6 py-12">
        <p className="font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
          calibration · step {Math.min(stepIdx + 1, STEPS.length)} / {STEPS.length}
        </p>
        <h1 className="mt-3 text-2xl font-medium tracking-tightest text-text-primary">
          {done ? 'Calibration complete.' : step.label}
        </h1>

        {/* stage */}
        <div className="relative mt-8 aspect-[16/9] w-full overflow-hidden rounded border border-border bg-surface-1">
          {/* webcam pinned bottom-right, small */}
          <div className="absolute bottom-4 right-4 z-20 h-28 w-40 overflow-hidden rounded border border-border-strong">
            <WebcamFeed />
          </div>

          {/* faint grid */}
          <div
            aria-hidden
            className="absolute inset-0 opacity-30"
            style={{
              backgroundImage:
                'linear-gradient(rgba(255,255,255,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.04) 1px, transparent 1px)',
              backgroundSize: '40px 40px',
            }}
          />

          {/* moving reticle */}
          <AnimatePresence>
            {!done && (
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

          {/* finish flash */}
          <AnimatePresence>
            {done && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.4 }}
                className="absolute inset-0 grid place-items-center"
              >
                <div className="font-mono text-[11px] uppercase tracking-eyebrow text-risk-low">
                  baseline captured · proceeding to session
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* progress bar */}
        <div className="mt-6 w-full">
          <div className="h-px w-full bg-border">
            <motion.div
              animate={{ width: `${pct * 100}%` }}
              transition={{ duration: 0.2, ease: 'linear' }}
              className="h-px bg-accent"
            />
          </div>
          <div className="mt-2 flex justify-between font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
            <span>baseline capture</span>
            <span>{Math.round(pct * 100)}%</span>
          </div>
        </div>

        <p className="mt-8 max-w-md text-center text-[12px] text-text-muted">
          Keep your face centered in the small preview. Move only your eyes between
          dots. We use this to learn what {`"normal"`} looks like for you.
        </p>
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
