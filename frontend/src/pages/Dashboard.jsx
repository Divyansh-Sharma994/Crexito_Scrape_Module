import { useEffect, useState } from "react";
import { api } from "../api";

export default function Dashboard({ onNavigate }) {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [enriching, setEnriching] = useState(false);
  const [enrichMsg, setEnrichMsg] = useState(null);

  useEffect(() => {
    api.get("/articles/stats/summary")
      .then(setStats)
      .catch(() => { })
      .finally(() => setLoading(false));
  }, []);

  const maxSector = stats?.by_sector?.[0]?.count || 1;
  const maxRegion = stats?.by_region?.[0]?.count || 1;

  const handleEnrich = async () => {
    setEnriching(true);
    setEnrichMsg(null);
    try {
      const res = await api.post("/scrape/enrich?concurrency=35");
      setEnrichMsg(`✓ ${res.message}`);
    } catch (e) {
      setEnrichMsg(`⚠ ${e.message}`);
    } finally {
      setEnriching(false);
    }
  };

  return (
    <div>
      <div className="page-header">
        <div className="page-title">Intelligence Overview</div>
        <div className="page-subtitle">// NEXUS GLOBAL NEWS SCRAPER — COMMAND CENTER</div>
      </div>

      <div className="stats-grid" style={{ gridTemplateColumns: "repeat(5, 1fr)" }}>
        <div className="stat-card">
          <div className="stat-label">Total Articles</div>
          <div className="stat-value">{loading ? "—" : (stats?.total_articles ?? 0).toLocaleString()}</div>
          <div className="stat-sub">In database</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Body Coverage</div>
          <div className="stat-value" style={{ color: (stats?.body_coverage_pct ?? 0) > 70 ? "var(--success)" : "var(--warning)" }}>
            {loading ? "—" : `${stats?.body_coverage_pct ?? 0}%`}
          </div>
          <div className="stat-sub">{loading ? "—" : `${(stats?.articles_with_body ?? 0).toLocaleString()} with full text`}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Sectors Tracked</div>
          <div className="stat-value">{loading ? "—" : stats?.by_sector?.length ?? 0}</div>
          <div className="stat-sub">Active sectors</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Regions Covered</div>
          <div className="stat-value">{loading ? "—" : stats?.by_region?.length ?? 0}</div>
          <div className="stat-sub">Geographic coverage</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Last Scraped</div>
          <div className="stat-value" style={{ fontSize: 18, paddingTop: 8 }}>
            {loading ? "—" : stats?.last_scraped
              ? new Date(stats.last_scraped).toLocaleDateString()
              : "Never"}
          </div>
          <div className="stat-sub">
            {stats?.last_scraped
              ? new Date(stats.last_scraped).toLocaleTimeString()
              : "—"}
          </div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 24 }}>
        <div className="card">
          <div className="card-title">Articles by Sector</div>
          {loading ? <div className="spinner" /> : (
            <div className="bar-chart">
              {stats?.by_sector?.slice(0, 8).map((s) => (
                <div className="bar-row" key={s.sector}>
                  <div className="bar-label">{s.sector}</div>
                  <div className="bar-outer">
                    <div className="bar-inner" style={{ width: `${(s.count / maxSector) * 100}%` }} />
                  </div>
                  <div className="bar-count">{s.count.toLocaleString()}</div>
                </div>
              ))}
              {!stats?.by_sector?.length && (
                <div className="empty-state" style={{ padding: "20px 0" }}>
                  <p>No data yet. Start a scrape job.</p>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="card">
          <div className="card-title">Articles by Region</div>
          {loading ? <div className="spinner" /> : (
            <div className="bar-chart">
              {stats?.by_region?.slice(0, 8).map((r) => (
                <div className="bar-row" key={r.region}>
                  <div className="bar-label">{r.region}</div>
                  <div className="bar-outer">
                    <div className="bar-inner"
                      style={{
                        width: `${(r.count / maxRegion) * 100}%`,
                        background: "linear-gradient(90deg, #7c3aed, #00e5ff)"
                      }} />
                  </div>
                  <div className="bar-count">{r.count.toLocaleString()}</div>
                </div>
              ))}
              {!stats?.by_region?.length && (
                <div className="empty-state" style={{ padding: "20px 0" }}>
                  <p>No data yet. Start a scrape job.</p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {enrichMsg && (
        <div className={`alert ${enrichMsg.startsWith("✓") ? "alert-success" : "alert-error"}`}>
          {enrichMsg}
        </div>
      )}

      <div className="card">
        <div className="card-title">Quick Actions</div>
        <div style={{ display: "flex", gap: 12 }}>
          <button className="btn btn-primary" onClick={() => onNavigate("scrape")}>
            ⊕ New Scrape Job
          </button>
          <button className="btn btn-secondary" onClick={() => onNavigate("articles")}>
            ≡ Browse Articles
          </button>
          <button className="btn btn-secondary" onClick={() => onNavigate("jobs")}>
            ◎ View Jobs
          </button>
          <button className="btn btn-secondary" onClick={handleEnrich} disabled={enriching}>
            {enriching ? <><div className="spinner" /> Running...</> : "↻ Enrich Missing Bodies"}
          </button>
        </div>
      </div>
    </div>
  );
}
