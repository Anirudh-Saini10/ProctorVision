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
