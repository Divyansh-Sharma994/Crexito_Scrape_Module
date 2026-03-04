# SPEC.md — Scraper Discovery Metrics & Task Tracking

> **Status**: `FINALIZED`
>
> ⚠️ **Planning Lock**: No code may be written until this spec is marked `FINALIZED`.

## Vision
Enhance the scraper engine and dashboard to provide real-time metrics on URL discovery (Discovery Pool) and granular task tracking (Phase Status) to improve transparency for long-running jobs.

## Goals
1. **Cumulative Metrics** — Track total unique URLs discovered across all engines (Google, Bing, Sitemaps, Recursive) for a single job.
2. **Phase Persistance** — Store the status and last update time of specific high-level tasks (Preflight, Discovery, Extraction) in the database.
3. **Advanced Dashboard** — Expose these metrics on the Jobs page with a toggleable details view.

## Success Criteria
- [x] Logs show a monotonic "Cumulative" URL count.
- [x] Jobs table shows "Discovery Pool: N URLs" under progress.
- [x] Toggle button expands to show phase-level statuses (e.g., Preflight: completed, Discovery: running).

---
*Last updated: 2026-03-04*
