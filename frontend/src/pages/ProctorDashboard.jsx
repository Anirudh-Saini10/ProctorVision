import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Search, ArrowRight, RefreshCw } from 'lucide-react'
import PageShell from '../components/PageShell.jsx'
import LiveDot from '../components/LiveDot.jsx'
import useProctorSocket from '../hooks/useProctorSocket.js'
import { getSessions as getMockSessions } from '../lib/mockSessions.js'

const FILTERS = ['all', 'live', 'ended']

function formatDuration(sec) {
  if (sec == null) return ''
  const m = Math.floor(sec / 60)
  return `${m}m`
}

export default function ProctorDashboard() {
  const { status, activeSessions, reload } = useProctorSocket()
  const [filter, setFilter] = useState('all')
  const [query, setQuery] = useState('')

  // refresh every 4s while open
  useEffect(() => {
    const id = setInterval(() => reload(), 4000)
    return () => clearInterval(id)
  }, [reload])

  // Map backend sessions to row shape; fall back to mocks when empty so the
  // dashboard never looks dead during a portfolio walkthrough.
  const sessions = useMemo(() => {
    if (activeSessions.length > 0) {
      return activeSessions.map((s) => ({
        id: s.session_id,
        candidate: s.candidate,
        status: s.status,
        risk: s.risk,
        lastEvent: s.last_event?.violation_type ?? '—',
        lastEventAgo: s.last_event ? 'live' : '',
        durationLabel: formatDuration(s.duration_sec),
        strictness: (s.strictness || 'moderate').toUpperCase(),
        real: true,
      }))
    }
    return getMockSessions().map((m) => ({
      id: m.id,
      candidate: m.candidate,
      status: m.status,
      risk: m.risk,
      lastEvent: m.lastEvent,
      lastEventAgo: m.lastEventAgo,
      durationLabel: `${m.durationMin}m`,
      strictness: m.strictness?.toUpperCase() ?? 'MODERATE',
      real: false,
    }))
  }, [activeSessions])

  const visible = sessions.filter((s) => {
    if (filter !== 'all' && s.status !== filter) return false
    if (
      query &&
      !s.candidate.toLowerCase().includes(query.toLowerCase()) &&
      !s.id.toLowerCase().includes(query.toLowerCase())
    )
      return false
    return true
  })

  const stats = {
    active: sessions.filter((s) => s.status === 'live').length,
    flagged: sessions.filter((s) => s.risk >= 50).length,
    avgRisk: sessions.length
      ? Math.round(sessions.reduce((a, s) => a + s.risk, 0) / sessions.length)
      : 0,
    ended: sessions.filter((s) => s.status === 'ended').length,
  }

  const wsLabel =
    status === 'open'
      ? 'connected'
      : status === 'connecting'
      ? 'connecting'
      : status === 'closed'
      ? 'disconnected'
      : status

  return (
    <PageShell>
      <section className="mx-auto max-w-7xl px-6 pt-12 pb-16">
        <div className="flex items-end justify-between">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
              proctor console · {wsLabel}
            </p>
            <h1 className="mt-2 text-3xl font-medium tracking-tightest text-text-primary">
              Sessions
            </h1>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={reload}
              className="btn-secondary"
              title="Refresh"
            >
              <RefreshCw size={13} strokeWidth={2} />
              Refresh
            </button>
            <Link to="/proctor/rules" className="btn-secondary">
              Configure rules
            </Link>
          </div>
        </div>

        <div className="mt-8 grid grid-cols-2 gap-px overflow-hidden rounded border border-border bg-border sm:grid-cols-4">
          <Stat label="active" value={stats.active} accent="accent" />
          <Stat label="flagged" value={stats.flagged} accent="risk-high" />
          <Stat label="avg risk" value={`${stats.avgRisk}/100`} />
          <Stat label="ended today" value={stats.ended} />
        </div>

        <div className="mt-8 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-1 rounded border border-border bg-surface-1 p-1">
            {FILTERS.map((f) => (
              <button
                key={f}
                type="button"
                onClick={() => setFilter(f)}
                className={`rounded px-3 py-1 font-mono text-[11px] uppercase tracking-eyebrow transition-colors ${
                  filter === f
                    ? 'bg-surface-3 text-text-primary'
                    : 'text-text-muted hover:text-text-secondary'
                }`}
              >
                {f}
              </button>
            ))}
          </div>

          <div className="relative w-full max-w-xs">
            <Search
              size={14}
              strokeWidth={1.5}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted"
            />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search candidate or code"
              className="input w-full pl-9"
            />
          </div>
        </div>

        {activeSessions.length === 0 && (
          <p className="mt-3 font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
            no live sessions · showing demo roster
          </p>
        )}

        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          className="mt-4 overflow-hidden rounded border border-border bg-surface-1"
        >
          <div className="grid grid-cols-12 gap-4 border-b border-border bg-surface-2 px-4 py-2.5 font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
            <span className="col-span-4">candidate</span>
            <span className="col-span-3">session</span>
            <span className="col-span-1">status</span>
            <span className="col-span-1 text-right">risk</span>
            <span className="col-span-2">last event</span>
            <span className="col-span-1 text-right">·</span>
          </div>
          <ul className="divide-y divide-border">
            {visible.map((s, i) => (
              <SessionRow key={s.id} session={s} index={i} />
            ))}
            {visible.length === 0 && (
              <li className="px-4 py-10 text-center font-mono text-[11px] uppercase tracking-eyebrow text-text-muted">
                no sessions match
              </li>
            )}
          </ul>
        </motion.div>
      </section>
    </PageShell>
  )
}

function Stat({ label, value, accent }) {
  const tone =
    accent === 'accent'
      ? 'text-accent'
      : accent === 'risk-high'
      ? 'text-risk-high'
      : 'text-text-primary'
  return (
    <div className="bg-surface-1 px-5 py-4">
      <p className="label">{label}</p>
      <p className={`mt-1 font-mono text-2xl tabular-nums ${tone}`}>{value}</p>
    </div>
  )
}

function SessionRow({ session, index }) {
  const live = session.status === 'live'
  const riskTone =
    session.risk >= 70
      ? 'text-risk-high'
      : session.risk >= 35
      ? 'text-risk-medium'
      : 'text-risk-low'
  return (
    <motion.li
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3, delay: index * 0.02 }}
    >
      <Link
        to={`/proctor/session/${session.id}`}
        className="grid grid-cols-12 items-center gap-4 px-4 py-3 transition-colors hover:bg-surface-2"
      >
        <div className="col-span-4 flex items-center gap-3">
          <div className="grid h-7 w-7 place-items-center rounded-full bg-surface-3 font-mono text-[10px] uppercase text-text-secondary">
            {session.candidate
              .split(' ')
              .map((n) => n[0])
              .join('')
              .slice(0, 2)}
          </div>
          <span className="text-[13px] text-text-primary">{session.candidate}</span>
          {!session.real && (
            <span className="font-mono text-[9px] uppercase tracking-eyebrow text-text-muted">
              demo
            </span>
          )}
        </div>
        <span className="col-span-3 font-mono text-[12px] tracking-wider text-text-secondary">
          {session.id.slice(0, 12)}
        </span>
        <span className="col-span-1">
          {live ? (
            <LiveDot variant="online" label="live" />
          ) : (
            <span className="font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
              ended
            </span>
          )}
        </span>
        <span className={`col-span-1 text-right font-mono tabular-nums ${riskTone}`}>
          {session.risk}
        </span>
        <span className="col-span-2 truncate text-[12px] text-text-secondary">
          <span className="text-text-primary">{session.lastEvent}</span>
          {session.lastEventAgo && (
            <span className="ml-2 font-mono text-[10px] text-text-muted">
              {session.lastEventAgo}
            </span>
          )}
        </span>
        <span className="col-span-1 flex justify-end">
          <ArrowRight size={14} strokeWidth={1.5} className="text-text-muted" />
        </span>
      </Link>
    </motion.li>
  )
}
