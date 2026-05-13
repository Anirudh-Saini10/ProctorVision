import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowRight, KeyRound, User } from 'lucide-react'
import PageShell from '../components/PageShell.jsx'
import { useSession } from '../state/SessionContext.jsx'

export default function Login() {
  const navigate = useNavigate()
  const { enter } = useSession()
  const [name, setName] = useState('')
  const [code, setCode] = useState('')
  const [error, setError] = useState('')

  const onSubmit = (e) => {
    e.preventDefault()
    const trimmedName = name.trim()
    const trimmedCode = code.trim().toUpperCase()
    if (!trimmedName) return setError('Enter your full name.')
    if (trimmedCode.length < 4)
      return setError('Session code must be at least 4 characters.')
    setError('')
    enter(trimmedName, trimmedCode)
    if (trimmedCode.startsWith('P-')) {
      navigate('/proctor', { replace: true })
    } else {
      navigate('/student', { replace: true })
    }
  }

  return (
    <PageShell>
      <section className="mx-auto flex w-full max-w-md flex-1 flex-col items-stretch justify-center px-6 py-16">
        <motion.p
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          className="font-mono text-[10px] uppercase tracking-eyebrow text-text-muted"
        >
          authentication / session-code
        </motion.p>

        <motion.h1
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1], delay: 0.05 }}
          className="mt-3 text-3xl font-medium tracking-tightest text-text-primary"
        >
          Enter your session.
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1], delay: 0.1 }}
          className="mt-2 text-[14px] text-text-secondary"
        >
          Use the code provided by your institution. Codes prefixed with{' '}
          <span className="font-mono text-text-primary">P-</span> open the
          proctor console.
        </motion.p>

        <motion.form
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1], delay: 0.15 }}
          onSubmit={onSubmit}
          className="mt-8 flex flex-col gap-4"
        >
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
            label="Session code"
            value={code}
            onChange={(v) => setCode(v.toUpperCase())}
            placeholder="ABC123"
            mono
          />

          {error && (
            <p className="text-[12px] text-risk-high">{error}</p>
          )}

          <button type="submit" className="btn-primary mt-2 group">
            Continue
            <ArrowRight
              size={14}
              strokeWidth={2}
              className="transition-transform duration-300 ease-linear group-hover:translate-x-0.5"
            />
          </button>
        </motion.form>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.4 }}
          className="mt-10 flex items-center gap-2 text-[11px] text-text-muted"
        >
          <span className="font-mono">demo:</span>
          <button
            type="button"
            onClick={() => {
              setName('Aanya Mehta')
              setCode('ABC123')
            }}
            className="font-mono text-text-secondary hover:text-text-primary"
          >
            student / ABC123
          </button>
          <span className="text-text-muted">·</span>
          <button
            type="button"
            onClick={() => {
              setName('Dr. Rao')
              setCode('P-7HX2')
            }}
            className="font-mono text-text-secondary hover:text-text-primary"
          >
            proctor / P-7HX2
          </button>
        </motion.div>
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
