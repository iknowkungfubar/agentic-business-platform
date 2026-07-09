import { useNavigate, useLocation } from 'react-router-dom';
import { useAppStore } from '../store/useChatStore';
import {
  MessageSquare,
  LayoutDashboard,
  Bot,
  Shield,
  LogOut,
} from 'lucide-react';

const navItems = [
  { path: '/chat', label: 'Chat', icon: MessageSquare },
  { path: '/admin/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/admin/agents', label: 'Agents', icon: Bot },
  { path: '/admin/scan', label: 'MCP Scanner', icon: Shield },
];

export function Sidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const logout = useAppStore((s) => s.logout);
  const sidebarOpen = useAppStore((s) => s.sidebarOpen);
  const user = useAppStore((s) => s.user);

  return (
    <aside
      className={`${
        sidebarOpen ? 'w-64' : 'w-16'
      } bg-slate-800 border-r border-slate-700 flex flex-col transition-all duration-200`}
    >
      {/* Logo */}
      <div className="h-16 flex items-center px-4 border-b border-slate-700">
        <h1 className={`font-bold text-emerald-400 ${!sidebarOpen && 'hidden'}`}>
          TurinTech
        </h1>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-4 space-y-1 px-2">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = location.pathname.startsWith(item.path);
          return (
            <button
              key={item.path}
              onClick={() => navigate(item.path)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                isActive
                  ? 'bg-emerald-600/20 text-emerald-400'
                  : 'text-slate-400 hover:bg-slate-700 hover:text-slate-200'
              }`}
            >
              <Icon size={20} />
              {sidebarOpen && <span>{item.label}</span>}
            </button>
          );
        })}
      </nav>

      {/* User info + logout */}
      <div className="border-t border-slate-700 p-4">
        {sidebarOpen && user && (
          <p className="text-xs text-slate-500 truncate mb-2">{user.email}</p>
        )}
        <button
          onClick={logout}
          className="w-full flex items-center gap-3 px-3 py-2 text-sm text-slate-400 hover:text-red-400 rounded-lg hover:bg-slate-700 transition-colors"
        >
          <LogOut size={20} />
          {sidebarOpen && <span>Logout</span>}
        </button>
      </div>
    </aside>
  );
}
