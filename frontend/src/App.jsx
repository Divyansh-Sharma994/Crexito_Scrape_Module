import { useState, useEffect } from "react";
import Dashboard from "./pages/Dashboard";
import NewScrape from "./pages/NewScrape";
import ArticlesBrowser from "./pages/ArticlesBrowser";
import BrandTracker from "./pages/BrandTracker";
import Jobs from "./pages/Jobs";
import Diagnostics from "./pages/Diagnostics";
import "./index.css";

const NAV = [
  { id: "dashboard", label: "Dashboard", icon: "◈" },
  { id: "scrape", label: "New Scrape", icon: "⊕" },
  { id: "articles", label: "Articles", icon: "≡" },
  { id: "brands", label: "Brand Tracker", icon: "🏢" },
  { id: "jobs", label: "Jobs", icon: "◎" },
  { id: "diagnostics", label: "Diagnostics", icon: "⎋" },
];

export default function App() {
  const [page, setPage] = useState("dashboard");
  const [apiStatus, setApiStatus] = useState("checking"); // "online" | "offline" | "checking"

  useEffect(() => {
    let ws;
    let pollInterval;

    const checkHealth = async () => {
      try {
        const resp = await fetch("/api/diagnostics/health");
        if (resp.ok) {
          setApiStatus("online");
        } else {
          setApiStatus("offline");
        }
      } catch (err) {
        setApiStatus("offline");
      }
    };

    const connect = () => {
      const loc = window.location;
      const protocol = loc.protocol === "https:" ? "wss:" : "ws:";
      const host = loc.host;
      ws = new WebSocket(`${protocol}//${host}/api/articles/ws/stats`);

      ws.onmessage = (event) => {
        setApiStatus("online");
      };

      ws.onerror = () => {
        // Don't mark offline immediately, fallback to REST check
        checkHealth();
      };

      ws.onclose = () => {
        setTimeout(connect, 10000); // Wait longer between retries to avoid spam
      };
    };

    connect();
    // Periodic safety poll every 30s in case WS is dead but REST is alive
    pollInterval = setInterval(checkHealth, 30000);
    checkHealth(); // Initial check

    return () => {
      if (ws) ws.close();
      if (pollInterval) clearInterval(pollInterval);
    };
  }, []);

  const statusColor = apiStatus === "online" ? "var(--success)" : apiStatus === "offline" ? "var(--danger)" : "var(--warning)";
  const statusLabel = apiStatus === "online" ? "API Connected" : apiStatus === "offline" ? "API Offline" : "Connecting...";

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="brand-icon">⬡</div>
          <div>
            <div className="brand-name">NEXUS</div>
            <div className="brand-sub">Global Intelligence</div>
          </div>
        </div>
        <nav className="sidebar-nav">
          {NAV.map((n) => (
            <button
              key={n.id}
              className={`nav-item ${page === n.id ? "active" : ""}`}
              onClick={() => setPage(n.id)}
            >
              <span className="nav-icon">{n.icon}</span>
              <span>{n.label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="status-dot" style={{ background: statusColor, boxShadow: `0 0 6px ${statusColor}` }} />
          <span>{statusLabel}</span>
        </div>
      </aside>

      <main className="main-content">
        {page === "dashboard" && <Dashboard onNavigate={setPage} />}
        {page === "scrape" && <NewScrape onNavigate={setPage} />}
        {page === "articles" && <ArticlesBrowser />}
        {page === "brands" && <BrandTracker />}
        {page === "jobs" && <Jobs />}
        {page === "diagnostics" && <Diagnostics />}
      </main>
    </div>
  );
}
