import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Check, FileDown } from 'lucide-react'
import PageShell from '../components/PageShell.jsx'
import RiskGauge from '../components/RiskGauge.jsx'
import { useSession } from '../state/SessionContext.jsx'

export default function Done() {
  const { name, code, reset } = useSession()
  // mock final risk
  const finalRisk = 22

  return (
    <PageShell>
      <section className="mx-auto flex max-w-3xl flex-col items-start px-6 pt-20 pb-16">
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          className="inline-flex items-center gap-2 rounded border border-border bg-surface-2 px-2.5 py-1 font-mono text-[10px] uppercase tracking-eyebrow text-risk-low"
        >
          <Check size={12} strokeWidth={2.25} />
          session ended cleanly
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.05, ease: [0.16, 1, 0.3, 1] }}
          className="mt-6 text-4xl font-medium tracking-tightest text-text-primary"
        >
          Thank you, {name || 'candidate'}.
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
          className="mt-4 max-w-xl text-[14px] leading-relaxed text-text-secondary"
        >
          Your session{' '}
          <span className="font-mono text-text-primary">{code}</span> has been
          recorded and analyzed. A summary has been forwarded to your proctor.
          You may close this window.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.15, ease: [0.16, 1, 0.3, 1] }}
          className="mt-10 flex w-full items-center gap-6 rounded border border-border bg-surface-1 p-6"
        >
          <RiskGauge value={finalRisk} size={120} label="Final" />
          <div className="min-w-0 flex-1">
            <p className="label">Outcome</p>
            <p className="mt-1 text-[15px] text-text-primary">
              No critical violations detected.
            </p>
            <p className="mt-2 text-[12px] text-text-muted">
              The proctor will review the full timeline and finalize your result.
            </p>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
          className="mt-8 flex flex-wrap gap-3"
        >
          <Link to={`/report/${code}`} className="btn-primary group">
            <FileDown size={14} strokeWidth={2} />
            Download my summary
          </Link>
          <Link to="/" onClick={reset} className="btn-secondary">
            Back to home
          </Link>
        </motion.div>
      </section>
    </PageShell>
  )
}
