import { motion } from 'framer-motion'

const SECTIONS = [
  {
    label: 'Environment',
    items: [
      'Quiet, well-lit room with no other people present.',
      'Plain background; no screens or printed material visible.',
      'Stable internet connection and power supply.',
    ],
  },
  {
    label: 'Workstation',
    items: [
      'One monitor only. Close all other applications and tabs.',
      'Webcam centered at eye level. Microphone unmuted.',
      'Phone, smartwatch, headphones must be out of reach.',
    ],
  },
  {
    label: 'Behavior',
    items: [
      'Look at the screen. Brief glances are fine; sustained off-task gaze is flagged.',
      'Do not leave the camera frame. Do not cover your face.',
      'Speaking aloud is allowed only if explicitly permitted.',
    ],
  },
  {
    label: 'Pre-Exam',
    items: [
      'Complete calibration before the exam begins.',
      'Acknowledge consent. Sessions are recorded and analyzed locally.',
      'Once started, the session cannot be paused.',
    ],
  },
]

export default function RulesList() {
  return (
    <div className="space-y-7">
      {SECTIONS.map((section, i) => (
        <motion.div
          key={section.label}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: i * 0.06, ease: [0.16, 1, 0.3, 1] }}
        >
          <p className="label">{section.label}</p>
          <ul className="mt-3 space-y-1.5">
            {section.items.map((item, j) => (
              <li
                key={j}
                className="flex gap-3 text-[13px] leading-relaxed text-text-secondary"
              >
                <span className="mt-2 h-px w-3 shrink-0 bg-border-strong" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </motion.div>
      ))}
    </div>
  )
}
