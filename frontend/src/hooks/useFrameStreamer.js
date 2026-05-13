import { useEffect, useRef } from 'react'

/**
 * Captures JPEG frames from a video element at a target FPS and forwards them
 * to a callback. Uses an offscreen canvas at downscaled resolution to keep
 * payload size and CPU low.
 *
 * @param {object} opts
 * @param {() => HTMLVideoElement | null} opts.getVideo - resolver for the video element
 * @param {boolean} opts.active - whether streaming should be running
 * @param {number} opts.fps - frames per second (default 5)
 * @param {number} opts.maxWidth - downscale width (default 480)
 * @param {number} opts.quality - jpeg quality 0..1 (default 0.6)
 * @param {(base64: string, ts: number) => void} opts.onFrame - called per frame
 */
export default function useFrameStreamer({
  getVideo,
  active,
  fps = 5,
  maxWidth = 480,
  quality = 0.6,
  onFrame,
}) {
  const canvasRef = useRef(null)
  const lastSentRef = useRef(0)
  const rafRef = useRef(0)
  const handlerRef = useRef(onFrame)
  const getVideoRef = useRef(getVideo)

  useEffect(() => {
    handlerRef.current = onFrame
  }, [onFrame])

  useEffect(() => {
    getVideoRef.current = getVideo
  }, [getVideo])

  useEffect(() => {
    if (!active) return
    const interval = 1000 / fps

    const tick = (now) => {
      rafRef.current = requestAnimationFrame(tick)
      if (now - lastSentRef.current < interval) return
      const video = getVideoRef.current?.()
      if (!video) return
      if (video.readyState < 2 || video.videoWidth === 0) return
      lastSentRef.current = now

      const vw = video.videoWidth
      const vh = video.videoHeight
      const scale = Math.min(1, maxWidth / vw)
      const w = Math.round(vw * scale)
      const h = Math.round(vh * scale)

      let canvas = canvasRef.current
      if (!canvas) {
        canvas = document.createElement('canvas')
        canvasRef.current = canvas
      }
      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w
        canvas.height = h
      }
      const ctx = canvas.getContext('2d')
      ctx.drawImage(video, 0, 0, w, h)
      const dataUrl = canvas.toDataURL('image/jpeg', quality)
      const base64 = dataUrl.split(',')[1] ?? ''
      handlerRef.current?.(base64, Date.now())
    }

    rafRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(rafRef.current)
  }, [active, fps, maxWidth, quality, videoRef])
}
