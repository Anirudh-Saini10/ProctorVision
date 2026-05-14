import { useEffect, useRef } from 'react'

/**
 * Reports tab/window focus changes via the supplied callback.
 *
 * Fires AT MOST ONCE per focus-loss episode: subsequent blur/visibility
 * events while already-blurred are suppressed, and the gate resets only
 * when focus returns. This prevents the alert storm that occurred when
 * users alt-tabbed, opened devtools, etc.
 *
 * The callback is fired only while `active` is true.
 */
export default function useTabMonitor({ active, onSwitch }) {
  const lostRef = useRef(false)
  const handlerRef = useRef(onSwitch)

  useEffect(() => {
    handlerRef.current = onSwitch
  }, [onSwitch])

  useEffect(() => {
    if (!active) return
    lostRef.current = false

    // Grace period: ignore the first 1.5s after session activation. Page
    // navigation, devtools opening, and other transient blurs within this
    // window are almost never real cheating signals.
    const armedAt = Date.now() + 1500

    const fire = (reason) => {
      if (lostRef.current) return
      if (Date.now() < armedAt) return
      lostRef.current = true
      handlerRef.current?.(reason)
    }
    const recover = () => {
      lostRef.current = false
    }

    const onVisibility = () => {
      if (document.visibilityState === 'hidden') fire('hidden')
      else recover()
    }
    const onBlur = () => fire('blur')
    const onFocus = () => recover()

    document.addEventListener('visibilitychange', onVisibility)
    window.addEventListener('blur', onBlur)
    window.addEventListener('focus', onFocus)
    return () => {
      document.removeEventListener('visibilitychange', onVisibility)
      window.removeEventListener('blur', onBlur)
      window.removeEventListener('focus', onFocus)
    }
  }, [active])
}
