import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowRight, KeyRound, User } from 'lucide-react'
import PageShell from '../components/PageShell.jsx'
import { publicApi, attemptsApi } from '../lib/api.js'
import { useSession } from '../state/SessionContext.jsx'

/**
 * Candidate-facing entry. Type the join code your proctor shared, type
 * your name, and we'll fetch the exam payload + register an Attempt
 * row in the DB. From here we drop the candidate into the standard
 * /student lobby → calibrate → exam pipeline; the only difference vs
 * the demo flow is that SessionContext now carries the real exam
 * (with questions) and attemptId.
 */
export default function Join() {
  const navigate = useNavigate()
  const { joinExam } = useSession()
  const [name, setName] = useState('')
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const onSubmit = async (e) => {
    e.preventDefault()
    const trimmedName = name.trim()
    const trimmedCode = code.trim().toUpperCase()
    if (!trimmedName) return setError('Enter your full name.')
    if (trimmedCode.length < 4) return setError('Enter the join code from your proctor.')

    setError('')
    setBusy(true)
    try {
      // Fetch the public exam payload (questions WITHOUT correct
      // answers). 404 → bad code; 403 → exam not live.
      const exam = await publicApi.examByCode(trimmedCode)
      // Register an attempt row so the proctor sees this candidate
      // listed under their exam even before they finish.
      const started = await attemptsApi.start({
        code: trimmedCode,
        candidate_name: trimmedName,
      })
      joinExam({
        name: trimmedName,
        code: trimmedCode,
        exam,
        attemptId: started.attempt_id,
      })
      navigate('/student', { replace: true })
    } catch (err) {
      setError(err.message || 'Could not join — please check the code.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <PageShell>
      <section className="mx-auto flex w-full max-w-md flex-1 flex-col px-6 py-16">
        <motion.p
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="font-mono text-[10px] uppercase tracking-eyebrow text-text-muted"
        >
          candidate / join exam
        </motion.p>
        <motion.h1
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.05 }}
          className="mt-3 text-3xl font-medium tracking-tightest text-text-primary"
        >
          Join your exam.
        </motion.h1>
        <motion.p
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
          className="mt-2 text-[14px] text-text-secondary"
        >
          Enter the join code your proctor shared with you, and your full
          name as it should appear on the report.
        </motion.p>

        <form onSubmit={onSubmit} className="mt-8 flex flex-col gap-4">
          <Field
            icon={User}
            label="Full name"
            value={name}
            onChange={setName}
            placeholder="Aanya Mehta"
            autoFocus
          />
          <Field
            icon={KeyRound}
            label="Join code"
            value={code}
            onChange={(v) => setCode(v.toUpperCase())}
            placeholder="A3K7QF"
            mono
          />
          {error && <p className="text-[12px] text-risk-high">{error}</p>}
          <button
            type="submit"
            disabled={busy}
            className="btn-primary mt-2 group disabled:opacity-50"
          >
            {busy ? 'Joining…' : 'Continue'}
            <ArrowRight
              size={14}
              strokeWidth={2}
              className="transition-transform duration-300 ease-linear group-hover:translate-x-0.5"
            />
          </button>
        </form>

        <p className="mt-8 text-center text-[12px] text-text-muted">
          Are you a proctor?{' '}
          <Link to="/proctor/login" className="text-text-secondary hover:text-text-primary">
            Sign in to your dashboard →
          </Link>
        </p>
      </section>
    </PageShell>
  )
}

function Field({ icon: Icon, label, value, onChange, placeholder, mono = false, autoFocus = false }) {
  return (
    <label className="block">
      <span className="label mb-2 block">{label}</span>
      <div className="relative">
        <Icon
          size={14}
          strokeWidth={1.5}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted"
        />
        <input
          type="text"
          value={value}
          autoFocus={autoFocus}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className={`input w-full pl-9 ${mono ? 'font-mono tracking-wider' : ''}`}
        />
      </div>
    </label>
  )
}
