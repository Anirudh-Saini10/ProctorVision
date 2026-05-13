import { useCallback, useEffect, useRef, useState } from 'react'
import { API_URL } from '../lib/config.js'

/**
 * Connects to /ws/proctor and exposes:
 *   - status
 *   - activeSessions: array (refreshed on initial active_sessions msg + on reload())
 *   - subscribed: { session_id, candidate, code, strictness, risk } | null
 *   - latestSnapshot: { data (base64), timestamp, risk, face_detected, frame } | null
 *   - liveRisk
 *   - events: live event stream (newest first)
 *   - subscribe(sid), unsubscribe(), reload()
 */
export default function useProctorSocket() {
  const wsRef = useRef(null)
  const [status, setStatus] = useState('idle')
  const [activeSessions, setActiveSessions] = useState([])
  const [subscribed, setSubscribed] = useState(null)
  const [latestSnapshot, setLatestSnapshot] = useState(null)
  const [liveRisk, setLiveRisk] = useState(0)
  const [events, setEvents] = useState([])
  const frameCounter = useRef(0)

  const send = useCallback((obj) => {
    const ws = wsRef.current
    if (ws && ws.readyState === 1) ws.send(JSON.stringify(obj))
  }, [])

  useEffect(() => {
    const wsUrl = API_URL.replace(/^http/, 'ws') + '/ws/proctor'
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws
    setStatus('connecting')

    ws.onopen = () => setStatus('open')
    ws.onclose = () => setStatus('closed')
    ws.onerror = () => setStatus('error')

    ws.onmessage = (evt) => {
      let msg
      try {
        msg = JSON.parse(evt.data)
      } catch {
        return
      }
      switch (msg.type) {
        case 'active_sessions':
          setActiveSessions(msg.sessions || [])
          break
        case 'subscribed':
          setSubscribed({
            session_id: msg.session_id,
            candidate: msg.candidate,
            code: msg.code,
            strictness: msg.strictness,
            risk: msg.risk,
          })
          setLatestSnapshot(null)
          setEvents([])
          frameCounter.current = 0
          break
        case 'snapshot':
          frameCounter.current += 1
          setLatestSnapshot({
            data: msg.data,
            timestamp: msg.timestamp,
            risk: msg.risk,
            face_detected: msg.face_detected,
            frame: frameCounter.current,
          })
          break
        case 'risk_score':
          setLiveRisk(msg.score)
          break
        case 'violation': {
          const ts = msg.timestamp ?? Date.now()
          const stamp = new Date(ts).toLocaleTimeString()
          setEvents((prev) =>
            [
              {
                id: `${ts}-${msg.violation_type}-${prev.length}`,
                kind: msg.violation_type,
                severity: msg.severity ?? 'medium',
                detail: msg.confidence
                  ? `confidence ${msg.confidence.toFixed(2)}`
                  : '',
                stamp,
              },
              ...prev,
            ].slice(0, 60)
          )
          break
        }
        case 'session_ended':
          setSubscribed((s) =>
            s ? { ...s, ended: true, summary: msg.summary } : s
          )
          break
        default:
          break
      }
    }

    return () => ws.close()
  }, [])

  const subscribe = useCallback(
    (sid) => send({ type: 'subscribe', session_id: sid }),
    [send]
  )
  const unsubscribe = useCallback(() => send({ type: 'unsubscribe' }), [send])
  const reload = useCallback(() => send({ type: 'list' }), [send])

  return {
    status,
    activeSessions,
    subscribed,
    latestSnapshot,
    liveRisk,
    events,
    subscribe,
    unsubscribe,
    reload,
  }
}
