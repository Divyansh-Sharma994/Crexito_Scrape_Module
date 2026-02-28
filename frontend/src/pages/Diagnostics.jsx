import { useState, useEffect } from "react";
import { api } from "../api";

export default function Diagnostics() {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);

    const fetchDiagnostics = async () => {
        try {
            const res = await api.get("/diagnostics/health");
            setData(res);
        } catch (e) {
            console.error(e);
            // Simulate offline state
            setData({
                overall: "offline",
                components: {
                    database: { status: "offline", message: "Cannot reach backend API" },
                    groq_api: { status: "offline", message: "Cannot reach backend API" },
                    playwright: { status: "offline", message: "Cannot reach backend API" },
                    jobs: { status: "offline", message: "Cannot reach backend API" }
                },
                recent_log_errors: []
            });
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchDiagnostics();
        const interval = setInterval(fetchDiagnostics, 15000); // Polling every 15s
        return () => clearInterval(interval);
    }, []);

    if (loading && !data) {
        return (
            <div style={{ textAlign: "center", padding: 60 }}>
                <div className="spinner" style={{ margin: "0 auto", width: 40, height: 40 }} />
                <p style={{ marginTop: 16, color: "var(--muted)" }}>Running System Diagnostics...</p>
            </div>
        );
    }

    const getStatusColor = (status) => {
        switch (status) {
            case "online": return "var(--success)";
            case "rate_limited": return "var(--warning)";
            case "degraded": return "var(--warning)";
            case "error": return "var(--danger)";
            case "offline": return "var(--danger)";
            default: return "var(--muted)";
        }
    };

    const getStatusLabel = (status) => {
        switch (status) {
            case "online": return "OK";
            case "rate_limited": return "RATE LIMITED";
            case "degraded": return "DEGRADED";
            case "error": return "ERROR";
            case "offline": return "OFFLINE";
            default: return "UNKNOWN";
        }
    };

    const c = data?.components || {};

    return (
        <div>
            <div className="page-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
                <div>
                    <div className="page-title">System Diagnostics</div>
                    <div className="page-subtitle">// LIVE RESOURCE MONITORING & TELEMETRY</div>
                </div>
                <div>
                    <button className="btn btn-secondary" onClick={fetchDiagnostics} disabled={loading}>
                        {loading ? "Refreshing..." : "↻ Refresh Now"}
                    </button>
                </div>
            </div>

            <div style={{
                padding: "16px 24px",
                marginBottom: 24,
                borderRadius: 8,
                background: "rgba(0,0,0,0.2)",
                border: `1px solid ${getStatusColor(data?.overall)}`,
                display: "flex",
                alignItems: "center",
                gap: 16
            }}>
                <div className="status-dot" style={{ background: getStatusColor(data?.overall), width: 16, height: 16 }} />
                <div style={{ fontSize: 18, fontWeight: 600 }}>
                    System Overall State: <span style={{ color: getStatusColor(data?.overall), textTransform: "uppercase" }}>{data?.overall || "UNKNOWN"}</span>
                </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginBottom: 24 }}>
                {/* DATABASE */}
                <div className="card">
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
                        <div className="card-title" style={{ margin: 0 }}>SQLite + WAL Database</div>
                        <span className="badge" style={{ backgroundColor: getStatusColor(c.database?.status) }}>
                            {getStatusLabel(c.database?.status)}
                        </span>
                    </div>
                    <div style={{ fontSize: 13, color: "var(--muted)" }}>
                        <strong>Message:</strong> {c.database?.message || "—"}
                    </div>
                </div>

                {/* GROQ API */}
                <div className="card">
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
                        <div className="card-title" style={{ margin: 0 }}>Groq NLP Engine</div>
                        <span className="badge" style={{ backgroundColor: getStatusColor(c.groq_api?.status) }}>
                            {getStatusLabel(c.groq_api?.status)}
                        </span>
                    </div>
                    <div style={{ fontSize: 13, color: "var(--muted)", marginBottom: 16 }}>
                        <strong>Message:</strong> {c.groq_api?.message || "—"}
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, background: "rgba(0,0,0,0.3)", padding: 12, borderRadius: 6 }}>
                        <div>
                            <div style={{ fontSize: 10, textTransform: "uppercase", opacity: 0.6 }}>Rem. Reqs</div>
                            <div style={{ fontFamily: "var(--font-mono)", fontSize: 14 }}>{c.groq_api?.remaining_reqs ?? "—"}</div>
                        </div>
                        <div>
                            <div style={{ fontSize: 10, textTransform: "uppercase", opacity: 0.6 }}>Reset Reqs</div>
                            <div style={{ fontFamily: "var(--font-mono)", fontSize: 14 }}>{c.groq_api?.reset_reqs ?? "—"}</div>
                        </div>
                        <div>
                            <div style={{ fontSize: 10, textTransform: "uppercase", opacity: 0.6 }}>Rem. Tokens</div>
                            <div style={{ fontFamily: "var(--font-mono)", fontSize: 14 }}>{c.groq_api?.remaining_tokens ?? "—"}</div>
                        </div>
                        <div>
                            <div style={{ fontSize: 10, textTransform: "uppercase", opacity: 0.6 }}>Reset Tokens</div>
                            <div style={{ fontFamily: "var(--font-mono)", fontSize: 14 }}>{c.groq_api?.reset_tokens ?? "—"}</div>
                        </div>
                    </div>
                </div>

                {/* WORKERS */}
                <div className="card">
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
                        <div className="card-title" style={{ margin: 0 }}>Scraping Workers / GHA</div>
                        <span className="badge" style={{ backgroundColor: getStatusColor(c.jobs?.status) }}>
                            {getStatusLabel(c.jobs?.status)}
                        </span>
                    </div>
                    <div style={{ fontSize: 13, color: "var(--muted)", marginBottom: 16 }}>
                        <strong>Message:</strong> {c.jobs?.message || "—"}
                    </div>
                    <div style={{ display: "flex", gap: 24, fontSize: 13 }}>
                        <div><span style={{ color: "var(--accent)" }}>●</span> Active Jobs: <strong>{c.jobs?.running_count || 0}</strong></div>
                        <div><span style={{ color: "var(--danger)" }}>●</span> Failed Jobs: <strong>{c.jobs?.failed_count || 0}</strong></div>
                    </div>
                </div>

                {/* PLAYWRIGHT */}
                <div className="card">
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
                        <div className="card-title" style={{ margin: 0 }}>Playwright Headless Engine</div>
                        <span className="badge" style={{ backgroundColor: getStatusColor(c.playwright?.status) }}>
                            {getStatusLabel(c.playwright?.status)}
                        </span>
                    </div>
                    <div style={{ fontSize: 13, color: "var(--muted)" }}>
                        <strong>Message:</strong> {c.playwright?.message || "—"}
                    </div>
                </div>
            </div>

            <div className="card">
                <div className="card-title" style={{ display: 'flex', alignItems: 'center' }}>
                    <span style={{ display: 'inline-block', width: 6, height: 16, background: 'var(--danger)', marginRight: 8, borderRadius: 2 }} />
                    Recent Real-Time Error Logs (scraper.log)
                </div>
                <div style={{
                    background: "#0d1117",
                    border: "1px solid var(--border)",
                    borderRadius: 6,
                    padding: 16,
                    maxHeight: 300,
                    overflowY: "auto",
                    fontFamily: "var(--font-mono)",
                    fontSize: 12,
                    lineHeight: 1.5,
                    color: "var(--danger)"
                }}>
                    {data?.recent_log_errors?.length > 0 ? (
                        data.recent_log_errors.map((err, i) => (
                            <div key={i} style={{ paddingBottom: 8, marginBottom: 8, borderBottom: "1px solid rgba(255,255,255,0.05)", wordWrap: "break-word" }}>
                                {err}
                            </div>
                        ))
                    ) : (
                        <div style={{ color: "var(--success)" }}>✓ No recent errors detected. Log is clean.</div>
                    )}
                </div>
            </div>
        </div>
    );
}
