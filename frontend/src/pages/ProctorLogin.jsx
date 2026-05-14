import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowRight, KeyRound, Mail, User } from 'lucide-react'
import PageShell from '../components/PageShell.jsx'
import { useAuth } from '../state/AuthContext.jsx'

/**
 * Combined login / register screen for proctors. Two tabs, single
 * page so the deep-link from the landing page lands somewhere
 * actionable regardless of whether the user has an account.
 */
export default function ProctorLogin() {
  const { login, register } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const redirectTo = location.state?.from || '/proctor'

  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const onSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      if (mode === 'login') {
        await login(email.trim().toLowerCase(), password)
      } else {
        if (name.trim().length < 1) throw new Error('Enter your name.')
        if (password.length < 6) throw new Error('Password must be at least 6 characters.')
        await register(email.trim().toLowerCase(), name.trim(), password)
      }
      navigate(redirectTo, { replace: true })
    } catch (err) {
      setError(err.message || 'Something went wrong.')
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
          proctor / authentication
        </motion.p>
        <motion.h1
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.05 }}
          className="mt-3 text-3xl font-medium tracking-tightest text-text-primary"
        >
          {mode === 'login' ? 'Sign in to ProctorVision.' : 'Create a proctor account.'}
        </motion.h1>

        <div className="mt-6 inline-flex self-start rounded border border-border bg-surface-1 p-1">
          {[
            ['login', 'Sign in'],
            ['register', 'Create account'],
          ].map(([v, label]) => (
            <button
              key={v}
              type="button"
              onClick={() => {
                setMode(v)
                setError('')
              }}
              className={`rounded px-3 py-1.5 font-mono text-[11px] uppercase tracking-eyebrow transition-colors ${
                mode === v
                  ? 'bg-accent text-white'
                  : 'text-text-muted hover:text-text-primary'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        <form onSubmit={onSubmit} className="mt-6 flex flex-col gap-4">
          <Field
            icon={Mail}
            label="Email"
            type="email"
            value={email}
            onChange={setEmail}
            placeholder="you@example.com"
            autoFocus
          />
          {mode === 'register' && (
            <Field
              icon={User}
              label="Display name"
              value={name}
              onChange={setName}
              placeholder="Dr. Rao"
            />
          )}
          <Field
            icon={KeyRound}
            label="Password"
            type="password"
            value={password}
            onChange={setPassword}
            placeholder={mode === 'login' ? '••••••••' : 'min. 6 characters'}
          />
          {error && <p className="text-[12px] text-risk-high">{error}</p>}
          <button
            type="submit"
            disabled={busy}
            className="btn-primary mt-2 group disabled:opacity-50"
          >
            {busy ? 'Working…' : mode === 'login' ? 'Sign in' : 'Create account'}
            <ArrowRight
              size={14}
              strokeWidth={2}
              className="transition-transform duration-300 ease-linear group-hover:translate-x-0.5"
            />
          </button>
        </form>

        <p className="mt-8 text-center text-[12px] text-text-muted">
          Are you a candidate?{' '}
          <Link to="/join" className="text-text-secondary hover:text-text-primary">
            Join an exam with a code →
          </Link>
        </p>
      </section>
    </PageShell>
  )
}

function Field({ icon: Icon, label, value, onChange, placeholder, type = 'text', autoFocus }) {
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
          type={type}
          value={value}
          autoFocus={autoFocus}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="input w-full pl-9"
        />
      </div>
    </label>
  )
}
