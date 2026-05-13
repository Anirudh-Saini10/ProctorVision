import { useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowLeft, Save } from 'lucide-react'
import PageShell from '../components/PageShell.jsx'
import StrictnessBadge from '../components/StrictnessBadge.jsx'
import { STRICTNESS } from '../state/SessionContext.jsx'

const PROFILES = [STRICTNESS.lenient, STRICTNESS.moderate, STRICTNESS.strict]

const RULES = [
  {
    id: 'gaze_off_screen',
    label: 'Gaze off screen',
    description:
      'Triggers when the candidate looks away from the screen for longer than the configured threshold.',
    thresholds: { lenient: '3.0s', moderate: '2.0s', strict: '1.2s' },
  },
  {
    id: 'head_turn',
    label: 'Head turn',
    description:
      'Detects sustained yaw beyond the calibrated baseline. Brief head movements are ignored.',
    thresholds: { lenient: '25°', moderate: '18°', strict: '12°' },
  },
  {
    id: 'lip_movement',
    label: 'Lip movement',
    description:
      'Possible vocalization. May be allowed if think-aloud is permitted.',
    thresholds: { lenient: 'off', moderate: 'on', strict: 'on' },
  },
  {
    id: 'multiple_faces',
    label: 'Multiple faces',
    description:
      'Another person enters the camera frame.',
    thresholds: { lenient: 'flag', moderate: 'flag', strict: 'flag' },
  },
  {
    id: 'phone_detected',
    label: 'Phone in frame',
    description:
      'YOLOv8 detects a mobile device in the candidate environment.',
    thresholds: { lenient: 'flag', moderate: 'flag', strict: 'flag' },
  },
  {
    id: 'tab_switch',
    label: 'Tab switch / focus loss',
    description:
      'The browser reports loss of visibility or window focus.',
    thresholds: { lenient: 'warn', moderate: 'flag', strict: 'flag' },
  },
]

export default function ProctorRules() {
  const [active, setActive] = useState('moderate')
  const profile = PROFILES.find((p) => p.id === active) ?? PROFILES[1]

  return (
    <PageShell>
      <section className="mx-auto max-w-5xl px-6 pt-10 pb-16">
        <Link
          to="/proctor"
          className="inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-eyebrow text-text-muted hover:text-text-secondary"
        >
          <ArrowLeft size={11} strokeWidth={2} /> sessions
        </Link>

        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          className="mt-4"
        >
          <p className="font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
            strictness profiles
          </p>
          <h1 className="mt-2 text-3xl font-medium tracking-tightest text-text-primary">
            Rules
          </h1>
          <p className="mt-2 max-w-xl text-[14px] text-text-secondary">
            Profiles compose the thresholds and severities of every detector
            into a single setting that applies to a session. Custom rules and
            cooldowns will be configurable in a later release.
          </p>
        </motion.div>

        {/* Profile selector */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.05, ease: [0.16, 1, 0.3, 1] }}
          className="mt-8 grid gap-3 sm:grid-cols-3"
        >
          {PROFILES.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => setActive(p.id)}
              className={`rounded border bg-surface-1 p-5 text-left transition-colors ${
                active === p.id
                  ? 'border-accent'
                  : 'border-border hover:border-border-strong'
              }`}
            >
              <StrictnessBadge strictness={p} />
              <p className="mt-3 text-[15px] text-text-primary">{p.label}</p>
              <p className="mt-1 text-[12px] leading-relaxed text-text-secondary">
                {p.blurb}
              </p>
            </button>
          ))}
        </motion.div>

        {/* Rules table */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
          className="mt-6 overflow-hidden rounded border border-border bg-surface-1"
        >
          <div className="grid grid-cols-12 gap-4 border-b border-border bg-surface-2 px-4 py-2.5 font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
            <span className="col-span-3">rule</span>
            <span className="col-span-6">description</span>
            <span className="col-span-3 text-right">threshold ({profile.label})</span>
          </div>
          <ul className="divide-y divide-border">
            {RULES.map((r) => (
              <li
                key={r.id}
                className="grid grid-cols-12 items-start gap-4 px-4 py-3 text-[13px]"
              >
                <span className="col-span-3 font-mono text-text-primary">
                  {r.label}
                </span>
                <span className="col-span-6 text-text-secondary">
                  {r.description}
                </span>
                <span className="col-span-3 text-right font-mono text-text-primary">
                  {r.thresholds[active]}
                </span>
              </li>
            ))}
          </ul>
        </motion.div>

        <div className="mt-8 flex justify-end gap-2">
          <Link to="/proctor" className="btn-secondary">
            Cancel
          </Link>
          <button
            type="button"
            className="btn-primary"
            onClick={() => alert('Saved (mock — backend persistence pending)')}
          >
            <Save size={14} strokeWidth={2} /> Save profile
          </button>
        </div>

        <p className="mt-6 font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
          rules are read-only in this preview · backend persistence pending
        </p>
      </section>
    </PageShell>
  )
}
