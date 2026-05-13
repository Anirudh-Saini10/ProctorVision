/**
 * Pulsing status dot — "system online" indicator.
 * Variants drive color; default is risk-low (green).
 */
const variants = {
  online: "bg-risk-low",
  warn: "bg-risk-medium",
  error: "bg-risk-high",
  accent: "bg-accent",
}

export default function LiveDot({ variant = "online", label, className = "" }) {
  const color = variants[variant] ?? variants.online
  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <span className="relative inline-flex h-1.5 w-1.5">
        <span
          className={`absolute inset-0 rounded-full ${color} animate-pulse-ring`}
        />
        <span
          className={`relative inline-flex h-1.5 w-1.5 rounded-full ${color} animate-pulse-dot`}
        />
      </span>
      {label && (
        <span className="font-mono text-[10px] uppercase tracking-eyebrow text-text-secondary">
          {label}
        </span>
      )}
    </span>
  )
}
