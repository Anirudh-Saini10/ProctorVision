import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowRight, AlertTriangle, Target } from 'lucide-react'
import PageShell from '../components/PageShell.jsx'
import EnvironmentCheck from '../components/EnvironmentCheck.jsx'
import RulesList from '../components/RulesList.jsx'
import StrictnessBadge from '../components/StrictnessBadge.jsx'
import { useSession, STRICTNESS } from '../state/SessionContext.jsx'

export default function StudentLobby() {
  const navigate = useNavigate()
  const {
    name,
    code,
    strictness,
    setStrictnessOverride,
    consented,
    setConsented,
  } = useSession()
  const [envReady, setEnvReady] = useState(false)

  const canStart = envReady && consented

  return (
    <PageShell>
      <section className="mx-auto max-w-7xl px-6 pt-12 pb-16">
        {/* identity strip */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          className="flex flex-wrap items-center gap-x-6 gap-y-2"
        >
          <div>
            <p className="label">Candidate</p>
            <p className="mt-1 text-[15px] text-text-primary">{name}</p>
          </div>
          <div>
            <p className="label">Session</p>
            <p className="mt-1 font-mono text-[15px] tracking-wider text-text-primary">
              {code}
            </p>
          </div>
          <div>
            <p className="label">Strictness</p>
            <div className="mt-1">
              <StrictnessBadge strictness={strictness} />
            </div>
          </div>
          <div>
            <p className="label">Override (testing)</p>
            <div className="mt-1 flex gap-1.5">
              {Object.values(STRICTNESS).map((s) => {
                const active = strictness.id === s.id
                return (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => setStrictnessOverride(s.id)}
                    className={`rounded border px-2.5 py-1 font-mono text-[10px] uppercase tracking-eyebrow transition-colors ${
                      active
                        ? 'border-accent bg-accent/10 text-accent'
                        : 'border-border bg-surface-1 text-text-muted hover:border-border-strong hover:text-text-secondary'
                    }`}
                  >
                    {s.label}
                  </button>
                )
              })}
            </div>
          </div>
        </motion.div>

        <div className="mt-10 grid gap-10 lg:grid-cols-12">
          {/* left: rules */}
          <div className="lg:col-span-7">
            <motion.h1
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.05, ease: [0.16, 1, 0.3, 1] }}
              className="text-3xl font-medium tracking-tightest text-text-primary"
            >
              Read this carefully.
            </motion.h1>
            <motion.p
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
              className="mt-2 max-w-xl text-[14px] text-text-secondary"
            >
              The rules below match the strictness profile assigned to your
              session. Violations are logged with timestamps and severity.
            </motion.p>

            {/* CRITICAL: phone / external-device warning */}
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.15, ease: [0.16, 1, 0.3, 1] }}
              className="mt-6 rounded border-l-2 border-risk-high bg-risk-high/5 p-4"
            >
              <div className="flex items-start gap-3">
                <AlertTriangle
                  size={18}
                  strokeWidth={2}
                  className="mt-0.5 flex-shrink-0 text-risk-high"
                />
                <div>
                  <p className="font-mono text-[10px] uppercase tracking-eyebrow text-risk-high">
                    Zero-tolerance violations
                  </p>
                  <p className="mt-2 text-[14px] font-semibold leading-relaxed text-text-primary">
                    NO PHONES OR SECONDARY SCREENS within camera view OR within
                    arm's reach. NO OTHER PEOPLE in the room. NO TAB SWITCHING.
                    NO LEAVING THE FRAME.
                  </p>
                  <p className="mt-2 text-[12.5px] leading-relaxed text-text-secondary">
                    These trigger <span className="font-semibold text-risk-high">CRITICAL</span> violations
                    and may result in <span className="font-semibold text-risk-high">automatic disqualification</span> of
                    your exam — regardless of strictness profile.
                  </p>
                </div>
              </div>
            </motion.div>

            {/* CRITICAL: calibration emphasis */}
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
              className="mt-3 rounded border-l-2 border-accent bg-accent/5 p-4"
            >
              <div className="flex items-start gap-3">
                <Target
                  size={18}
                  strokeWidth={2}
                  className="mt-0.5 flex-shrink-0 text-accent"
                />
                <div>
                  <p className="font-mono text-[10px] uppercase tracking-eyebrow text-accent">
                    Calibration is critical
                  </p>
                  <p className="mt-2 text-[14px] font-semibold leading-relaxed text-text-primary">
                    DO THE 10-SECOND CALIBRATION PROPERLY. Sit straight, keep your
                    head still, and follow each dot with your EYES ONLY.
                  </p>
                  <p className="mt-2 text-[12.5px] leading-relaxed text-text-secondary">
                    A bad calibration produces a skewed baseline and will
                    incorrectly flag your natural gaze as cheating throughout
                    the entire exam. You will be offered a chance to
                    <span className="font-semibold text-text-primary"> recalibrate</span> if
                    the result looks wrong — use it.
                  </p>
                  <div className="mt-3 rounded border border-border bg-bg-base/40 p-3">
                    <p className="font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
                      What to expect — dot sequence
                    </p>
                    <p className="mt-1.5 text-[12.5px] leading-relaxed text-text-secondary">
                      A blue dot will appear in the following order. Move
                      <span className="font-semibold text-text-primary"> only your eyes</span> to
                      track it — keep your head still:
                    </p>
                    <ol className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 font-mono text-[11.5px] text-text-secondary sm:grid-cols-3">
                      <li>1. center</li>
                      <li>2. top-left</li>
                      <li>3. top-right</li>
                      <li>4. bottom-right</li>
                      <li>5. bottom-left</li>
                      <li>6. hold neutral</li>
                    </ol>
                  </div>
                </div>
              </div>
            </motion.div>

            <div className="mt-6">
              <RulesList />
            </div>

            <motion.label
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.45, ease: [0.16, 1, 0.3, 1] }}
              className="mt-8 flex cursor-pointer items-start gap-3 rounded border border-border bg-surface-1 p-4 transition-colors hover:border-border-strong"
            >
              <input
                type="checkbox"
                checked={consented}
                onChange={(e) => setConsented(e.target.checked)}
                className="mt-0.5 h-4 w-4 cursor-pointer accent-accent"
              />
              <span className="text-[13px] leading-relaxed text-text-secondary">
                I have read and understood the rules above. I consent to being
                recorded and analyzed for the duration of this session. I
                understand that violations will be logged and may affect my
                result.
              </span>
            </motion.label>
          </div>

          {/* right: env check + cta */}
          <div className="lg:col-span-5">
            <div className="lg:sticky lg:top-24">
              <p className="label">Pre-flight</p>
              <p className="mt-1 text-[13px] text-text-secondary">
                We are verifying your environment before calibration.
              </p>
              <div className="mt-4">
                <EnvironmentCheck onReady={() => setEnvReady(true)} />
              </div>

              <button
                type="button"
                disabled={!canStart}
                onClick={() => navigate('/student/calibrate')}
                className={`group mt-6 flex w-full items-center justify-center gap-2 rounded border px-4 py-2.5 text-[13px] font-medium transition-all duration-300 ease-linear ${
                  canStart
                    ? 'border-accent bg-accent text-white hover:bg-accent-hover'
                    : 'cursor-not-allowed border-border bg-surface-2 text-text-muted'
                }`}
              >
                Begin calibration
                <ArrowRight
                  size={14}
                  strokeWidth={2}
                  className={`transition-transform duration-300 ease-linear ${
                    canStart ? 'group-hover:translate-x-0.5' : ''
                  }`}
                />
              </button>

              <p className="mt-3 text-center font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
                {envReady && consented
                  ? 'ready'
                  : envReady
                  ? 'awaiting consent'
                  : 'verifying environment'}
              </p>

              <Link
                to="/login"
                className="mt-6 block text-center text-[12px] text-text-muted hover:text-text-secondary"
              >
                Cancel and return
              </Link>
            </div>
          </div>
        </div>
      </section>
    </PageShell>
  )
}
