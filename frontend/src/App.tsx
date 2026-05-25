import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import Chat from './pages/Chat'
import Documents from './pages/Documents'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/chat" replace />} />
        <Route path="/chat" element={<Chat />} />
        <Route path="/documents" element={<Documents />} />
        <Route path="*" element={<Navigate to="/chat" replace />} />
      </Route>
    </Routes>
  )
}
