import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../state/AuthContext.jsx'

/**
 * Guard for proctor routes — requires a valid JWT.
 * While the AuthProvider is still resolving (`status === 'unknown'`)
 * we render a tiny placeholder rather than flashing the login page.
 */
export default function RequireAuth({ children }) {
  const { status } = useAuth()
  const location = useLocation()

  if (status === 'unknown') {
    return (
      <div className="grid min-h-screen place-items-center font-mono text-[11px] uppercase tracking-eyebrow text-text-muted">
        loading…
      </div>
    )
  }
  if (status !== 'authed') {
    return (
      <Navigate
        to="/proctor/login"
        replace
        state={{ from: location.pathname }}
      />
    )
  }
  return children
}
