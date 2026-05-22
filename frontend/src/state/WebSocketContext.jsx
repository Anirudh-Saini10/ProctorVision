import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { WS_URL } from '../lib/config.js'

/**
 * Single shared WebSocket connection for the proctoring session.
 * Mounted at app root; persists across page navigations (calibrate -> exam -> done).
 *
 * State surface for consumers:
 *   - status: 'idle' | 'connecting' | 'open' | 'closed' | 'error'
 *   - sessionId: backend session UUID (set after `session_started`)
 *   - calibration: { state, progress, remaining, ...} | null
 *   - calibrationComplete: bool
 *   - riskScore: number 0-100
 *   - violations: array of violation events received this session
 *   - lastFrameInfo: { frame_number, face_detected, face_count } | null
 *   - summary: final summary dict | null (set on session_ended)
 *
 * Methods:
 *   - connect()
 *   - startSession()
 *   - sendFrame(base64Jpeg, timestampMs)
 *   - sendTabSwitch(direction)
 *   - endSession(): Promise<summary>
 *   - reset(): clears local state for a fresh run
 *   - close(): close socket
 */
const WebSocketCtx = createContext(null)

const initialState = {
  status: 'idle',
  sessionId: null,
  calibration: null,
  calibrationComplete: false,
  riskScore: 0,
  violations: [],
  lastFrameInfo: null,
  summary: null,
}

export function WebSocketProvider({ children }) {
  const wsRef = useRef(null)
  const endResolversRef = useRef([])
  const [status, setStatus] = useState('idle')
  const [sessionId, setSessionId] = useState(null)
  const [calibration, setCalibration] = useState(null)
  const [calibrationComplete, setCalibrationComplete] = useState(false)
  const [riskScore, setRiskScore] = useState(0)
  const [violations, setViolations] = useState([])
  const [lastFrameInfo, setLastFrameInfo] = useState(null)
  const [summary, setSummary] = useState(null)
  // Set when the proctor force-ends the candidate's session — the
  // Exam page watches this and navigates to /student/done so the
  // candidate sees the same end-of-session experience as if they
  // ended it themselves.
  const [forceEndedReason, setForceEndedReason] = useState(null)
  const [errorMessage, setErrorMessage] = useState(null)

  const reset = useCallback(() => {
    setSessionId(null)
    setCalibration(null)
    setCalibrationComplete(false)
    setRiskScore(0)
    setViolations([])
    setLastFrameInfo(null)
    setSummary(null)
    setForceEndedReason(null)
    setErrorMessage(null)
  }, [])

  const connect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState <= 1) return wsRef.current
    const ws = new WebSocket(WS_URL)
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
        case 'session_started':
          setSessionId(msg.session_id)
          break
        case 'calibration_progress':
          setCalibration(msg)
          break
        case 'calibration_complete':
          setCalibrationComplete(true)
          break
        case 'violation':
          setViolations((v) => [
            { ...msg, id: `${msg.timestamp}-${msg.violation_type}-${v.length}` },
            ...v,
          ].slice(0, 200))
          break
        case 'risk_score':
          setRiskScore(msg.score)
          break
        case 'frame_processed':
          // Keep snake_case keys — Exam.jsx and other consumers read
          // `face_detected` directly off this object. Renaming to
          // camelCase here broke the "no face" banner detection and
          // made the recording header permanently show "NO FACE".
          setLastFrameInfo({
            frame_number: msg.frame_number,
            face_detected: msg.face_detected,
            face_count: msg.face_count,
          })
          if (msg.diag && msg.frame_number % 30 === 0) {
            // eslint-disable-next-line no-console
            console.log('[WS diag]', JSON.stringify(msg.diag))
          }
          break
        case 'session_ended':
          setSummary(msg.summary)
          // resolve any pending endSession() promises
          while (endResolversRef.current.length) {
            const r = endResolversRef.current.shift()
            r(msg.summary)
          }
          break
        case 'force_end':
          // Proctor pushed the End Session button. Mirror what the
          // candidate would do themselves: dispatch session_end so the
          // backend returns the final summary, then surface the reason
          // for the Exam page to redirect to /student/done.
          setForceEndedReason(msg.reason || 'Ended by proctor')
          if (wsRef.current && wsRef.current.readyState === 1) {
            wsRef.current.send(JSON.stringify({ type: 'session_end' }))
          }
          break
        case 'error':
          setErrorMessage(msg.message || 'Unknown server error')
          if (msg.detail) {
            // eslint-disable-next-line no-console
            console.warn('[WS] Server error detail:', msg.detail)
          }
          break
        default:
          break
      }
    }

    return ws
  }, [])

  const send = useCallback((obj) => {
    const ws = wsRef.current
    if (ws && ws.readyState === 1) {
      ws.send(JSON.stringify(obj))
    }
  }, [])

  const startSession = useCallback((meta = {}) => {
    reset()
    const ws = connect()
    const dispatch = () =>
      send({
        type: 'session_start',
        candidate_name: meta.candidate_name ?? null,
        code: meta.code ?? null,
        strictness: meta.strictness ?? null,
        // Optional: link this WS-bound proctoring session to the
        // persisted Attempt row created by /api/attempts. Backend
        // writes the integrity summary back onto that row at
        // session_end so the proctor's exam-attempts view shows the
        // final score next to the candidate's name.
        attempt_id: meta.attempt_id ?? null,
      })
    if (ws.readyState === 1) dispatch()
    else ws.addEventListener('open', dispatch, { once: true })
  }, [connect, send, reset])

  const sendFrame = useCallback(
    (base64, timestamp) => {
      send({ type: 'frame', data: base64, timestamp: timestamp ?? Date.now() })
    },
    [send]
  )

  const sendTabSwitch = useCallback(
    (direction = 'blur') => {
      send({ type: 'tab_switch', direction, timestamp: Date.now() })
    },
    [send]
  )

  const sendAudioActivity = useCallback(
    (isSpeaking, audioLevel = 0) => {
      send({
        type: 'audio_activity',
        is_speaking: isSpeaking,
        audio_level: audioLevel,
        timestamp: Date.now(),
      })
    },
    [send]
  )

  const endSession = useCallback(() => {
    return new Promise((resolve) => {
      endResolversRef.current.push(resolve)
      send({ type: 'session_end' })
      // safety timeout — resolve with whatever we have after 4s
      setTimeout(() => {
        if (endResolversRef.current.includes(resolve)) {
          endResolversRef.current = endResolversRef.current.filter(
            (r) => r !== resolve
          )
          resolve(null)
        }
      }, 4000)
    })
  }, [send])

  const close = useCallback(() => {
    wsRef.current?.close()
    wsRef.current = null
  }, [])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      wsRef.current?.close()
    }
  }, [])

  const value = useMemo(
    () => ({
      status,
      sessionId,
      calibration,
      calibrationComplete,
      riskScore,
      violations,
      lastFrameInfo,
      summary,
      forceEndedReason,
      errorMessage,
      connect,
      startSession,
      sendFrame,
      sendTabSwitch,
      sendAudioActivity,
      endSession,
      reset,
      close,
    }),
    [
      status,
      sessionId,
      calibration,
      calibrationComplete,
      riskScore,
      violations,
      lastFrameInfo,
      summary,
      forceEndedReason,
      errorMessage,
      connect,
      startSession,
      sendFrame,
      sendTabSwitch,
      sendAudioActivity,
      endSession,
      reset,
      close,
    ]
  )

  return <WebSocketCtx.Provider value={value}>{children}</WebSocketCtx.Provider>
}

export function useWS() {
  const ctx = useContext(WebSocketCtx)
  if (!ctx) throw new Error('useWS must be used within WebSocketProvider')
  return ctx
}
