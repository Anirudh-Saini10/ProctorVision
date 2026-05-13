import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Check, FileDown } from 'lucide-react'
import PageShell from '../components/PageShell.jsx'
import RiskGauge from '../components/RiskGauge.jsx'
import { useSession } from '../state/SessionContext.jsx'
import { useWS } from '../state/WebSocketContext.jsx'
import { REPORT_URL } from '../lib/config.js'

export default function Done() {
  const { name, code, reset } = useSession()
  const { summary, sessionId, riskScore } = useWS()

  const finalRisk = summary?.risk_score ?? riskScore ?? 0
  const violationCount = summary?.violations?.length ?? 0
  const sid = summary?.session_id ?? sessionId
  const verdict =
    finalRisk >= 70
      ? 'High concern. Review recommended.'
      : finalRisk >= 35
      ? 'Moderate signal. Some violations logged.'
      : 'Within expected range. Few or no violations.'

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
          recorded and analyzed. {violationCount} event
          {violationCount === 1 ? '' : 's'} logged. A summary has been forwarded
          to your proctor. You may close this window.
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
            <p className="mt-1 text-[15px] text-text-primary">{verdict}</p>
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
          {sid ? (
            <a href={REPORT_URL(sid)} className="btn-primary group" download>
              <FileDown size={14} strokeWidth={2} />
              Download my summary (PDF)
            </a>
          ) : (
            <button type="button" disabled className="btn-primary opacity-50">
              <FileDown size={14} strokeWidth={2} /> Download my summary
            </button>
          )}
          <Link to="/" onClick={reset} className="btn-secondary">
            Back to home
          </Link>
        </motion.div>

        {sid && (
          <p className="mt-6 font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
            session id · {sid}
          </p>
        )}
      </section>
    </PageShell>
  )
}
