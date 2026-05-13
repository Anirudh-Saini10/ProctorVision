/**
 * Static mock data for the proctor views. Stable across reloads.
 * Will be replaced by real backend data once the snapshot WS pipe is wired.
 */

const NAMES = [
  'Aanya Mehta',
  'Rahul Singh',
  'Priya Verma',
  'Karan Kapoor',
  'Sneha Iyer',
  'Vikram Joshi',
  'Meera Nair',
  'Arjun Khanna',
  'Tanvi Desai',
  'Ishaan Bose',
]

function pick(arr, seed) {
  return arr[seed % arr.length]
}

function pseudoRisk(seed) {
  const base = (seed * 17 + 7) % 90
  return base
}

function code(seed) {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
  let out = ''
  let s = seed * 9301 + 49297
  for (let i = 0; i < 6; i++) {
    s = (s * 9301 + 49297) % 233280
    out += chars[s % chars.length]
  }
  return out
}

const STATUSES = ['live', 'live', 'live', 'live', 'live', 'live', 'ended', 'ended', 'ended', 'ended']
const EVENTS = [
  'gaze drift',
  'head turn',
  'object: phone',
  'lip motion',
  'multi-face',
  'absent face',
  'occlusion',
]

export function getSessions() {
  return NAMES.map((name, i) => {
    const status = STATUSES[i]
    const risk = pseudoRisk(i + 1)
    const lastEvent = pick(EVENTS, i + 3)
    const lastEventAgo = `${(i % 5) + 1}s ago`
    return {
      id: code(i + 1),
      candidate: name,
      status,
      risk,
      lastEvent,
      lastEventAgo,
      durationMin: status === 'ended' ? 45 + (i * 3) % 30 : 12 + (i * 7) % 30,
      strictness: ['Lenient', 'Moderate', 'Strict'][i % 3],
    }
  })
}

export function getSession(id) {
  return getSessions().find((s) => s.id === id) ?? null
}

/**
 * Synthesize an event timeline with timestamps for replay/timeline charts.
 */
export function getEvents(id, count = 22) {
  const seed = id.charCodeAt(0) + id.charCodeAt(id.length - 1)
  const out = []
  for (let i = 0; i < count; i++) {
    const t = i * 47 + (seed % 30)
    const sevRoll = (seed + i * 13) % 100
    const severity = sevRoll > 85 ? 'high' : sevRoll > 55 ? 'medium' : 'low'
    out.push({
      id: `${id}-e${i}`,
      atSec: t,
      severity,
      kind: pick(EVENTS, seed + i),
      detail: `confidence ${(0.55 + ((seed + i) % 40) / 100).toFixed(2)}`,
    })
  }
  return out
}
