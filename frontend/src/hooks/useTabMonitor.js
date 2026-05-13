import { useEffect } from 'react'

/**
 * Reports tab/window focus changes via the supplied callback.
 * - 'hidden' when document.visibilityState becomes hidden (tab switch / minimize)
 * - 'blur'   when window loses focus (alt-tab to another window)
 *
 * The callback is fired only while `active` is true.
 */
export default function useTabMonitor({ active, onSwitch }) {
  useEffect(() => {
    if (!active) return

    const onVisibility = () => {
      if (document.visibilityState === 'hidden') onSwitch?.('hidden')
    }
    const onBlur = () => onSwitch?.('blur')

    document.addEventListener('visibilitychange', onVisibility)
    window.addEventListener('blur', onBlur)
    return () => {
      document.removeEventListener('visibilitychange', onVisibility)
      window.removeEventListener('blur', onBlur)
    }
  }, [active, onSwitch])
}
