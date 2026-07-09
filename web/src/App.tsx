import { useEffect } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Sidebar } from './components/Sidebar';
import { useAppStore } from './store/useChatStore';

export function App() {
  const isAuthenticated = useAppStore((s) => s.isAuthenticated);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/login', { replace: true });
      return;
    }
    if (location.pathname === '/') {
      navigate('/chat', { replace: true });
    }
  }, [isAuthenticated, navigate, location.pathname]);

  if (!isAuthenticated) return null;

  return (
    <div className="flex h-screen bg-slate-900 text-slate-100">
      <Sidebar />
      <main className="flex-1 overflow-hidden">
        <Outlet />
      </main>
    </div>
  );
}
