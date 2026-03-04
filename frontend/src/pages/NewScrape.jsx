import { useState, useEffect, useMemo } from "react";
import { api } from "../api";

export default function NewScrape({ onNavigate }) {
  const [options, setOptions] = useState({ sectors: [], regions: [] });
  const [form, setForm] = useState({
    sector: "",
    region: "",
    date_from: "",
    date_to: new Date().toISOString().slice(0, 10),
    search_mode: "broad",
  });
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.get("/scrape/options").then(setOptions).catch(() => { });
  }, []);

  // Client-side date range validation
  const dateWarning = useMemo(() => {
    if (!form.date_from || !form.date_to) return null;
    const days = Math.round((new Date(form.date_to) - new Date(form.date_from)) / 86400000);
    if (days < 0) return "⚠ Date From must be before Date To";
    if (days > 30) return `⚠ Range is ${days} days — max allowed is 30 days per job`;
    return null;
  }, [form.date_from, form.date_to]);

  const handleSubmit = async () => {
    if (!form.sector || !form.region || !form.date_from || !form.date_to) {
      setError("All fields are required.");
      return;
    }
    if (dateWarning) {
      setError(dateWarning);
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.post("/scrape/start", form);
      setResult(res);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  return (
    <div>
      <div className="page-header">
        <div className="page-title">New Scrape Job</div>
        <div className="page-subtitle">// CONFIGURE TARGET PARAMETERS AND LAUNCH</div>
      </div>

      {error && <div className="alert alert-error">⚠ {error}</div>}
      {result && (
        <div className="alert alert-success">
          ✓ Job started — ID: <strong style={{ fontFamily: "var(--font-mono)", marginLeft: 8 }}>{result.job_id}</strong>
          <span style={{ marginLeft: 12, fontSize: 12, opacity: 0.8 }}>{result.message}</span>
          <button
            className="btn btn-secondary"
            style={{ marginLeft: "auto", padding: "4px 12px", fontSize: 11 }}
            onClick={() => onNavigate("jobs")}
          >
            Monitor →
          </button>
        </div>
      )}

      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-title">Target Configuration</div>

        <div className="form-grid">
          <div className="form-group">
            <label className="form-label">Sector</label>
            <select className="form-control" value={form.sector} onChange={(e) => set("sector", e.target.value)}>
              <option value="">— Select sector —</option>
              {options.sectors.map((s) => (
                <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Region</label>
            <select className="form-control" value={form.region} onChange={(e) => set("region", e.target.value)}>
              <option value="">— Select region —</option>
              {options.regions.map((r) => (
                <option key={r} value={r}>{r.charAt(0).toUpperCase() + r.slice(1)}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Date From</label>
            <input
              type="date"
              className="form-control"
              value={form.date_from}
              max={form.date_to}
              onChange={(e) => set("date_from", e.target.value)}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Date To</label>
            <input
              type="date"
              className="form-control"
              value={form.date_to}
              min={form.date_from}
              max={new Date().toISOString().slice(0, 10)}
              onChange={(e) => set("date_to", e.target.value)}
            />
          </div>
        </div>

        <div className="form-group" style={{ marginTop: 20 }}>
          <label className="form-label">Search Mode</label>
          <div style={{ display: "flex", gap: 12 }}>
            <button
              className={`btn ${form.search_mode === "broad" ? "btn-primary" : "btn-secondary"}`}
              style={{ flex: 1, padding: "12px" }}
              onClick={() => set("search_mode", "broad")}
            >
              <div style={{ fontWeight: 700 }}>Broad Mode</div>
              <div style={{ fontSize: 11, opacity: 0.8 }}>Save everything found</div>
            </button>
            <button
              className={`btn ${form.search_mode === "smart" ? "btn-primary" : "btn-secondary"}`}
              style={{ flex: 1, padding: "12px", border: form.search_mode === "smart" ? "1px solid var(--accent)" : "1px solid transparent" }}
              onClick={() => set("search_mode", "smart")}
            >
              <div style={{ fontWeight: 700 }}>✨ Smart Mode</div>
              <div style={{ fontSize: 11, opacity: 0.8 }}>AI filter for relevance</div>
            </button>
          </div>
          {form.search_mode === "smart" && (
            <div style={{ fontSize: 12, color: "var(--accent)", marginTop: 8, fontStyle: "italic" }}>
              Uses local LLM to filter out passing mentions and ensuring your target is the primary subject.
            </div>
          )}
        </div>

        {dateWarning && (
          <div className="alert alert-error" style={{ marginBottom: 16 }}>{dateWarning}</div>
        )}

        <button className="btn btn-primary" onClick={handleSubmit} disabled={loading || !!dateWarning}>
          {loading ? <><div className="spinner" /> Launching...</> : "⊕ Launch Scrape Job"}
        </button>
      </div>

      <div className="card">
        <div className="card-title">How It Works</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 20 }}>
          {[
            { step: "01", title: "Discovery", desc: "RSS feeds from Google News + Bing are queried using your sector + region + date range to discover relevant article URLs." },
            { step: "02", title: "Extraction", desc: "Each URL is rendered by a headless Chromium browser with paywall bypass, then parsed to extract full body, author, agency, and date." },
            { step: "03", title: "AI Processing", desc: "Articles are deduplicated, stored with full text, and summarized using Groq AI. Your team can then query, filter, and export." },
          ].map((s) => (
            <div key={s.step} style={{ borderLeft: "2px solid var(--border)", paddingLeft: 16 }}>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--accent)", marginBottom: 8 }}>
                STEP {s.step}
              </div>
              <div style={{ fontWeight: 700, marginBottom: 6 }}>{s.title}</div>
              <div style={{ fontSize: 13, color: "var(--muted)", lineHeight: 1.6 }}>{s.desc}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
