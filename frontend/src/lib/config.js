/**
 * Runtime configuration. Values come from Vite env vars at build time.
 * Default to local dev backend when not provided.
 */

const HTTP =
  import.meta.env.VITE_API_URL?.replace(/\/$/, '') ?? 'http://localhost:8000'

// Derive WS URL from HTTP URL (http -> ws, https -> wss)
const WS = HTTP.replace(/^http/, 'ws')

export const API_URL = HTTP
export const WS_URL = `${WS}/ws`
export const REPORT_URL = (sessionId) => `${HTTP}/api/report/${sessionId}`
