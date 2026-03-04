import { useState, useEffect } from "react";
import { api } from "../api";

function JobRow({ job, onDelete, onRefresh }) {
  const [showPhases, setShowPhases] = useState(false);
  const pct = job.total_found > 0
    ? Math.round((job.total_scraped / job.total_found) * 100)
    : 0;

  let phaseStats = {};
  if (job.phase_stats) {
    try {
      phaseStats = typeof job.phase_stats === "string" ? JSON.parse(job.phase_stats) : job.phase_stats;
    } catch (e) {
      console.error("Parse error:", e);
    }
  }

  return (
    <>
      <tr className={showPhases ? "row-active" : ""}>
        <td style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--muted)" }}>
          {job.id.slice(0, 12)}...
        </td>
        <td><span className="badge badge-sector">{job.sector}</span></td>
        <td><span className="badge badge-region">{job.region}</span></td>
        <td style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>
          {job.date_from} → {job.date_to}
        </td>
        <td>
          <span className={`badge badge-${job.status}`}>{job.status}</span>
        </td>
        <td>
          <div style={{ minWidth: 160 }}>
            <div style={{ fontSize: 10, color: "var(--muted)", marginBottom: 8 }}>
              Discovery Pool: <b style={{ color: "var(--accent)" }}>{(job.cumulative_found || 0).toLocaleString()} URLs</b>
            </div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, marginBottom: 4 }}>
              {(job.total_scraped || 0).toLocaleString()} / {(job.total_found || 0).toLocaleString()} articles
            </div>
            {(job.status === "running" || job.status === "pending") && (
              <div className="progress-bar-track">
                <div className="progress-bar-fill" style={{ width: `${pct}%` }} />
              </div>
            )}
            <button
              className="btn btn-secondary"
              onClick={() => setShowPhases(!showPhases)}
              style={{
                padding: "2px 8px", fontSize: 9, marginTop: 12, height: "auto",
                textTransform: "none", fontWeight: 400, opacity: 0.9,
                background: "rgba(0, 229, 255, 0.05)", border: "1px solid rgba(0, 229, 255, 0.1)"
              }}
            >
              {showPhases ? "▲ Hide Tracker" : "▼ Track Phases"}
            </button>
          </div>
        </td>
        <td style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--muted)" }}>
          {job.started_at ? new Date(job.started_at).toLocaleString() : "—"}
        </td>
        <td style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--muted)" }}>
          {job.completed_at ? new Date(job.completed_at).toLocaleString() : "—"}
        </td>
        <td style={{ maxWidth: 200, fontSize: 11, color: "var(--danger)", wordBreak: "break-word" }}>
          {job.error ? job.error.slice(0, 80) : "—"}
        </td>
        <td>
          <div style={{ display: "flex", gap: 6 }}>
            <button className="btn btn-secondary" style={{ padding: "4px 10px", fontSize: 11 }}
              onClick={() => onRefresh(job.id)}>
              ↻
            </button>
            <button className="btn btn-danger" style={{ padding: "4px 10px", fontSize: 11 }}
              onClick={() => onDelete(job.id)}>
              ✕
            </button>
          </div>
        </td>
      </tr>
      {showPhases && (
        <tr style={{ background: "rgba(0,0,0,0.3)" }}>
          <td colSpan={10} style={{ padding: "16px 24px", borderBottom: "1px solid var(--border)" }}>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 24 }}>
              {Object.entries(phaseStats).length > 0 ? (
                Object.entries(phaseStats).map(([name, data]) => (
                  <div key={name} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    <div style={{ fontSize: 10, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>{name}</div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span className={`badge badge-${data.status}`} style={{ fontSize: 9 }}>{data.status}</span>
                      <span style={{ fontSize: 9, color: "var(--muted)", fontFamily: "var(--font-mono)" }}>
                        {new Date(data.updated_at).toLocaleTimeString()}
                      </span>
                    </div>
                  </div>
                ))
              ) : (
                <div style={{ fontSize: 11, color: "var(--muted)", fontStyle: "italic" }}>
                  Waiting for backend to report phase progress...
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

export default function Jobs() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);

  const loadJobs = async () => {
    try {
      const data = await api.get("/scrape/jobs");
      setJobs(data);
    } catch { }
    setLoading(false);
  };

  useEffect(() => {
    loadJobs();
    const interval = setInterval(loadJobs, 5000); // Poll every 5s
    return () => clearInterval(interval);
  }, []);

  const refreshJob = async (id) => {
    try {
      const updated = await api.get(`/scrape/job/${id}`);
      setJobs((prev) => prev.map((j) => (j.id === id ? updated : j)));
    } catch { }
  };

  const deleteJob = async (id) => {
    if (!confirm("Delete this job and all its articles?")) return;
    try {
      await api.delete(`/scrape/job/${id}`);
      setJobs((prev) => prev.filter((j) => j.id !== id));
    } catch { }
  };

  const runningJobs = jobs.filter((j) => j.status === "running" || j.status === "pending");
  const completedJobs = jobs.filter((j) => j.status === "completed");
  const failedJobs = jobs.filter((j) => ["failed", "interrupted", "partial"].includes(j.status));
  const totalArticles = jobs.reduce((sum, j) => sum + (j.total_scraped || 0), 0);

  return (
    <div>
      <div className="page-header">
        <div className="page-title">Scrape Jobs</div>
        <div className="page-subtitle">// MONITORING CENTER — AUTO-REFRESHES EVERY 5s</div>
      </div>

      <div className="stats-grid" style={{ gridTemplateColumns: "repeat(4,1fr)", marginBottom: 24 }}>
        <div className="stat-card">
          <div className="stat-label">Total Jobs</div>
          <div className="stat-value">{jobs.length}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Active</div>
          <div className="stat-value" style={{ color: runningJobs.length > 0 ? "var(--warning)" : "var(--text)" }}>
            {runningJobs.length}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Failed / Interrupted</div>
          <div className="stat-value" style={{ color: failedJobs.length > 0 ? "var(--danger)" : "var(--text)" }}>
            {failedJobs.length}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Articles Collected</div>
          <div className="stat-value">{totalArticles.toLocaleString()}</div>
        </div>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Job ID</th>
              <th>Sector</th>
              <th>Region</th>
              <th>Date Range</th>
              <th>Status</th>
              <th>Progress & Tasks</th>
              <th>Started</th>
              <th>Completed</th>
              <th>Error</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={10} style={{ textAlign: "center", padding: 40 }}>
                <div className="spinner" style={{ margin: "0 auto" }} />
              </td></tr>
            ) : jobs.length === 0 ? (
              <tr><td colSpan={10}>
                <div className="empty-state">
                  <div className="empty-state-icon">◎</div>
                  <h3>No jobs yet</h3>
                  <p>Launch your first scrape from the New Scrape page.</p>
                </div>
              </td></tr>
            ) : jobs.map((job) => (
              <JobRow key={job.id} job={job} onDelete={deleteJob} onRefresh={refreshJob} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
