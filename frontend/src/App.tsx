import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import LoginPage from './pages/LoginPage'
import SchoolsPage from './pages/SchoolsPage'
import SchoolPage from './pages/SchoolPage'
import SetupPage from './pages/SetupPage'
import AssignmentsPage from './pages/AssignmentsPage'
import SchedulesPage from './pages/SchedulesPage'
import ConstraintsPage from './pages/ConstraintsPage'
import ScheduleViewPage from './pages/ScheduleViewPage'
import SpecialEventsPage from './pages/SpecialEventsPage'
import ElectiveBandsPage from './pages/ElectiveBandsPage'
import AccessTokensPage from './pages/AccessTokensPage'

function ProtectedLayout() {
  const token = localStorage.getItem('token')
  return token ? <Layout /> : <Navigate to="/login" replace />
}

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<ProtectedLayout />}>
        <Route index element={<SchoolsPage />} />
        <Route path="schools/:schoolId" element={<SchoolPage />} />
        <Route path="schools/:schoolId/setup" element={<SetupPage />} />
        <Route path="schools/:schoolId/assignments" element={<AssignmentsPage />} />
        <Route path="schools/:schoolId/schedules" element={<SchedulesPage />} />
        <Route path="schools/:schoolId/schedules/:scheduleId/view" element={<ScheduleViewPage />} />
        <Route path="schools/:schoolId/constraints" element={<ConstraintsPage />} />
        <Route path="schools/:schoolId/special-events" element={<SpecialEventsPage />} />
        <Route path="schools/:schoolId/electives" element={<ElectiveBandsPage />} />
        <Route path="tokens" element={<AccessTokensPage />} />
      </Route>
    </Routes>
  )
}

export default App
