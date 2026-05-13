import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react'

/**
 * Self-contained webcam component. Mirrored video, optional overlay slot,
 * minimal UI chrome. Releases the stream on unmount.
 *
 * Exposes the underlying <video> element via ref.current.video for callers
 * that need to capture frames (frame streamer).
 */
const WebcamFeed = forwardRef(function WebcamFeed(
  { className = '', mirrored = true, children, onReady, onError },
  ref
) {
  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const [state, setState] = useState('init') // init | streaming | error

  useImperativeHandle(ref, () => ({
    get video() {
      return videoRef.current
    },
    get stream() {
      return streamRef.current
    },
  }))

  useEffect(() => {
    let cancelled = false
    async function start() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { width: { ideal: 640 }, height: { ideal: 480 } },
          audio: false,
        })
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop())
          return
        }
        streamRef.current = stream
        if (videoRef.current) {
          videoRef.current.srcObject = stream
          await videoRef.current.play().catch(() => {})
        }
        setState('streaming')
        onReady?.(stream)
      } catch (err) {
        setState('error')
        onError?.(err)
      }
    }
    start()
    return () => {
      cancelled = true
      streamRef.current?.getTracks().forEach((t) => t.stop())
      streamRef.current = null
    }
  }, [onReady, onError])

  return (
    <div className={`relative overflow-hidden bg-surface-1 ${className}`}>
      <video
        ref={videoRef}
        autoPlay
        muted
        playsInline
        className={`h-full w-full object-cover ${mirrored ? '-scale-x-100' : ''}`}
      />
      {state === 'init' && (
        <div className="absolute inset-0 grid place-items-center font-mono text-[10px] uppercase tracking-eyebrow text-text-muted">
          requesting camera…
        </div>
      )}
      {state === 'error' && (
        <div className="absolute inset-0 grid place-items-center px-4 text-center font-mono text-[10px] uppercase tracking-eyebrow text-risk-high">
          camera unavailable
        </div>
      )}
      {children}
    </div>
  )
})

export default WebcamFeed
