import { useCallback, useEffect, useRef, useState } from 'react'
import { WS_BASE } from '../lib/config.js'

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
  // Persisted gallery of violation evidence frames. Newest first.
  // Each entry: { id, violation_type, data, timestamp, risk }
  const [evidenceSnapshots, setEvidenceSnapshots] = useState([])
  const frameCounter = useRef(0)

  const send = useCallback((obj) => {
    const ws = wsRef.current
    if (ws && ws.readyState === 1) ws.send(JSON.stringify(obj))
  }, [])

  useEffect(() => {
    const wsUrl = WS_BASE() + '/ws/proctor'
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
            ended: Boolean(msg.ended),
            ended_reason: msg.ended_reason || null,
          })
          setLatestSnapshot(null)
          setEvents([])
          setEvidenceSnapshots([])
          frameCounter.current = 0
          // Seed the live risk gauge from the subscribed payload so
          // ended-session replays don't start at zero. (For live
          // sessions a `risk_score` message will quickly overwrite
          // this anyway.)
          setLiveRisk(msg.risk ?? 0)
          break
        case 'snapshot':
        case 'evidence_snapshot':
          // Both produce the same on-screen update — the only
          // difference is that `evidence_snapshot` is sent immediately
          // when a violation fires (showing the proctor exactly what
          // tripped the alert), while `snapshot` is the periodic
          // ~1fps refresh. We bump the frame counter on both so the
          // "frame NNNN" indicator advances naturally.
          frameCounter.current += 1
          setLatestSnapshot({
            data: msg.data,
            timestamp: msg.timestamp,
            risk: msg.risk,
            face_detected: msg.face_detected,
            frame: frameCounter.current,
            evidence_for: msg.violation_type || null,
          })
          // Persist evidence snapshots in their own gallery so the
          // proctor can review every violation frame after the fact,
          // not just the most recent one. Plain `snapshot` (periodic
          // ~1fps refresh) is intentionally NOT persisted — only
          // violation-attached frames go into the evidence wall.
          if (msg.type === 'evidence_snapshot') {
            setEvidenceSnapshots((prev) => {
              // De-duplicate by violation_id — the backend replays
              // archived snapshots on (re)subscribe, so without this
              // a refresh would multiply them.
              const id = msg.violation_id
              if (id && prev.some((s) => s.id === id)) return prev
              return [
                {
                  id: id ?? `${msg.timestamp}-${msg.violation_type}`,
                  violation_id: id,
                  violation_type: msg.violation_type,
                  data: msg.data,
                  timestamp: msg.timestamp,
                  risk: msg.risk,
                },
                ...prev,
              ].slice(0, 60)
            })
          }
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
  const manualFlag = useCallback(
    (note) => send({ type: 'manual_flag', note: note ?? '' }),
    [send]
  )
  const forceEnd = useCallback(
    (reason) => send({ type: 'force_end', reason: reason ?? 'Ended by proctor' }),
    [send]
  )

  return {
    status,
    activeSessions,
    subscribed,
    latestSnapshot,
    liveRisk,
    events,
    evidenceSnapshots,
    subscribe,
    unsubscribe,
    reload,
    manualFlag,
    forceEnd,
  }
}
