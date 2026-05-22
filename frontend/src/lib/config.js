/**
 * Runtime configuration. Values come from Vite env vars at build time.
 * Default to local dev backend when not provided.
 */

const HTTP =
  import.meta.env.VITE_API_URL?.replace(/\/$/, '') ?? ''

// Derive WS URL from HTTP URL (http -> ws, https -> wss).
// When HTTP is empty (same-origin deploy) derive from browser location
// at runtime. WebSocket() requires an absolute URL — relative paths
// like "/ws" throw a DOMException.
function _deriveWsBase() {
  if (HTTP) return HTTP.replace(/^http/, 'ws')
  if (typeof window !== 'undefined') {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${proto}//${window.location.host}`
  }
  return ''
}

export const API_URL = HTTP
export const WS_URL = `${_deriveWsBase()}/ws`
export const WS_BASE = _deriveWsBase
export const REPORT_URL = (sessionId) => `${HTTP}/api/report/${sessionId}`

// Frame stream FPS for the candidate's webcam feed.
//
// Localhost can comfortably process 5fps with full MediaPipe + YOLO,
// but HF Spaces' free-tier CPU caps out around 1-2fps. The backend
// coalesces dropped frames either way, but streaming faster than the
// backend can keep up just wastes bandwidth on the slow deployment.
//
// Override with VITE_STREAM_FPS in .env / .env.production.
// Default 5 (good for local dev); HF Spaces .env.production sets it to 3.
const _parsedFps = Number.parseInt(import.meta.env.VITE_STREAM_FPS ?? '', 10)
export const STREAM_FPS = Number.isFinite(_parsedFps) && _parsedFps > 0
  ? _parsedFps
  : 5
