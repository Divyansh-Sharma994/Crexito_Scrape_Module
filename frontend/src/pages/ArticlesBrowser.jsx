import { useState, useEffect, useCallback } from "react";
import { api } from "../api";

function ArticleModal({ article, onClose }) {
  if (!article) return null;
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-title">{article.title || "Untitled"}</div>
        <div className="modal-meta">
          <div className="meta-item">Author: <span>{article.author || "Unknown"}</span></div>
          <div className="meta-item">Agency: <span>{article.agency || "Unknown"}</span></div>
          <div className="meta-item">Published: <span>{article.published_at ? new Date(article.published_at).toLocaleString() : "Unknown"}</span></div>
          <div className="meta-item">Words: <span>{article.word_count ?? "—"}</span></div>
          <div className="meta-item">
            <span className="badge badge-sector">{article.sector}</span>
          </div>
          <div className="meta-item">
            <span className="badge badge-region">{article.region}</span>
          </div>
        </div>
        <div style={{ marginBottom: 16 }}>
          <a href={article.url} target="_blank" rel="noopener noreferrer"
            style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>
            ↗ Open original article
          </a>
        </div>
        {article.full_body ? (
          <div className="article-body">{article.full_body}</div>
        ) : (
          <div style={{ color: "var(--muted)", fontStyle: "italic" }}>
            Full body not available for this article.
          </div>
        )}
        <div style={{ marginTop: 24, textAlign: "right" }}>
          <button className="btn btn-secondary" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}

export default function ArticlesBrowser() {
  const [articles, setArticles] = useState([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(null);
  const [options, setOptions] = useState({ sectors: [], regions: [] });

  const [filters, setFilters] = useState({
    sector: "",
    region: "",
    date_from: "",
    date_to: "",
    search: "",
  });

  useEffect(() => {
    api.get("/scrape/options").then(setOptions).catch(() => {});
  }, []);

  const loadArticles = useCallback(async (pg = 1) => {
    setLoading(true);
    const params = new URLSearchParams({ page: pg, page_size: 25 });
    Object.entries(filters).forEach(([k, v]) => { if (v) params.set(k, v); });
    try {
      const res = await api.get(`/articles/?${params}`);
      setArticles(res.articles);
      setTotal(res.total);
      setTotalPages(res.total_pages);
      setPage(pg);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => { loadArticles(1); }, []);

  const openArticle = async (id) => {
    try {
      const full = await api.get(`/articles/${id}`);
      setSelected(full);
    } catch {}
  };

  const setFilter = (k, v) => setFilters((f) => ({ ...f, [k]: v }));

  const exportCsv = () => {
    const params = {};
    Object.entries(filters).forEach(([k, v]) => { if (v) params[k] = v; });
    window.open(api.exportUrl(params), "_blank");
  };

  return (
    <div>
      {selected && <ArticleModal article={selected} onClose={() => setSelected(null)} />}

      <div className="page-header">
        <div className="page-title">Articles Browser</div>
        <div className="page-subtitle">// {total.toLocaleString()} ARTICLES IN DATABASE</div>
      </div>

      {/* Filters */}
      <div className="filter-bar">
        <div className="form-group">
          <label className="form-label">Sector</label>
          <select className="form-control" value={filters.sector} onChange={(e) => setFilter("sector", e.target.value)}>
            <option value="">All Sectors</option>
            {options.sectors.map((s) => <option key={s}>{s}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label className="form-label">Region</label>
          <select className="form-control" value={filters.region} onChange={(e) => setFilter("region", e.target.value)}>
            <option value="">All Regions</option>
            {options.regions.map((r) => <option key={r}>{r}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label className="form-label">From</label>
          <input type="date" className="form-control" value={filters.date_from} onChange={(e) => setFilter("date_from", e.target.value)} />
        </div>
        <div className="form-group">
          <label className="form-label">To</label>
          <input type="date" className="form-control" value={filters.date_to} onChange={(e) => setFilter("date_to", e.target.value)} />
        </div>
        <div className="form-group" style={{ minWidth: 220 }}>
          <label className="form-label">Search</label>
          <input
            type="text"
            className="form-control"
            placeholder="Title or body..."
            value={filters.search}
            onChange={(e) => setFilter("search", e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && loadArticles(1)}
          />
        </div>
        <button className="btn btn-primary" onClick={() => loadArticles(1)} style={{ alignSelf: "flex-end" }}>
          Search
        </button>
        <button className="btn btn-secondary" onClick={exportCsv} style={{ alignSelf: "flex-end" }}>
          ↓ Export CSV
        </button>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Title</th>
              <th>Author</th>
              <th>Agency</th>
              <th>Published</th>
              <th>Sector</th>
              <th>Region</th>
              <th>Words</th>
              <th>URL</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={8} style={{ textAlign: "center", padding: 40 }}>
                <div className="spinner" style={{ margin: "0 auto" }} />
              </td></tr>
            ) : articles.length === 0 ? (
              <tr><td colSpan={8}>
                <div className="empty-state">
                  <div className="empty-state-icon">◈</div>
                  <h3>No articles found</h3>
                  <p>Try adjusting your filters or start a new scrape job.</p>
                </div>
              </td></tr>
            ) : articles.map((a) => (
              <tr key={a.id} style={{ cursor: "pointer" }} onClick={() => openArticle(a.id)}>
                <td style={{ maxWidth: 300, fontWeight: 600, fontSize: 13 }}>
                  {a.title?.slice(0, 80) || "—"}{a.title?.length > 80 ? "..." : ""}
                </td>
                <td style={{ whiteSpace: "nowrap", fontSize: 12 }}>{a.author || "—"}</td>
                <td style={{ whiteSpace: "nowrap", fontSize: 12 }}>{a.agency || "—"}</td>
                <td style={{ whiteSpace: "nowrap", fontSize: 12, fontFamily: "var(--font-mono)" }}>
                  {a.published_at ? new Date(a.published_at).toLocaleDateString() : "—"}
                </td>
                <td><span className="badge badge-sector">{a.sector}</span></td>
                <td><span className="badge badge-region">{a.region}</span></td>
                <td style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>{a.word_count ?? "—"}</td>
                <td onClick={(e) => e.stopPropagation()}>
                  <a className="url-cell" href={a.url} target="_blank" rel="noopener noreferrer" title={a.url}>
                    ↗ link
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="pagination">
          <button className="btn btn-secondary" disabled={page <= 1} onClick={() => loadArticles(page - 1)}>
            ← Prev
          </button>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--muted)" }}>
            Page {page} of {totalPages}
          </span>
          <button className="btn btn-secondary" disabled={page >= totalPages} onClick={() => loadArticles(page + 1)}>
            Next →
          </button>
        </div>
      )}
    </div>
  );
}
