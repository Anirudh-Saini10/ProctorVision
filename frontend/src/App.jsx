import { Routes, Route } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import { useLocation } from 'react-router-dom'
import Landing from './pages/Landing.jsx'
import Login from './pages/Login.jsx'
import StudentLobby from './pages/StudentLobby.jsx'
import Session from './pages/Session.jsx'
import Report from './pages/Report.jsx'
import RequireSession from './components/RequireSession.jsx'

function App() {
  const location = useLocation()
  return (
    <AnimatePresence mode="wait">
      <Routes location={location} key={location.pathname}>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />

        {/* Student */}
        <Route
          path="/student"
          element={
            <RequireSession role="student">
              <StudentLobby />
            </RequireSession>
          }
        />

        {/* placeholders kept for now; will be replaced in next phase */}
        <Route path="/session" element={<Session />} />
        <Route path="/report" element={<Report />} />
      </Routes>
    </AnimatePresence>
  )
}

export default App
