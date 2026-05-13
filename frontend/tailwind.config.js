/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        surface: {
          0: "#0a0a0a",
          1: "#111111",
          2: "#141414",
          3: "#1a1a1a",
          4: "#222222",
        },
        border: {
          DEFAULT: "rgba(255,255,255,0.06)",
          strong: "rgba(255,255,255,0.12)",
        },
        text: {
          primary: "#e5e5e5",
          secondary: "#a3a3a3",
          muted: "#737373",
        },
        accent: {
          DEFAULT: "#3b82f6",
          hover: "#2563eb",
          active: "#1d4ed8",
        },
        risk: {
          low: "#4ade80",
          medium: "#facc15",
          high: "#f87171",
        },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
      },
      borderRadius: {
        DEFAULT: "4px",
        sm: "2px",
        md: "4px",
        lg: "6px",
      },
      letterSpacing: {
        tightest: "-0.04em",
        eyebrow: "0.16em",
      },
      transitionTimingFunction: {
        linear: "cubic-bezier(0.16, 1, 0.3, 1)",
      },
      keyframes: {
        "pulse-dot": {
          "0%, 100%": { opacity: 1, transform: "scale(1)" },
          "50%": { opacity: 0.6, transform: "scale(0.85)" },
        },
        "pulse-ring": {
          "0%": { transform: "scale(0.9)", opacity: 0.6 },
          "100%": { transform: "scale(2.2)", opacity: 0 },
        },
        "grid-drift": {
          "0%": { transform: "translate(0, 0)" },
          "100%": { transform: "translate(48px, 48px)" },
        },
        "shimmer": {
          "0%": { backgroundPosition: "200% 0" },
          "100%": { backgroundPosition: "-200% 0" },
        },
      },
      animation: {
        "pulse-dot": "pulse-dot 1.8s ease-in-out infinite",
        "pulse-ring": "pulse-ring 1.8s ease-out infinite",
        "grid-drift": "grid-drift 24s linear infinite",
        "shimmer": "shimmer 6s linear infinite",
      },
    },
  },
  plugins: [],
}
