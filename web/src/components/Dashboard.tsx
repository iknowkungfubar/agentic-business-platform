import { useState, useEffect } from 'react';
import { useAppStore } from '../store/useChatStore';
import { adminApi } from '../api/client';
import { Bot, Shield, FileText, Activity } from 'lucide-react';

export function Dashboard() {
  const agents = useAppStore((s) => s.agents);
  const setAgents = useAppStore((s) => s.setAgents);
  const [policyCount, setPolicyCount] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      adminApi.listAgents().then((r) => setAgents(r.items)).catch(() => {}),
      adminApi.listPolicies().then((r) => setPolicyCount(r.total)).catch(() => {}),
    ]).finally(() => setLoading(false));
  }, [setAgents]);

  const healthyCount = agents.filter((a) => a.status === 'healthy').length;

  const stats = [
    { label: 'Agents', value: agents.length, icon: Bot, color: 'text-blue-400' },
    { label: 'Healthy', value: healthyCount, icon: Activity, color: 'text-emerald-400' },
    { label: 'Policies', value: policyCount, icon: Shield, color: 'text-purple-400' },
    { label: 'Scans', value: '—', icon: FileText, color: 'text-amber-400' },
  ];

  return (
    <div className="h-full overflow-y-auto">
      <div className="p-6">
        <h1 className="text-2xl font-bold mb-6">Platform Dashboard</h1>

        {loading ? (
          <div className="flex items-center justify-center h-64">
            <p className="text-slate-500 animate-pulse">Loading dashboard...</p>
          </div>
        ) : (
          <>
            {/* Stats */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
              {stats.map((stat) => {
                const Icon = stat.icon;
                return (
                  <div key={stat.label} className="bg-slate-800 border border-slate-700 rounded-xl p-4">
                    <div className="flex items-center gap-3">
                      <Icon className={stat.color} size={24} />
                      <div>
                        <p className="text-2xl font-bold">{stat.value}</p>
                        <p className="text-xs text-slate-400">{stat.label}</p>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Agent List */}
            <div className="bg-slate-800 border border-slate-700 rounded-xl p-4">
              <h2 className="text-lg font-semibold mb-4">Registered Agents</h2>
              {agents.length === 0 ? (
                <p className="text-slate-500 text-sm">No agents registered.</p>
              ) : (
                <div className="space-y-2">
                  {agents.map((agent) => (
                    <div
                      key={agent.id}
                      className="flex items-center justify-between p-3 bg-slate-700/50 rounded-lg"
                    >
                      <div>
                        <p className="text-sm font-medium">{agent.name}</p>
                        <p className="text-xs text-slate-400">{agent.provider}</p>
                      </div>
                      <span
                        className={`text-xs px-2 py-1 rounded-full ${
                          agent.status === 'healthy'
                            ? 'bg-emerald-900/50 text-emerald-300'
                            : agent.status === 'unreachable'
                              ? 'bg-red-900/50 text-red-300'
                              : 'bg-amber-900/50 text-amber-300'
                        }`}
                      >
                        ● {agent.status}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
