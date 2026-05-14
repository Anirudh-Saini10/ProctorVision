/**
 * Thin REST client. Handles base URL, JWT auth header, and JSON
 * error unpacking so callers don't have to.
 *
 * The token is read out of localStorage at call time (not closed-over)
 * so a fresh login is picked up by callers immediately without
 * re-mounting React trees.
 */

import { API_URL } from './config.js'

const TOKEN_KEY = 'pv.token'

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    /* ignore */
  }
}

export class ApiError extends Error {
  constructor(message, status, body) {
    super(message)
    this.status = status
    this.body = body
  }
}

async function request(path, { method = 'GET', body, auth = false, headers = {} } = {}) {
  const finalHeaders = { Accept: 'application/json', ...headers }
  if (body !== undefined) finalHeaders['Content-Type'] = 'application/json'
  if (auth) {
    const t = getToken()
    if (t) finalHeaders.Authorization = `Bearer ${t}`
  }
  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers: finalHeaders,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  const text = await res.text()
  let parsed = null
  if (text) {
    try {
      parsed = JSON.parse(text)
    } catch {
      parsed = text
    }
  }
  if (!res.ok) {
    const detail =
      (parsed && parsed.detail) ||
      (typeof parsed === 'string' ? parsed : null) ||
      `HTTP ${res.status}`
    throw new ApiError(detail, res.status, parsed)
  }
  return parsed
}

// ── auth ────────────────────────────────────────────────────────────

export const authApi = {
  register: (body) => request('/api/auth/register', { method: 'POST', body }),
  login: (body) => request('/api/auth/login', { method: 'POST', body }),
  me: () => request('/api/auth/me', { auth: true }),
}

// ── exams (proctor) ─────────────────────────────────────────────────

export const examsApi = {
  list: () => request('/api/exams', { auth: true }),
  get: (id) => request(`/api/exams/${id}`, { auth: true }),
  create: (body) => request('/api/exams', { method: 'POST', body, auth: true }),
  update: (id, body) =>
    request(`/api/exams/${id}`, { method: 'PATCH', body, auth: true }),
  replaceQuestions: (id, questions) =>
    request(`/api/exams/${id}/questions`, { method: 'PUT', body: questions, auth: true }),
  remove: (id) => request(`/api/exams/${id}`, { method: 'DELETE', auth: true }),
  attempts: (id) => request(`/api/exams/${id}/attempts`, { auth: true }),
}

// ── exams (public, candidate-facing) ────────────────────────────────

export const publicApi = {
  examByCode: (code) => request(`/api/exams/by-code/${encodeURIComponent(code)}`),
}

// ── attempts (candidate) ────────────────────────────────────────────

export const attemptsApi = {
  start: (body) => request('/api/attempts', { method: 'POST', body }),
  submit: (id, body) =>
    request(`/api/attempts/${id}/submit`, { method: 'POST', body }),
  result: (id) => request(`/api/attempts/${id}/result`),
}
