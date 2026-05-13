/**
 * Subtle animated background grid + radial accent.
 * Drifts very slowly (24s) so it never distracts.
 */
export default function AmbientGrid() {
  return (
    <div
      aria-hidden
      className="pointer-events-none fixed inset-0 -z-10 overflow-hidden"
    >
      {/* drifting grid */}
      <div
        className="absolute inset-[-1px] animate-grid-drift opacity-[0.5]"
        style={{
          backgroundImage:
            "linear-gradient(rgba(255,255,255,0.025) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
        }}
      />
      {/* radial accent — single soft vignette of brand color, top-right */}
      <div
        className="absolute -top-40 -right-40 h-[600px] w-[600px] rounded-full"
        style={{
          background:
            "radial-gradient(circle at center, rgba(59,130,246,0.10) 0%, transparent 60%)",
        }}
      />
      {/* bottom vignette for depth */}
      <div
        className="absolute -bottom-40 -left-40 h-[500px] w-[500px] rounded-full"
        style={{
          background:
            "radial-gradient(circle at center, rgba(99,102,241,0.06) 0%, transparent 60%)",
        }}
      />
    </div>
  )
}
