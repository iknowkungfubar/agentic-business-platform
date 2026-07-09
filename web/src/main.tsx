import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { App } from './App';
import { AuthScreen } from './components/AuthScreen';
import { Dashboard } from './components/Dashboard';
import { ChatArea } from './components/ChatArea';
import { ProtectedRoute } from './components/ProtectedRoute';
import './index.css';

import './i18n/config';
import { ErrorBoundary } from './components/ErrorBoundary';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<AuthScreen />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <App />
              </ProtectedRoute>
            }
          >
            <Route index element={<Navigate to="/chat" replace />} />
            <Route path="chat" element={<ChatArea />} />
            <Route path="chat/:conversationId" element={<ChatArea />} />
            <Route path="admin/dashboard" element={<Dashboard />} />
            <Route path="admin/agents" element={<div className="p-6 text-slate-300">Agent Management</div>} />
            <Route path="admin/scan" element={<div className="p-6 text-slate-300">MCP Scanner</div>} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ErrorBoundary>
  </StrictMode>,
);
