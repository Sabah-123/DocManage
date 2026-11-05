import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import './index.css'

import AppLayout   from './components/layout/AppLayout'
import LoginPage   from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import ChatPage    from './pages/ChatPage'
import DocumentsPage from './pages/DocumentsPage'
import ProfilePage from './pages/ProfilePage'
import UploadPage from './pages/UploadPage'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<AppLayout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard"  element={<DashboardPage />} />
          <Route path="chat"       element={<ChatPage />} />
          <Route path="documents"  element={<DocumentsPage />} />
          <Route path="profile"    element={<ProfilePage />} />
          <Route path="upload"     element={<UploadPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
)
