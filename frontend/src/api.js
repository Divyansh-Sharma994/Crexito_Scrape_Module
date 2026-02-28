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

  exportUrl(params) {
    const query = new URLSearchParams(params).toString();
    return `${API_BASE}/articles/export/csv?${query}`;
  }
};
