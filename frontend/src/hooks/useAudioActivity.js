import { useEffect, useRef, useState } from 'react'

/**
 * Audio-based speech detection.
 *
 * Opens the user's microphone, computes RMS of the live mic stream via
 * Web Audio AnalyserNode, and reports sustained activity above a threshold
 * to the supplied callback as `(is_speaking: bool, audio_level: number)`.
 *
 * Why we bother:
 * - MediaPipe lip-MAR is brittle (lighting, beards, partial occlusion).
 * - Audio energy is a much stronger talking signal in real testing rooms.
 * - The backend's `audio_activity` handler converts these into
 *   `lip_movement` violations with `metadata.source = 'audio'`.
 *
 * Anti-false-positive measures here:
 * - Raise threshold above keyboard / fan / mouse-click noise (RMS ~0.04).
 * - Only fire `is_speaking=true` after sustained activity for >= 800ms.
 * - Fire AT MOST ONCE per speaking burst until the user goes quiet for
 *   the cooldown window (matches backend's per-violation cooldown, so we
 *   don't spam log_violation calls that get rejected anyway).
 */
// Tightened from 0.045 — normal indoor speaking volume sits around 0.02-0.05 RMS.
// 0.025 still rejects fan / keyboard / breathing (~0.005-0.015) but catches
// real speech from a normal seated distance.
const RMS_THRESHOLD = 0.025
// A single "yes" / "I think" syllable cluster is ~400ms.
const SUSTAIN_MS = 450
// Pauses BETWEEN words ("yo... please tell me... the answer") commonly
// run 150-300ms. We don't want each word-gap to reset the sustain timer
// — otherwise long sentences with natural pauses never trigger. As long
// as the candidate goes quiet for less than this, we consider them
// "still speaking" for sustain-tracking purposes.
const PAUSE_GRACE_MS = 400
const QUIET_TO_REARM_MS = 1200

/**
 * Returns `{ status, level }` so the UI can render a mic indicator.
 *   status: 'idle' | 'requesting' | 'active' | 'denied' | 'error'
 *   level:  current normalised RMS (0..1), throttled to ~10 Hz
 */
export default function useAudioActivity({ active, onSpeaking }) {
  const handlerRef = useRef(onSpeaking)
  const [status, setStatus] = useState('idle')
  const [level, setLevel] = useState(0)

  useEffect(() => {
    handlerRef.current = onSpeaking
  }, [onSpeaking])

  useEffect(() => {
    if (!active) {
      setStatus('idle')
      return
    }
    let cancelled = false
    let audioCtx = null
    let stream = null
    let raf = 0

    const speakingSinceRef = { current: 0 }
    const lastVoicedRef = { current: 0 } // last frame where rms > threshold
    const armedRef = { current: true }
    const lastQuietRef = { current: Date.now() }
    let lastSentAt = 0
    let levelTick = 0

    async function start() {
      setStatus('requesting')
      try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      } catch (e) {
        console.error('[audio] mic permission denied / unavailable:', e?.name, e?.message)
        setStatus('denied')
        return
      }
      if (cancelled) {
        stream.getTracks().forEach((t) => t.stop())
        return
      }

      const Ctor = window.AudioContext || window.webkitAudioContext
      audioCtx = new Ctor()
      // Chromium-based browsers create AudioContexts in 'suspended' state
      // until a user gesture resumes them. Without this, the analyser
      // returns silence forever and audio detection silently does nothing.
      if (audioCtx.state === 'suspended') {
        try { await audioCtx.resume() } catch (e) {
          console.warn('[audio] could not resume AudioContext:', e?.message)
        }
      }

      const src = audioCtx.createMediaStreamSource(stream)
      const analyser = audioCtx.createAnalyser()
      analyser.fftSize = 1024
      analyser.smoothingTimeConstant = 0.6
      src.connect(analyser)
      const buf = new Float32Array(analyser.fftSize)
      setStatus('active')
      console.info(
        '[audio] mic active · ctx.state =', audioCtx.state,
        '· sampleRate =', audioCtx.sampleRate
      )

      const tick = () => {
        if (cancelled) return
        analyser.getFloatTimeDomainData(buf)
        let sum = 0
        for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i]
        const rms = Math.sqrt(sum / buf.length)
        const now = Date.now()

        // throttle React updates so we don't re-render every frame
        if (++levelTick % 6 === 0) setLevel(rms)

        const isVoiced = rms > RMS_THRESHOLD

        if (isVoiced) {
          // Start the speaking window if we weren't already in one
          if (!speakingSinceRef.current) speakingSinceRef.current = now
          lastVoicedRef.current = now
        } else if (
          speakingSinceRef.current &&
          now - lastVoicedRef.current > PAUSE_GRACE_MS
        ) {
          // We've been quiet long enough that the previous burst is over.
          // Reset the sustain window. Inter-word pauses shorter than
          // PAUSE_GRACE_MS keep the window open so a full sentence with
          // natural pauses still accumulates sustain time.
          speakingSinceRef.current = 0
        }

        // Always advance "officially quiet" timer when not voiced
        if (!isVoiced) {
          if (!armedRef.current && now - lastQuietRef.current >= QUIET_TO_REARM_MS) {
            armedRef.current = true
          }
          if (now - lastVoicedRef.current > PAUSE_GRACE_MS) {
            lastQuietRef.current = now
          }
        }

        if (
          speakingSinceRef.current &&
          armedRef.current &&
          now - speakingSinceRef.current >= SUSTAIN_MS &&
          now - lastSentAt > 1000
        ) {
          lastSentAt = now
          armedRef.current = false
          const audioLevel = Math.min(1, rms / 0.1)
          console.info('[audio] speech detected · rms =', rms.toFixed(3))
          handlerRef.current?.(true, audioLevel)
        }

        raf = requestAnimationFrame(tick)
      }
      raf = requestAnimationFrame(tick)
    }

    start()

    return () => {
      cancelled = true
      cancelAnimationFrame(raf)
      if (stream) stream.getTracks().forEach((t) => t.stop())
      if (audioCtx) audioCtx.close().catch(() => {})
    }
  }, [active])

  return { status, level }
}
