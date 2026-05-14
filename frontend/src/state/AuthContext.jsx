/**
 * Proctor authentication context.
 *
 * Wraps JWT storage + the `me` round-trip on mount. We deliberately
 * don't auto-redirect from this context; the route guard does that
 * so we can keep the context usable on public pages too (e.g. the
 * landing page can show "Logged in as Foo" without forcing redirect).
 */

import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { authApi, ApiError, getToken, setToken } from '../lib/api.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [proctor, setProctor] = useState(null)
  // 'unknown' until we've checked the token; 'guest' or 'authed' after.
  const [status, setStatus] = useState(getToken() ? 'unknown' : 'guest')

  // On mount, if we have a token, hydrate the proctor profile.
  useEffect(() => {
    let cancelled = false
    if (!getToken()) return
    authApi
      .me()
      .then((p) => {
        if (cancelled) return
        setProctor(p)
        setStatus('authed')
      })
      .catch(() => {
        if (cancelled) return
        // Bad / expired token — wipe it and act as guest.
        setToken(null)
        setProctor(null)
        setStatus('guest')
      })
    return () => {
      cancelled = true
    }
  }, [])

  const login = useCallback(async (email, password) => {
    const res = await authApi.login({ email, password })
    setToken(res.access_token)
    setProctor(res.proctor)
    setStatus('authed')
    return res.proctor
  }, [])

  const register = useCallback(async (email, name, password) => {
    const res = await authApi.register({ email, name, password })
    setToken(res.access_token)
    setProctor(res.proctor)
    setStatus('authed')
    return res.proctor
  }, [])

  const logout = useCallback(() => {
    setToken(null)
    setProctor(null)
    setStatus('guest')
  }, [])

  return (
    <AuthContext.Provider value={{ proctor, status, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be inside AuthProvider')
  return ctx
}

export { ApiError }
