import { Navigate, useLocation } from 'react-router-dom'
import { useSession } from '../state/SessionContext.jsx'

/**
 * Guards student/proctor routes. If no code is set, kick to /login.
 * Optional `role` prop enforces 'student' or 'proctor'.
 */
export default function RequireSession({ role, children }) {
  const { code, role: actualRole } = useSession()
  const location = useLocation()

  if (!code) {
    return <Navigate to="/login" replace state={{ from: location }} />
  }
  if (role && actualRole !== role) {
    // role mismatch — bounce to landing
    return <Navigate to="/" replace />
  }
  return children
}
