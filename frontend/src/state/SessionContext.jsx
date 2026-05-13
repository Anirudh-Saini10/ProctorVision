import { createContext, useContext, useState, useCallback } from 'react'

/**
 * Lightweight session state — no real auth.
 * Codes starting with `P-` route to proctor; anything else is treated as student.
 * Strictness is set per-session (mocked) and shown read-only to the student.
 */
const SessionContext = createContext(null)

const STRICTNESS = {
  lenient: {
    id: 'lenient',
    label: 'Lenient',
    blurb:
      'Forgiving thresholds. Brief glances away or off-camera moments are tolerated. Best for low-stakes assessments.',
  },
  moderate: {
    id: 'moderate',
    label: 'Moderate',
    blurb:
      'Balanced thresholds. Sustained gaze deviation, head turns, and detected objects are flagged. Recommended default.',
  },
  strict: {
    id: 'strict',
    label: 'Strict',
    blurb:
      'Tight thresholds with short cooldowns. Any sustained off-task behavior or environmental anomaly is logged. For high-stakes exams.',
  },
}

function deriveRole(code) {
  if (!code) return null
  return code.trim().toUpperCase().startsWith('P-') ? 'proctor' : 'student'
}

function deriveStrictness(code) {
  // last char of code seeds the mock strictness so each code feels deterministic
  const c = (code ?? '').trim().slice(-1).toUpperCase()
  if (!c) return STRICTNESS.moderate
  if ('AEIOU'.includes(c)) return STRICTNESS.strict
  if ('0123456789'.includes(c)) return STRICTNESS.lenient
  return STRICTNESS.moderate
}

export function SessionProvider({ children }) {
  const [name, setName] = useState('')
  const [code, setCode] = useState('')
  const [consented, setConsented] = useState(false)
  const [calibrated, setCalibrated] = useState(false)

  const enter = useCallback((nm, cd) => {
    setName(nm)
    setCode(cd)
    setConsented(false)
    setCalibrated(false)
  }, [])

  const reset = useCallback(() => {
    setName('')
    setCode('')
    setConsented(false)
    setCalibrated(false)
  }, [])

  const role = deriveRole(code)
  const strictness = deriveStrictness(code)

  return (
    <SessionContext.Provider
      value={{
        name,
        code,
        role,
        strictness,
        consented,
        setConsented,
        calibrated,
        setCalibrated,
        enter,
        reset,
      }}
    >
      {children}
    </SessionContext.Provider>
  )
}

export function useSession() {
  const ctx = useContext(SessionContext)
  if (!ctx) throw new Error('useSession must be used within SessionProvider')
  return ctx
}

export { STRICTNESS }
