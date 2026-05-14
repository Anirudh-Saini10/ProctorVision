/**
 * Runtime configuration. Values come from Vite env vars at build time.
 * Default to local dev backend when not provided.
 */

const HTTP =
  import.meta.env.VITE_API_URL?.replace(/\/$/, '') ?? ''

// Derive WS URL from HTTP URL (http -> ws, https -> wss).
// When HTTP is empty (same-origin deploy) just use relative /ws.
const WS = HTTP ? HTTP.replace(/^http/, 'ws') : ''

export const API_URL = HTTP
export const WS_URL = `${WS}/ws`
export const REPORT_URL = (sessionId) => `${HTTP}/api/report/${sessionId}`
