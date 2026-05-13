import PageShell from '../components/PageShell.jsx'

export default function Report() {
  return (
    <PageShell>
      <section className="mx-auto max-w-7xl px-6 py-20">
        <p className="font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
          /report
        </p>
        <h1 className="mt-4 text-3xl font-medium tracking-tightest text-text-primary">
          Session report
        </h1>
        <p className="mt-3 max-w-lg text-[14px] text-text-secondary">
          Violation timeline, risk score breakdown, and PDF download will live
          here. Coming in the next phase.
        </p>
      </section>
    </PageShell>
  )
}
