/**
 * Read-only strictness indicator. Shown to the student.
 */
const tone = {
  lenient: { dot: 'bg-risk-low', text: 'text-risk-low' },
  moderate: { dot: 'bg-accent', text: 'text-accent' },
  strict: { dot: 'bg-risk-high', text: 'text-risk-high' },
}

export default function StrictnessBadge({ strictness, size = 'md' }) {
  const t = tone[strictness.id] ?? tone.moderate
  const padding = size === 'lg' ? 'px-3 py-1.5 text-[12px]' : 'px-2.5 py-1 text-[11px]'
  return (
    <span
      className={`inline-flex items-center gap-2 rounded border border-border bg-surface-2 ${padding} font-mono uppercase tracking-eyebrow ${t.text}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${t.dot}`} />
      {strictness.label}
    </span>
  )
}
