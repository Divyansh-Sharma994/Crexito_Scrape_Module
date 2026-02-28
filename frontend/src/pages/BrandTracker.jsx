import { useState, useEffect } from "react";

export default function BrandTracker() {
    const [brands, setBrands] = useState([]);
    const [newBrand, setNewBrand] = useState("");
    const [loading, setLoading] = useState(false);
    const [msg, setMsg] = useState(null);
    const [days, setDays] = useState(30);

    useEffect(() => {
        fetchBrands();
    }, []);

    const fetchBrands = async () => {
        try {
            const res = await fetch("/api/brands/");
            const data = await res.json();
            setBrands(data);
        } catch (err) {
            console.error("Failed to fetch brands", err);
        }
    };

    const addBrand = async () => {
        if (!newBrand.trim()) return;
        try {
            const res = await fetch("/api/brands/", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name: newBrand.trim() }),
            });
            if (res.ok) {
                setNewBrand("");
                fetchBrands();
            } else {
                const err = await res.json();
                setMsg({ type: "error", text: err.detail || "Failed to add brand" });
            }
        } catch (err) {
            setMsg({ type: "error", text: "Connection error" });
        }
    };

    const deleteBrand = async (name) => {
        try {
            await fetch(`/api/brands/${name}`, { method: "DELETE" });
            fetchBrands();
        } catch (err) {
            console.error(err);
        }
    };

    const startScrape = async () => {
        setLoading(true);
        setMsg(null);
        try {
            const res = await fetch(`/api/brands/scrape?days=${days}`, { method: "POST" });
            const data = await res.json();
            if (res.ok) {
                setMsg({ type: "success", text: `Job started: ${data.job_id}. Checking the last ${days} days for ${brands.length} brands.` });
            } else {
                setMsg({ type: "error", text: data.detail || "Failed to start scrape" });
            }
        } catch (err) {
            setMsg({ type: "error", text: "Connection error" });
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="page-container">
            <header className="page-header">
                <div>
                    <h1 className="page-title">🏢 Brand Tracker</h1>
                    <p className="page-subtitle">Monitor specific companies and brands across news sources</p>
                </div>
            </header>

            {msg && (
                <div className={`alert ${msg.type === "error" ? "alert-error" : "alert-success"}`}>
                    {loading && msg.type !== "error" ? <div className="spinner"></div> : null}
                    {msg.text}
                </div>
            )}

            <div className="grid">
                <div className="card" style={{ marginBottom: "2rem" }}>
                    <div className="card-title">Discovery Controls</div>
                    <div className="filter-bar" style={{ gap: "24px", alignItems: "flex-end" }}>
                        <div className="form-group" style={{ flex: 1 }}>
                            <label className="form-label">Scrape Duration (Lookback)</label>
                            <select
                                className="form-control"
                                value={days}
                                onChange={(e) => setDays(e.target.value)}
                                disabled={loading}
                            >
                                <option value={1}>24 Hours (Daily Refresh)</option>
                                <option value={7}>7 Days (Weekly Round-up)</option>
                                <option value={30}>30 Days (Monthly Deep Dive - 1k+ Articles)</option>
                                <option value={90}>90 Days (Quarterly Analysis - Max Scale)</option>
                            </select>
                        </div>
                        <button
                            className="btn btn-primary"
                            onClick={startScrape}
                            disabled={loading || brands.length === 0}
                            style={{ height: "42px", minWidth: "220px", justifyContent: "center" }}
                        >
                            {loading ? "Launching..." : "🚀 Precise Scrape Now"}
                        </button>
                    </div>
                </div>

                <div className="card" style={{ marginBottom: "2rem" }}>
                    <div className="card-title">Add Target</div>
                    <div style={{ display: "flex", gap: "1rem" }}>
                        <input
                            type="text"
                            className="form-control"
                            placeholder="Enter brand name (e.g. Razorpay, Zomato, Fujifilm)"
                            value={newBrand}
                            onChange={(e) => setNewBrand(e.target.value)}
                            onKeyDown={(e) => e.key === "Enter" && addBrand()}
                            style={{ flex: 1 }}
                        />
                        <button className="btn btn-secondary" onClick={addBrand}>Add Brand</button>
                    </div>
                </div>

                <div className="card col-full">
                    <div className="card-title">Active Watchlist ({brands.length})</div>
                    <div className="table-wrap" style={{ marginTop: "1rem" }}>
                        <table className="table">
                            <thead>
                                <tr>
                                    <th>Brand Name</th>
                                    <th>Added On</th>
                                    <th>Last Scraped</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {brands.length === 0 ? (
                                    <tr><td colSpan="4" className="empty-state">No brands found. Add your first brand above.</td></tr>
                                ) : (
                                    brands.map((b) => (
                                        <tr key={b.name}>
                                            <td style={{ fontWeight: 600, color: "var(--accent)" }}>{b.name}</td>
                                            <td><span className="badge badge-pending">{new Date(b.added_at).toLocaleDateString()}</span></td>
                                            <td>{b.last_scraped ? <span className="badge badge-completed">{new Date(b.last_scraped).toLocaleString()}</span> : <span className="badge badge-interrupted">Never</span>}</td>
                                            <td>
                                                <button className="btn btn-danger" onClick={() => deleteBrand(b.name)} style={{ padding: "6px 12px", fontSize: "11px" }}>Remove</button>
                                            </td>
                                        </tr>
                                    ))
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    );
}
