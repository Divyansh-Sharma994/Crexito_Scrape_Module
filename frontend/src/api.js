// Use Vite proxy for /api routes in dev (vite.config.js proxies /api → :8000)
// In production, set VITE_API_URL to the real backend URL
const API_BASE = import.meta.env.VITE_API_URL || "/api";

export const api = {
  async get(endpoint) {
    const response = await fetch(`${API_BASE}${endpoint}`);
    if (!response.ok) {
      const body = await response.text();
      let detail = response.statusText;
      try { detail = JSON.parse(body).detail || detail; } catch { }
      throw new Error(detail);
    }
    return response.json();
  },

  async post(endpoint, data) {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      const body = await response.text();
      let detail = response.statusText;
      try { detail = JSON.parse(body).detail || detail; } catch { }
      throw new Error(detail);
    }
    return response.json();
  },

  async delete(endpoint) {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      method: "DELETE",
    });
    if (!response.ok) throw new Error(`API Error: ${response.statusText}`);
    return response.json();
  },

  _cleanParams(params) {
    const clean = {};
    if (!params) return "";
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") {
        clean[k] = v;
      }
    });
    return new URLSearchParams(clean).toString();
  },

  exportUrl(params) {
    const query = this._cleanParams(params);
    return `${API_BASE}/articles/export/csv?${query}`;
  },

  exportXlsxUrl(params) {
    const query = this._cleanParams(params);
    return `${API_BASE}/articles/export/xlsx?${query}`;
  }
};
