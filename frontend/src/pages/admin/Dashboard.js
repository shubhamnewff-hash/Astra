import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import api from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  MessageSquare, Users, TrendingUp, TrendingDown,
  ThumbsUp, ThumbsDown, BookOpen, HelpCircle, Calendar
} from "lucide-react";
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from "recharts";

const STAT_CONFIG = [
  { key: "total_questions", label: "Total Questions", icon: MessageSquare, color: "#3B82F6", link: "/admin/conversations" },
  { key: "active_users", label: "Active Users", icon: Users, color: "#10B981", link: "/admin/users" },
  { key: "resolution_rate", label: "Resolution Rate", icon: TrendingUp, color: "#10B981", suffix: "%", link: "/admin/conversations" },
  { key: "escalation_rate", label: "Escalation Rate", icon: TrendingDown, color: "#F59E0B", suffix: "%", link: "/admin/conversations" },
  { key: "helpful_pct", label: "Helpful %", icon: ThumbsUp, color: "#10B981", suffix: "%", link: "/admin/feedback?filter=helpful" },
  { key: "not_helpful_pct", label: "Not Helpful %", icon: ThumbsDown, color: "#EF4444", suffix: "%", link: "/admin/feedback?filter=not_helpful" },
  { key: "total_knowledge_items", label: "Knowledge Items", icon: BookOpen, color: "#8B5CF6", link: "/admin/knowledge" },
  { key: "unanswered_questions", label: "Unanswered Qs", icon: HelpCircle, color: "#FF6B00", link: "/admin/gap-analysis" },
];

const PIE_COLORS = ["#10B981", "#EF4444"];

const PRESETS = [
  { label: "Today", key: "today" },
  { label: "7 Days", key: "7d" },
  { label: "30 Days", key: "30d" },
  { label: "This Month", key: "month" },
  { label: "This Year", key: "year" },
  { label: "All Time", key: "all" },
];

function getPresetRange(key) {
  const now = new Date();
  const todayStr = now.toISOString().split("T")[0];
  switch (key) {
    case "today": return { from: todayStr, to: todayStr };
    case "7d": { const d = new Date(now); d.setDate(d.getDate() - 7); return { from: d.toISOString().split("T")[0], to: todayStr }; }
    case "30d": { const d = new Date(now); d.setDate(d.getDate() - 30); return { from: d.toISOString().split("T")[0], to: todayStr }; }
    case "month": return { from: `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-01`, to: todayStr };
    case "year": return { from: `${now.getFullYear()}-01-01`, to: todayStr };
    case "all": return { from: "", to: "" };
    default: return { from: "", to: "" };
  }
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="px-3 py-2 rounded-lg shadow-lg border border-[#E2E8F0]" style={{ background: '#0A101D' }}>
      <p className="text-xs text-slate-400 mb-1">{label}</p>
      {payload.map((p, i) => (
        <p key={i} className="text-xs font-semibold" style={{ color: p.color }}>{p.name}: {p.value}</p>
      ))}
    </div>
  );
};

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [charts, setCharts] = useState(null);
  const [loading, setLoading] = useState(true);
  const [preset, setPreset] = useState("30d");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [showCustom, setShowCustom] = useState(false);

  const fetchData = useCallback(async (from, to) => {
    setLoading(true);
    const params = {};
    if (from) params.date_from = from;
    if (to) params.date_to = to;
    try {
      const [s, c] = await Promise.all([
        api.get("/admin/analytics", { params }),
        api.get("/admin/analytics/charts", { params }),
      ]);
      setStats(s.data);
      setCharts(c.data);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => {
    const { from, to } = getPresetRange(preset);
    setDateFrom(from);
    setDateTo(to);
    fetchData(from, to);
  }, [preset, fetchData]);

  const applyCustom = () => {
    fetchData(dateFrom, dateTo);
    setPreset("custom");
  };

  const periodLabel = preset === "custom"
    ? `${dateFrom || "Start"} → ${dateTo || "Now"}`
    : PRESETS.find(p => p.key === preset)?.label || "30 Days";

  if (loading && !stats) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight" style={{ fontFamily: 'Outfit', color: '#0A101D' }}>Dashboard</h1>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <Card key={i} className="border border-[#E2E8F0]"><CardContent className="p-5"><div className="h-16 animate-pulse bg-[#F1F5F9] rounded" /></CardContent></Card>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="admin-dashboard">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight" style={{ fontFamily: 'Outfit', color: '#0A101D' }}>Dashboard</h1>
          <p className="text-sm mt-1" style={{ color: '#64748B' }}>
            Showing data for: <span className="font-semibold text-[#0A101D]">{periodLabel}</span>
          </p>
        </div>

        {/* Date Filter Controls */}
        <div className="flex flex-wrap items-center gap-2">
          {PRESETS.map(({ label, key }) => (
            <Button key={key} variant={preset === key ? "default" : "outline"} size="sm"
              className={preset === key ? "bg-[#FF6B00] text-white hover:bg-[#E55E00]" : "text-[#64748B]"}
              onClick={() => { setPreset(key); setShowCustom(false); }}
              data-testid={`filter-${key}`}>
              {label}
            </Button>
          ))}
          <Button variant={showCustom ? "default" : "outline"} size="sm"
            className={showCustom ? "bg-[#FF6B00] text-white" : "text-[#64748B]"}
            onClick={() => setShowCustom(!showCustom)}>
            <Calendar className="h-3.5 w-3.5 mr-1" /> Custom
          </Button>
        </div>
      </div>

      {showCustom && (
        <Card className="border border-[#E2E8F0] bg-white">
          <CardContent className="p-4 flex flex-wrap items-end gap-3">
            <div>
              <label className="text-xs font-medium text-[#64748B] block mb-1">From</label>
              <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className="w-40" data-testid="date-from" />
            </div>
            <div>
              <label className="text-xs font-medium text-[#64748B] block mb-1">To</label>
              <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className="w-40" data-testid="date-to" />
            </div>
            <Button onClick={applyCustom} size="sm" style={{ background: '#FF6B00' }} className="text-white" data-testid="apply-custom-filter">
              Apply
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Stat Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 stagger-children">
        {STAT_CONFIG.map(({ key, label, icon: Icon, color, suffix, link }) => (
          <Link key={key} to={link} className="block focus:outline-none focus:ring-2 focus:ring-[#FF6B00] focus:ring-offset-2 rounded-lg" data-testid={`stat-${key}`}>
            <Card className="animate-fade-in-up border border-[#E2E8F0] hover:border-[#FF6B00] hover:shadow-lg hover:-translate-y-1 transition-all duration-200 bg-white cursor-pointer h-full">
              <CardContent className="p-5">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-xs font-bold uppercase tracking-[0.15em] mb-2" style={{ color: '#64748B' }}>{label}</p>
                    <p className="text-3xl font-bold" style={{ fontFamily: 'Outfit', color: '#0A101D' }}>
                      {stats?.[key] ?? 0}{suffix || ""}
                    </p>
                  </div>
                  <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: `${color}15` }}>
                    <Icon className="w-5 h-5" style={{ color }} />
                  </div>
                </div>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="border border-[#E2E8F0] bg-white">
          <CardHeader>
            <CardTitle className="text-base" style={{ fontFamily: 'Outfit' }}>Questions Over Time</CardTitle>
          </CardHeader>
          <CardContent>
            {charts?.daily_questions?.length > 0 ? (
              <ResponsiveContainer width="100%" height={250}>
                <AreaChart data={charts.daily_questions}>
                  <defs>
                    <linearGradient id="colorQ" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#FF6B00" stopOpacity={0.2} />
                      <stop offset="95%" stopColor="#FF6B00" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                  <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#64748B' }} tickFormatter={(v) => v.slice(5)} />
                  <YAxis tick={{ fontSize: 11, fill: '#64748B' }} />
                  <Tooltip content={<CustomTooltip />} />
                  <Area type="monotone" dataKey="questions" stroke="#FF6B00" fill="url(#colorQ)" strokeWidth={2} name="Questions" />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[250px] flex items-center justify-center text-sm" style={{ color: '#64748B' }}>No data for this period</div>
            )}
          </CardContent>
        </Card>

        <Card className="border border-[#E2E8F0] bg-white">
          <CardHeader>
            <CardTitle className="text-base" style={{ fontFamily: 'Outfit' }}>Feedback Over Time</CardTitle>
          </CardHeader>
          <CardContent>
            {charts?.daily_feedback?.length > 0 ? (
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={charts.daily_feedback}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                  <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#64748B' }} tickFormatter={(v) => v.slice(5)} />
                  <YAxis tick={{ fontSize: 11, fill: '#64748B' }} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend />
                  <Bar dataKey="helpful" fill="#10B981" radius={[4, 4, 0, 0]} name="Helpful" />
                  <Bar dataKey="not_helpful" fill="#EF4444" radius={[4, 4, 0, 0]} name="Not Helpful" />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[250px] flex items-center justify-center text-sm" style={{ color: '#64748B' }}>No feedback data for this period</div>
            )}
          </CardContent>
        </Card>

        <Card className="border border-[#E2E8F0] bg-white">
          <CardHeader>
            <CardTitle className="text-base" style={{ fontFamily: 'Outfit' }}>Feedback Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            {(charts?.feedback_pie?.[0]?.value > 0 || charts?.feedback_pie?.[1]?.value > 0) ? (
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie data={charts.feedback_pie} cx="50%" cy="50%" outerRadius={90} innerRadius={50}
                    dataKey="value" label={({ name, value }) => `${name}: ${value}`} labelLine={false}>
                    {charts.feedback_pie.map((_, i) => (
                      <Cell key={i} fill={PIE_COLORS[i]} />
                    ))}
                  </Pie>
                  <Tooltip />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[250px] flex items-center justify-center text-sm" style={{ color: '#64748B' }}>No feedback data yet</div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="border border-[#E2E8F0] bg-white">
          <CardContent className="p-5">
            <h3 className="text-sm font-semibold mb-3" style={{ fontFamily: 'Outfit', color: '#0A101D' }}>Knowledge Base</h3>
            <div className="space-y-2">
              <div className="flex justify-between"><span className="text-sm" style={{ color: '#64748B' }}>Modules</span><span className="text-sm font-semibold">{stats?.total_modules ?? 0}</span></div>
              <div className="flex justify-between"><span className="text-sm" style={{ color: '#64748B' }}>Knowledge Items</span><span className="text-sm font-semibold">{stats?.total_knowledge_items ?? 0}</span></div>
              <div className="flex justify-between"><span className="text-sm" style={{ color: '#64748B' }}>Conversations</span><span className="text-sm font-semibold">{stats?.total_conversations ?? 0}</span></div>
            </div>
          </CardContent>
        </Card>
        <Link to="/admin/feedback" className="block">
          <Card className="border border-[#E2E8F0] bg-white hover:border-[#FF6B00] hover:shadow-md transition-all cursor-pointer h-full">
            <CardContent className="p-5">
              <h3 className="text-sm font-semibold mb-3" style={{ fontFamily: 'Outfit', color: '#0A101D' }}>Feedback</h3>
              <div className="space-y-2">
                <div className="flex justify-between"><span className="text-sm" style={{ color: '#64748B' }}>Total</span><span className="text-sm font-semibold">{stats?.total_feedback ?? 0}</span></div>
                <div className="flex justify-between"><span className="text-sm" style={{ color: '#64748B' }}>Helpful</span><span className="text-sm font-semibold text-[#10B981]">{stats?.helpful_count ?? 0}</span></div>
                <div className="flex justify-between"><span className="text-sm" style={{ color: '#64748B' }}>Not Helpful</span><span className="text-sm font-semibold text-[#EF4444]">{stats?.not_helpful_count ?? 0}</span></div>
              </div>
            </CardContent>
          </Card>
        </Link>
      </div>
    </div>
  );
}
