import { Routes, Route } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import { useLocation } from 'react-router-dom'
import Landing from './pages/Landing.jsx'
import Login from './pages/Login.jsx'
import StudentLobby from './pages/StudentLobby.jsx'
import Calibrate from './pages/Calibrate.jsx'
import Exam from './pages/Exam.jsx'
import Done from './pages/Done.jsx'
import ProctorDashboard from './pages/ProctorDashboard.jsx'
import ProctorMonitor from './pages/ProctorMonitor.jsx'
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
        <Route
          path="/student/calibrate"
          element={
            <RequireSession role="student">
              <Calibrate />
            </RequireSession>
          }
        />
        <Route
          path="/student/exam"
          element={
            <RequireSession role="student">
              <Exam />
            </RequireSession>
          }
        />
        <Route
          path="/student/done"
          element={
            <RequireSession role="student">
              <Done />
            </RequireSession>
          }
        />

        {/* Proctor */}
        <Route
          path="/proctor"
          element={
            <RequireSession role="proctor">
              <ProctorDashboard />
            </RequireSession>
          }
        />
        <Route
          path="/proctor/session/:id"
          element={
            <RequireSession role="proctor">
              <ProctorMonitor />
            </RequireSession>
          }
        />

        {/* Reports — accessible to anyone with the link */}
        <Route path="/report" element={<Report />} />
        <Route path="/report/:id" element={<Report />} />
      </Routes>
    </AnimatePresence>
  )
}

export default App
