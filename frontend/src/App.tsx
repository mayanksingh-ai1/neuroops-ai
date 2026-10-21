import { HealthStatus } from "./components/HealthStatus";
import { AnalysisResult } from "./components/AnalysisResult";
import { fetchDashboard, type DashboardData } from "./api/dashboard";
import { useEffect, useState } from "react";
import {
  Activity,
  AlertCircle,
  ArrowDownRight,
  ArrowUpRight,
  BarChart3,
  Bell,
  Bot,
  CalendarDays,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  ClipboardList,
  Download,
  FileText,
  Filter,
  LayoutDashboard,
  Menu,
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const navigation = [
  { label: "Overview", icon: LayoutDashboard },
  { label: "Complaint Analysis", icon: BarChart3 },
  { label: "AI Research", icon: Search },
  { label: "AI Agent", icon: Bot },
  { label: "LLM Evaluation", icon: ShieldCheck },
  { label: "Reports", icon: FileText },
];

function Sidebar({
  active,
  onSelect,
  open,
  onClose,
}: {
  active: string;
  onSelect: (label: string) => void;
  open: boolean;
  onClose: () => void;
}) {
  return (
    <>
      {open && (
        <button
          className="scrim"
          onClick={onClose}
          aria-label="Close navigation"
        />
      )}
      <aside className={`sidebar ${open ? "sidebar-open" : ""}`}>
        <div className="brand">
          <div className="brand-mark">
            <Activity size={20} strokeWidth={2.4} />
          </div>
          <div>
            <strong>
              neuroops<span>ai</span>
            </strong>
            <small>COMPLAINT INTELLIGENCE</small>
          </div>
          <button
            className="icon-button mobile-close"
            onClick={onClose}
            aria-label="Close menu"
          >
            <X size={18} />
          </button>
        </div>
        <div className="workspace">
          <div className="workspace-avatar">N</div>
          <div>
            <b>Northstar Commerce</b>
            <small>Demo workspace</small>
          </div>
          <ChevronDown size={15} />
        </div>
        <div className="nav-caption">WORKSPACE</div>
        <nav aria-label="Main navigation">
          {navigation.map(({ label, icon: Icon }) => (
            <button
              key={label}
              onClick={() => {
                onSelect(label);
                onClose();
              }}
              className={`nav-item ${active === label ? "active" : ""}`}
            >
              <Icon size={18} />
              <span>{label}</span>
              {label === "AI Agent" && <i className="nav-dot" />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="usage-card">
            <div className="usage-head">
              <span>Sample plan usage</span>
              <span>68%</span>
            </div>
            <div className="usage-track">
              <i />
            </div>
            <small>6,820 of 10,000 credits used</small>
            <div className="usage-link">
              Illustrative plan <ChevronRight size={13} />
            </div>
          </div>
          <button
            disabled
            title="Not available in Phase 1"
            className="nav-item"
          >
            <Settings2 size={18} />
            <span>Settings</span>
          </button>
          <button
            disabled
            title="Not available in Phase 1"
            className="nav-item"
          >
            <CircleHelp size={18} />
            <span>Help & support</span>
          </button>
          <div className="user-profile">
            <div className="user-avatar">AM</div>
            <div>
              <b>Alex Morgan</b>
              <small>Product analyst</small>
            </div>
            <MoreDots />
          </div>
        </div>
      </aside>
    </>
  );
}

function MoreDots() {
  return (
    <span className="more-dots" aria-hidden="true">
      •••
    </span>
  );
}

function MetricCard({
  title,
  value,
  delta,
  sub,
  icon: Icon,
  color,
  negative = false,
}: {
  title: string;
  value: string;
  delta: string;
  sub: string;
  icon: typeof Activity;
  color: string;
  negative?: boolean;
}) {
  return (
    <article className="metric-card">
      <div className="metric-top">
        <span>{title}</span>
        <span className={`metric-icon ${color}`}>
          <Icon size={17} />
        </span>
      </div>
      <div className="metric-value">{value}</div>
      <div className="metric-foot">
        <span className={`delta ${negative ? "down" : ""}`}>
          {negative ? <ArrowDownRight size={14} /> : <ArrowUpRight size={14} />}
          {delta}
        </span>
        <span>{sub}</span>
      </div>
    </article>
  );
}

function App() {
  const [active, setActive] = useState("Overview");
  const [menuOpen, setMenuOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [data, setData] = useState<DashboardData | null>(null);
  const [dataState, setDataState] = useState<"loading" | "ready" | "empty" | "error">("loading");
  const [reloadToken, setReloadToken] = useState(0);
  useEffect(() => {
    let cancelled = false;
    setDataState("loading");
    fetchDashboard(query)
      .then((result) => {
        if (cancelled) return;
        setData(result);
        setDataState(result.total ? "ready" : "empty");
      })
      .catch(() => !cancelled && setDataState("error"));
    return () => { cancelled = true; };
  }, [query, reloadToken]);
  const visibleComplaints = data?.complaints ?? [];
  const totalComplaints = data?.status.total ?? 0;
  const resolved = data?.status.counts.resolved ?? 0;
  const resolutionRate = totalComplaints ? `${((resolved / totalComplaints) * 100).toFixed(1)}%` : "—";
  const categories = data?.categories ?? [];
  const trend = data?.trend ?? [];
  const categoryMaximum = Math.max(...categories.map((category) => category.count), 1);

  return (
    <div className="app-shell">
      <Sidebar
        active={active}
        onSelect={setActive}
        open={menuOpen}
        onClose={() => setMenuOpen(false)}
      />
      <main className="main-area">
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="icon-button menu-button"
              onClick={() => setMenuOpen(true)}
              aria-label="Open navigation"
            >
              <Menu size={20} />
            </button>
            <div className="breadcrumb">
              Workspace <ChevronRight size={14} /> <b>{active}</b>
            </div>
          </div>
          <div className="topbar-actions">
            <button
              disabled
              title="Not available in Phase 1"
              className="date-filter"
            >
              <CalendarDays size={15} />
              <span>Last 7 days</span>
              <ChevronDown size={14} />
            </button>
            <button
              disabled
              title="Not available in Phase 1"
              className="icon-button notification"
              aria-label="Notifications"
            >
              <Bell size={18} />
              <i />
            </button>
            <div className="top-avatar">AM</div>
          </div>
        </header>
        <div className="content-wrap">
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                <span className="live-dot" /> OVERVIEW{" "}
                <span className="mock-label">DATABASE DATA</span>
              </div>
              <h1>
                Good morning, Alex <span>✦</span>
              </h1>
              <p>Here’s what’s happening with your customer feedback.</p>
            </div>
            <button className="export-button" onClick={() => window.print()}>
              <Download size={16} /> Print dashboard
            </button>
          </div>
          {dataState !== "ready" && <div className="notice">
            <div className="notice-icon">
              <AlertCircle size={17} />
            </div>
            <div>
              <b>{dataState === "loading" ? "Loading complaint data" : dataState === "error" ? "Cannot load complaint data" : "No complaint data yet"}</b>
              <span>
                {dataState === "loading" && "Fetching current records from the NeuroOps API."}
                {dataState === "error" && "Start the API and PostgreSQL, apply the migration, then retry."}
                {dataState === "empty" && "Import a validated CSV to populate this dashboard."}
              </span>
            </div>
            {dataState !== "loading" && <button className="export-button" onClick={() => setReloadToken((value) => value + 1)}>Retry</button>}
          </div>}
          {active === "Complaint Analysis" ? (
            <section className="panel p-6" aria-label="Stored complaint intelligence">
              <h2>Complaint intelligence</h2>
              <p className="mt-3 text-slate-300">
                AI suggestions require human review. Priority follows configured rules.
                An operator can classify complaints through the API.
              </p>
              <button className="export-button mt-5" disabled={dataState === "loading"}
                onClick={() => setReloadToken((value) => value + 1)}>
                Refresh analysis
              </button>
              <div className="table-wrap mt-5">
                <table>
                  <thead><tr><th>COMPLAINT</th><th>ORIGINAL CATEGORY / PRIORITY</th><th>AI ANALYSIS</th></tr></thead>
                  <tbody>{visibleComplaints.map((complaint) => (
                    <tr key={complaint.complaint_id}>
                      <td><div className="complaint-title">{complaint.title}</div>
                        <div className="complaint-id">{complaint.complaint_id}</div></td>
                      <td>{complaint.category} / {complaint.priority}</td>
                      <td><AnalysisResult analysis={complaint.analysis} /></td>
                    </tr>
                  ))}</tbody>
                </table>
                {dataState !== "loading" && visibleComplaints.length === 0 &&
                  <p className="empty-state">No complaints to analyze.</p>}
              </div>
              <p className="mt-3 text-slate-300">Showing the latest attempt for the first {visibleComplaints.length} matching complaints.</p>
            </section>
          ) : active !== "Overview" ? (
            <section className="panel py-12 text-center">
              <h2 className="text-xl font-semibold">{active}</h2>
              <p className="mt-3 text-slate-300">
                Planned feature — not implemented in Phase 3.
              </p>
              <button
                className="export-button mx-auto mt-5"
                onClick={() => setActive("Overview")}
              >
                Back to overview
              </button>
            </section>
          ) : (
            <>
              <section
                className="metrics-grid"
                aria-label="Complaint metrics"
              >
                <MetricCard
                  title="Total complaints"
                  value={String(totalComplaints)}
                  delta="Stored records"
                  sub="from PostgreSQL"
                  icon={ClipboardList}
                  color="violet"
                />
                <MetricCard
                  title="Resolution rate"
                  value={resolutionRate}
                  delta={`${resolved} resolved`}
                  sub="of stored complaints"
                  icon={ShieldCheck}
                  color="green"
                />
                <MetricCard
                  title="Open complaints"
                  value={String(data?.status.counts.open ?? 0)}
                  delta={`${data?.status.counts.in_progress ?? 0} in progress`}
                  sub="current status"
                  icon={Activity}
                  color="blue"
                  negative
                />
                <MetricCard
                  title="Categories"
                  value={String(categories.length)}
                  delta="Grouped by issue"
                  sub="current records"
                  icon={Sparkles}
                  color="amber"
                />
              </section>
              <section className="analytics-grid">
                <article className="panel trend-panel">
                  <div className="panel-header">
                    <div>
                      <h2>Complaint volume</h2>
                      <p>
                        Daily complaints received{" "}
                        <span className="mock-inline">· DATABASE</span>
                      </p>
                    </div>
                    <button
                      disabled
                      title="Not available in Phase 1"
                      className="select-button"
                    >
                      This week <ChevronDown size={14} />
                    </button>
                  </div>
                  <div className="chart-summary">
                    <strong>{trend.reduce((sum, row) => sum + row.complaints, 0)}</strong>
                    <span>complaints in selected range</span>
                  </div>
                  <div className="trend-chart">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={trend}
                        margin={{ top: 9, right: 4, bottom: 0, left: -20 }}
                      >
                        <CartesianGrid
                          vertical={false}
                          stroke="#222b40"
                          strokeDasharray="3 5"
                        />
                        <XAxis
                          dataKey="day"
                          axisLine={false}
                          tickLine={false}
                          tick={{ fill: "#737e96", fontSize: 11 }}
                          dy={8}
                        />
                        <YAxis
                          axisLine={false}
                          tickLine={false}
                          tick={{ fill: "#737e96", fontSize: 11 }}
                        />
                        <Tooltip
                          cursor={{ fill: "rgba(129,140,248,.07)" }}
                          contentStyle={{
                            background: "#111a2c",
                            border: "1px solid #27324a",
                            borderRadius: 8,
                            color: "#e5e7eb",
                            fontSize: 12,
                          }}
                        />
                        <Bar
                          isAnimationActive={false}
                          dataKey="complaints"
                          fill="#818cf8"
                          radius={[5, 5, 0, 0]}
                          maxBarSize={34}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </article>
                <article className="panel category-panel">
                  <div className="panel-header">
                    <div>
                      <h2>Top complaint categories</h2>
                      <p>
                        By volume <span className="mock-inline">· DATABASE</span>
                      </p>
                    </div>
                    <button
                      disabled
                      title="Not available in Phase 1"
                      className="icon-button subtle"
                      aria-label="More category options"
                    >
                      <MoreDots />
                    </button>
                  </div>
                  <div className="category-list">
                    {categories.map((category) => (
                      <div className="category-row" key={category.name}>
                        <div className="category-label">
                          <i style={{ background: category.color }} />
                          <span>{category.name}</span>
                          <b>{category.count}</b>
                        </div>
                        <div className="category-track">
                          <i
                            style={{
                              width: `${(category.count / categoryMaximum) * 100}%`,
                              background: category.color,
                            }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                  <button
                    className="text-link"
                    onClick={() => setActive("Complaint Analysis")}
                  >
                    View all categories <ChevronRight size={14} />
                  </button>
                </article>
              </section>
              <section className="panel activity-panel">
                <div className="panel-header activity-header">
                  <div>
                    <h2>Recent complaints</h2>
                    <p>
                      Latest imported customer feedback{" "}
                      <span className="mock-inline">· DATABASE</span>
                    </p>
                  </div>
                  <div className="table-actions">
                    <label className="search-field">
                      <Search size={15} />
                      <input
                        aria-label="Search complaints"
                        placeholder="Search complaints..."
                        value={query}
                        onChange={(event) => setQuery(event.target.value)}
                      />
                    </label>
                    <button
                      disabled
                      title="Not available in Phase 1"
                      className="filter-button"
                    >
                      <Filter size={15} />
                      <span>Filter</span>
                    </button>
                  </div>
                </div>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>COMPLAINT</th>
                        <th>CATEGORY</th>
                        <th>CHANNEL</th>
                        <th>RECEIVED</th>
                        <th>ORIGINAL PRIORITY</th>
                        <th>AI ANALYSIS</th>
                        <th aria-label="Open complaint" />
                      </tr>
                    </thead>
                    <tbody>
                        {visibleComplaints.map((complaint) => (
                        <tr key={complaint.complaint_id}>
                          <td>
                            <div className="complaint-title">
                              {complaint.title}
                            </div>
                            <div className="complaint-id">{complaint.complaint_id}</div>
                          </td>
                          <td>
                            <span className="category-chip">
                              {complaint.category}
                            </span>
                          </td>
                          <td>
                            <span className="channel-label">
                              {complaint.channel}
                            </span>
                          </td>
                          <td className="time-label">{complaint.received_date}</td>
                          <td>
                            <span className={`priority ${complaint.priority === "high" ? "red" : complaint.priority === "medium" ? "amber" : "slate"}`}>
                              <i />
                              {complaint.priority}
                            </span>
                          </td>
                          <td><AnalysisResult analysis={complaint.analysis} /></td>
                          <td>
                            <button
                              disabled
                              title="Not available in Phase 1"
                              className="row-arrow"
                              aria-label={`Open ${complaint.complaint_id}`}
                            >
                              <ChevronRight size={16} />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {visibleComplaints.length === 0 && (
                    <div className="empty-state">
                      <Search size={20} />
                      <b>No complaints found</b>
                      <span>Try another search term.</span>
                    </div>
                  )}
                </div>
                <div className="table-footer">
                  <span>
                    Showing <b>{visibleComplaints.length}</b> of {data?.total ?? 0} stored records
                  </span>
                  <div>
                    <button
                      disabled
                      title="Not available in Phase 1"
                      className="page-button"
                      aria-label="Previous page"
                    >
                      <ChevronLeft size={15} />
                    </button>
                    <button
                      disabled
                      title="Not available in Phase 1"
                      className="page-number"
                    >
                      1
                    </button>
                    <button
                      disabled
                      title="Not available in Phase 1"
                      className="page-button"
                      aria-label="Next page"
                    >
                      <ChevronRight size={15} />
                    </button>
                  </div>
                </div>
              </section>
              <section className="panel mt-4">
                <h2 className="text-sm font-semibold">
                  Import status
                </h2>
                <p className="mt-2 text-xs text-slate-300">
                  Dashboard values are calculated from imported PostgreSQL complaint records.
                </p>
                <ul className="mt-4 space-y-3 text-sm text-slate-300">
                  <li>
                    CSV validation accepts required columns and reports invalid rows.
                  </li>
                  <li>Duplicate complaint IDs are skipped without overwriting stored data.</li>
                  <li>AI analysis features are still not implemented.</li>
                </ul>
              </section>
            </>
          )}
          <HealthStatus />
          <footer className="page-footer">
            <span>
              <i /> Database-backed dashboard · Imported records only
            </span>
            <span>
              NeuroOps AI <b>·</b> Phase 3
            </span>
          </footer>
        </div>
      </main>
    </div>
  );
}

export default App;
