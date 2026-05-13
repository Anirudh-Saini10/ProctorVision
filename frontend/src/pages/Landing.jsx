import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowUpRight, Eye, Headphones, ScanFace, Activity } from 'lucide-react'
import PageShell from '../components/PageShell.jsx'
import LiveDot from '../components/LiveDot.jsx'
import TelemetryTile from '../components/TelemetryTile.jsx'

const fadeUp = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] },
}

export default function Landing() {
  return (
    <PageShell>
      <section className="mx-auto max-w-7xl px-6 pt-20 pb-16 sm:pt-28">
        <div className="grid gap-16 lg:grid-cols-12 lg:gap-12">
          {/* left: copy */}
          <div className="lg:col-span-7">
            <motion.div {...fadeUp}>
              <LiveDot variant="online" label="system online" />
            </motion.div>

            <motion.h1
              {...fadeUp}
              transition={{ ...fadeUp.transition, delay: 0.05 }}
              className="mt-8 max-w-3xl text-[44px] font-medium leading-[1.05] tracking-tightest text-text-primary sm:text-[64px]"
            >
              Computer vision proctoring,
              <br />
              <span className="text-text-secondary">built for integrity.</span>
            </motion.h1>

            <motion.p
              {...fadeUp}
              transition={{ ...fadeUp.transition, delay: 0.1 }}
              className="mt-6 max-w-xl text-[15px] leading-relaxed text-text-secondary"
            >
              Real-time gaze, head pose, lip movement, and object detection
              running on-device. Calibrated to each candidate. Designed for
              remote exams that respect both rigor and the people taking them.
            </motion.p>

            <motion.div
              {...fadeUp}
              transition={{ ...fadeUp.transition, delay: 0.15 }}
              className="mt-10 flex flex-wrap items-center gap-3"
            >
              <Link to="/login" className="btn-primary group">
                Begin proctored session
                <ArrowUpRight
                  size={14}
                  strokeWidth={2}
                  className="transition-transform duration-300 ease-linear group-hover:translate-x-0.5 group-hover:-translate-y-0.5"
                />
              </Link>
              <Link to="/login" className="btn-secondary">
                Proctor sign-in
              </Link>
            </motion.div>

            {/* feature row — terminal-style, not card slop */}
            <motion.div
              {...fadeUp}
              transition={{ ...fadeUp.transition, delay: 0.2 }}
              className="mt-16 grid max-w-2xl grid-cols-2 gap-x-10 gap-y-6 sm:grid-cols-4"
            >
              <Feature icon={Eye} label="Gaze" />
              <Feature icon={ScanFace} label="Head pose" />
              <Feature icon={Activity} label="Lip motion" />
              <Feature icon={Headphones} label="Objects" />
            </motion.div>
          </div>

          {/* right: live tile */}
          <div className="lg:col-span-5">
            <div className="lg:sticky lg:top-24">
              <TelemetryTile />
              <motion.div
                {...fadeUp}
                transition={{ ...fadeUp.transition, delay: 0.4 }}
                className="mt-3 flex items-center justify-between font-mono text-[10px] uppercase tracking-eyebrow text-text-muted"
              >
                <span>preview / non-authoritative</span>
                <span>frame ∞</span>
              </motion.div>
            </div>
          </div>
        </div>
      </section>

      <Footer />
    </PageShell>
  )
}

function Feature({ icon: Icon, label }) {
  return (
    <div className="flex items-center gap-2.5 border-l border-border pl-3">
      <Icon size={14} strokeWidth={1.5} className="text-text-secondary" />
      <span className="text-[13px] text-text-primary">{label}</span>
    </div>
  )
}

function Footer() {
  return (
    <footer className="mt-auto border-t border-border">
      <div className="mx-auto flex max-w-7xl flex-col gap-2 px-6 py-4 font-mono text-[10px] uppercase tracking-eyebrow text-text-muted sm:flex-row sm:items-center sm:justify-between">
        <span>proctorvision · build a1b2c3d</span>
        <span className="flex items-center gap-2">
          <span>uptime 99.9%</span>
          <LiveDot variant="online" />
        </span>
      </div>
      <div className="mx-auto max-w-7xl px-6 pb-5 pt-1 text-[11px] text-text-muted">
        Built by{' '}
        <span className="text-text-secondary">Anirudh Saini</span>
        <span className="mx-1.5 text-text-muted">·</span>
        <a
          href="#"
          className="font-mono uppercase tracking-eyebrow text-text-secondary transition-colors hover:text-accent"
        >
          VELOUR
        </a>
      </div>
    </footer>
  )
}
