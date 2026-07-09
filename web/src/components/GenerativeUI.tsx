/* Generative UI renderer — dynamically renders LLM-generated UI components.
 *
 * Catches `ui_component` events from the SSE stream and maps type strings
 * to pre-built, styled React components (Recharts, Radix, etc.).
 * The LLM calls render_component via <<render_component{"type":"...","props":{...}}>>
 * markers in the stream, and this renderer safely instantiates the UI.
 */
import { useMemo } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, PieChart, Pie, Cell,
} from 'recharts';

// ── Component Registry ───────────────────────────────────────

interface ComponentProps {
  data?: Record<string, unknown>[];
  x_key?: string;
  y_key?: string;
  columns?: string[];
  label?: string;
  value?: number | string;
  [key: string]: unknown;
}

const CHART_COLORS = ['#10b981', '#6366f1', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4'];

function BarChartComponent({ data, x_key, y_key }: ComponentProps) {
  if (!data || !x_key || !y_key) return null;
  return (
    <div className="w-full h-64 bg-slate-800 rounded-xl p-4 border border-slate-700 my-3" role="img" aria-label="Bar chart">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis dataKey={x_key} stroke="#94a3b8" fontSize={12} />
          <YAxis stroke="#94a3b8" fontSize={12} />
          <Tooltip
            contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px', color: '#e2e8f0' }}
          />
          <Bar dataKey={y_key} fill="#10b981" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function DataGridComponent({ data, columns }: ComponentProps) {
  if (!data || !columns) return null;
  return (
    <div className="w-full overflow-x-auto bg-slate-800 rounded-xl border border-slate-700 my-3" role="table" aria-label="Data grid">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-700">
            {columns.map((col: string) => (
              <th key={col} className="px-4 py-2 text-left text-slate-400 font-medium">{col}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr key={i} className="border-b border-slate-700/50 hover:bg-slate-700/30">
              {columns.map((col: string) => (
                <td key={col} className="px-4 py-2 text-slate-200">{String(row[col] ?? '')}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MetricCardComponent({ label, value }: ComponentProps) {
  return (
    <div className="inline-block bg-slate-800 rounded-xl border border-slate-700 p-4 my-2 min-w-32" role="status" aria-label={label}>
      <p className="text-xs text-slate-400 uppercase tracking-wide">{label}</p>
      <p className="text-2xl font-bold text-emerald-400 mt-1">{value}</p>
    </div>
  );
}

function LineChartComponent({ data, x_key, y_key }: ComponentProps) {
  if (!data || !x_key || !y_key) return null;
  return (
    <div className="w-full h-64 bg-slate-800 rounded-xl p-4 border border-slate-700 my-3" role="img" aria-label="Line chart">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis dataKey={x_key} stroke="#94a3b8" fontSize={12} />
          <YAxis stroke="#94a3b8" fontSize={12} />
          <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px', color: '#e2e8f0' }} />
          <Line type="monotone" dataKey={y_key} stroke="#6366f1" strokeWidth={2} dot={{ fill: '#6366f1' }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function PieChartComponent({ data, x_key, y_key }: ComponentProps) {
  if (!data || !x_key || !y_key) return null;
  return (
    <div className="w-full h-64 bg-slate-800 rounded-xl p-4 border border-slate-700 my-3" role="img" aria-label="Pie chart">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie data={data} dataKey={y_key} nameKey={x_key} cx="50%" cy="50%" outerRadius={80} label>
            {data.map((_, i) => (
              <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
            ))}
          </Pie>
          <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px', color: '#e2e8f0' }} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── Component Registry ───────────────────────────────────────

const COMPONENT_MAP: Record<string, React.FC<ComponentProps>> = {
  bar_chart: BarChartComponent,
  line_chart: LineChartComponent,
  pie_chart: PieChartComponent,
  data_grid: DataGridComponent,
  metric_card: MetricCardComponent,
};

// ── Props ────────────────────────────────────────────────────

interface GenerativeUIProps {
  type: string;
  props: ComponentProps;
}

export function GenerativeUI({ type, props }: GenerativeUIProps) {
  const Component = useMemo(() => COMPONENT_MAP[type], [type]);

  if (!Component) {
    return (
      <div className="bg-slate-800 rounded-xl p-3 my-2 border border-amber-700/50 text-amber-400 text-xs">
        Unknown component: <code className="text-slate-400">{type}</code>
      </div>
    );
  }

  return <Component {...props} />;
}

// ── Component Types Export ───────────────────────────────────

export type { ComponentProps };
export { COMPONENT_MAP };
