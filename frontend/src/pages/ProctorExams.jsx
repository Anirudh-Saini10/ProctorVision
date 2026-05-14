import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Plus, LogOut, Copy, Check, ExternalLink } from 'lucide-react'
import PageShell from '../components/PageShell.jsx'
import { examsApi } from '../lib/api.js'
import { useAuth } from '../state/AuthContext.jsx'

/**
 * Proctor home — list of exams I've created. Each row links into the
 * editor (reuses for view + edit) and exposes the join code for
 * sharing with candidates.
 */
export default function ProctorExams() {
  const { proctor, logout } = useAuth()
  const navigate = useNavigate()
  const [exams, setExams] = useState(null)
  const [error, setError] = useState('')
  const [copiedCode, setCopiedCode] = useState(null)

  useEffect(() => {
    examsApi
      .list()
      .then(setExams)
      .catch((e) => setError(e.message))
  }, [])

  const copy = async (code) => {
    try {
      await navigator.clipboard.writeText(code)
      setCopiedCode(code)
      setTimeout(() => setCopiedCode(null), 1500)
    } catch {
      /* ignore */
    }
  }

  return (
    <PageShell>
      <section className="mx-auto max-w-6xl px-6 pt-12 pb-16">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
              proctor / exams
            </p>
            <h1 className="mt-2 text-3xl font-medium tracking-tightest text-text-primary">
              My exams
            </h1>
            <p className="mt-1 text-[13px] text-text-secondary">
              Signed in as {proctor?.name} ({proctor?.email})
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link
              to="/proctor/sessions"
              className="btn-secondary"
              title="Open the live monitoring console"
            >
              Live console
            </Link>
            <Link to="/proctor/exams/new" className="btn-primary">
              <Plus size={14} strokeWidth={2} /> New exam
            </Link>
            <button
              type="button"
              onClick={() => {
                logout()
                navigate('/proctor/login', { replace: true })
              }}
              className="btn-secondary"
            >
              <LogOut size={13} strokeWidth={2} /> Sign out
            </button>
          </div>
        </div>

        {error && (
          <p className="mt-6 rounded border border-risk-high/40 bg-risk-high/5 p-3 text-[13px] text-risk-high">
            {error}
          </p>
        )}

        <div className="mt-8 grid gap-3">
          {exams === null && !error && (
            <p className="font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
              loading…
            </p>
          )}
          {exams && exams.length === 0 && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="rounded border border-dashed border-border bg-surface-1 p-10 text-center"
            >
              <p className="text-[14px] text-text-secondary">
                No exams yet. Create your first one to generate a join code.
              </p>
              <Link to="/proctor/exams/new" className="btn-primary mt-4 inline-flex">
                <Plus size={14} strokeWidth={2} /> Create exam
              </Link>
            </motion.div>
          )}
          {exams &&
            exams.map((e, i) => (
              <motion.div
                key={e.id}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.03 }}
                className="grid grid-cols-12 items-center gap-4 rounded border border-border bg-surface-1 p-4 hover:border-border-strong"
              >
                <div className="col-span-12 sm:col-span-5">
                  <Link
                    to={`/proctor/exams/${e.id}`}
                    className="block text-[15px] text-text-primary hover:underline"
                  >
                    {e.title}
                  </Link>
                  <p className="mt-1 font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
                    {e.question_count} {e.question_count === 1 ? 'question' : 'questions'}
                    {' · '}
                    {e.attempt_count} {e.attempt_count === 1 ? 'attempt' : 'attempts'}
                    {' · '}
                    strictness {e.strictness}
                    {' · '}
                    {e.duration_min}m
                  </p>
                </div>
                <div className="col-span-7 sm:col-span-3">
                  <p className="label">Join code</p>
                  <div className="mt-1 flex items-center gap-2">
                    <code className="font-mono text-lg tracking-widest text-text-primary">
                      {e.code}
                    </code>
                    <button
                      type="button"
                      onClick={() => copy(e.code)}
                      className="rounded border border-border p-1.5 text-text-muted hover:text-text-primary"
                      title="Copy code"
                    >
                      {copiedCode === e.code ? (
                        <Check size={13} strokeWidth={2} className="text-accent" />
                      ) : (
                        <Copy size={13} strokeWidth={2} />
                      )}
                    </button>
                  </div>
                </div>
                <div className="col-span-3 sm:col-span-2">
                  <span
                    className={`inline-block rounded border px-2 py-0.5 font-mono text-[10px] uppercase tracking-eyebrow ${
                      e.status === 'live'
                        ? 'border-accent/50 bg-accent/10 text-accent'
                        : e.status === 'closed'
                        ? 'border-border bg-surface-2 text-text-muted'
                        : 'border-risk-medium/40 bg-risk-medium/10 text-risk-medium'
                    }`}
                  >
                    {e.status}
                  </span>
                </div>
                <div className="col-span-2 flex justify-end gap-2">
                  <Link
                    to={`/proctor/exams/${e.id}`}
                    className="btn-secondary text-[12px]"
                  >
                    Open <ExternalLink size={12} strokeWidth={2} />
                  </Link>
                </div>
              </motion.div>
            ))}
        </div>
      </section>
    </PageShell>
  )
}
