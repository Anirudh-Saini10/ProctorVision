import { Routes, Route, Navigate } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import { useLocation } from 'react-router-dom'
import Landing from './pages/Landing.jsx'
import Login from './pages/Login.jsx'
import Join from './pages/Join.jsx'
import StudentLobby from './pages/StudentLobby.jsx'
import Calibrate from './pages/Calibrate.jsx'
import Exam from './pages/Exam.jsx'
import Done from './pages/Done.jsx'
import ProctorLogin from './pages/ProctorLogin.jsx'
import ProctorExams from './pages/ProctorExams.jsx'
import ProctorExamEditor from './pages/ProctorExamEditor.jsx'
import ProctorDashboard from './pages/ProctorDashboard.jsx'
import ProctorMonitor from './pages/ProctorMonitor.jsx'
import ProctorRules from './pages/ProctorRules.jsx'
import Report from './pages/Report.jsx'
import RequireSession from './components/RequireSession.jsx'
import RequireAuth from './components/RequireAuth.jsx'

function App() {
  const location = useLocation()
  return (
    <AnimatePresence mode="wait">
      <Routes location={location} key={location.pathname}>
        <Route path="/" element={<Landing />} />
        {/* Legacy demo entry — kept for backwards compatibility with
           any old links / docs. New product flow lives at /join (for
           candidates) and /proctor/login (for proctors). */}
        <Route path="/login" element={<Login />} />
        <Route path="/join" element={<Join />} />
        <Route path="/proctor/login" element={<ProctorLogin />} />

        {/* Proctor — real product (auth-gated) */}
        <Route
          path="/proctor/exams"
          element={
            <RequireAuth>
              <ProctorExams />
            </RequireAuth>
          }
        />
        <Route
          path="/proctor/exams/new"
          element={
            <RequireAuth>
              <ProctorExamEditor />
            </RequireAuth>
          }
        />
        <Route
          path="/proctor/exams/:id"
          element={
            <RequireAuth>
              <ProctorExamEditor />
            </RequireAuth>
          }
        />
        {/* `/proctor` now redirects to the exams list — that's the
           proctor's "home". The live console lives at /proctor/sessions
           (formerly /proctor for the demo). */}
        <Route
          path="/proctor"
          element={<Navigate to="/proctor/exams" replace />}
        />
        <Route
          path="/proctor/sessions"
          element={
            <RequireAuth>
              <ProctorDashboard />
            </RequireAuth>
          }
        />

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

        {/* Proctor — auxiliary (still auth-gated) */}
        <Route
          path="/proctor/session/:id"
          element={
            <RequireAuth>
              <ProctorMonitor />
            </RequireAuth>
          }
        />
        <Route
          path="/proctor/rules"
          element={
            <RequireAuth>
              <ProctorRules />
            </RequireAuth>
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
