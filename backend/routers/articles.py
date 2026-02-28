from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse
from db.database import get_db
import csv
import io
from typing import Optional, AsyncGenerator
from datetime import date

router = APIRouter()


@router.get("/")
async def get_articles(
    sector: Optional[str] = None,
    region: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    job_id: Optional[str] = None,
    search: Optional[str] = None,
    has_body: Optional[bool] = None,   # New filter: only articles with full body
    page: int = 1,
    page_size: int = 25,
):
    """Fetch articles with filtering and pagination. Fix #7: Includes summary in response."""
    offset = (page - 1) * page_size

    conditions = []
    params = []
    i = 1

    if sector:
        conditions.append(f"sector = ${i}"); params.append(sector); i += 1
    if region:
        conditions.append(f"region = ${i}"); params.append(region); i += 1
    if date_from:
        conditions.append(f"published_at >= ${i}"); params.append(str(date_from)); i += 1
    if date_to:
        conditions.append(f"published_at <= ${i}"); params.append(str(date_to)); i += 1
    if job_id:
        conditions.append(f"scrape_job_id = ${i}"); params.append(job_id); i += 1
    if search:
        conditions.append(f"(title ILIKE ${i} OR full_body ILIKE ${i+1})")
        params.extend([f"%{search}%", f"%{search}%"]); i += 2
    if has_body is True:
        conditions.append("full_body IS NOT NULL AND length(full_body) > 100")
    elif has_body is False:
        conditions.append("(full_body IS NULL OR length(full_body) <= 100)")

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    base_query = f"FROM articles {where}"

    async with get_db() as db:
        total = await db.fetchval(f"SELECT COUNT(*) {base_query}", *params)
        # Return preview (first 200 chars) in list view; full body from single-article endpoint
        rows = await db.fetch(
            f"""SELECT id, title, url, author, agency, published_at,
                       sector, region, word_count, scraped_at, scrape_job_id,
                       summary,
                       CASE WHEN full_body IS NOT NULL THEN substr(full_body, 1, 200) ELSE NULL END as body_preview
                {base_query}
                ORDER BY published_at DESC
                LIMIT ${i} OFFSET ${i + 1}""",
            *params, page_size, offset
        )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": -(-total // page_size) if total else 0,
        "articles": rows,
    }


@router.get("/stats/summary")
async def get_stats():
    """Dashboard stats."""
    async with get_db() as db:
        total = await db.fetchval("SELECT COUNT(*) FROM articles")
        with_body = await db.fetchval("SELECT COUNT(*) FROM articles WHERE full_body IS NOT NULL AND length(full_body) > 100")
        with_summary = await db.fetchval("SELECT COUNT(*) FROM articles WHERE summary IS NOT NULL")
        by_sector = await db.fetch("SELECT sector, COUNT(*) as count FROM articles GROUP BY sector ORDER BY count DESC")
        by_region = await db.fetch("SELECT region, COUNT(*) as count FROM articles GROUP BY region ORDER BY count DESC")
        recent_jobs = await db.fetch("SELECT status, COUNT(*) as count FROM scrape_jobs GROUP BY status")
        latest = await db.fetchrow("SELECT MAX(scraped_at) as last_scraped FROM articles")

    return {
        "total_articles": total or 0,
        "articles_with_body": with_body or 0,
        "articles_with_summary": with_summary or 0,
        "body_coverage_pct": round((with_body / total * 100), 1) if total else 0,
        "by_sector": by_sector,
        "by_region": by_region,
        "jobs_by_status": recent_jobs,
        "last_scraped": latest["last_scraped"] if latest else None,
    }


@router.get("/export/csv")
async def export_csv(
    sector: Optional[str] = None,
    region: Optional[str] = None,
    job_id: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    has_body: Optional[bool] = None,
):
    """FIX #13: Streaming CSV export — never loads entire dataset into RAM."""
    conditions = []
    params = []
    i = 1

    if sector:
        conditions.append(f"sector = ${i}"); params.append(sector); i += 1
    if region:
        conditions.append(f"region = ${i}"); params.append(region); i += 1
    if job_id:
        conditions.append(f"scrape_job_id = ${i}"); params.append(job_id); i += 1
    if date_from:
        conditions.append(f"published_at >= ${i}"); params.append(str(date_from)); i += 1
    if date_to:
        conditions.append(f"published_at <= ${i}"); params.append(str(date_to)); i += 1
    if has_body is True:
        conditions.append("full_body IS NOT NULL AND length(full_body) > 100")

    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    CHUNK_SIZE = 500  # FIX #13: Process 500 rows at a time

    async def generate_csv() -> AsyncGenerator[bytes, None]:
        header = io.StringIO()
        csv.writer(header).writerow(["Title", "URL", "Author", "Agency", "Published At", "Sector", "Region", "Word Count", "Summary", "Full Body"])
        yield header.getvalue().encode("utf-8")

        offset = 0
        while True:
            async with get_db() as db:
                rows = await db.fetch(
                    f"SELECT title, url, author, agency, published_at, sector, region, word_count, summary, full_body "
                    f"FROM articles {where} ORDER BY published_at DESC LIMIT {CHUNK_SIZE} OFFSET {offset}",
                    *params
                )
            if not rows:
                break
            chunk = io.StringIO()
            writer = csv.writer(chunk)
            for r in rows:
                writer.writerow([
                    r["title"], r["url"], r.get("author"), r.get("agency"),
                    r.get("published_at"), r["sector"], r["region"],
                    r.get("word_count"), r.get("summary"), r.get("full_body")
                ])
            yield chunk.getvalue().encode("utf-8")
            offset += CHUNK_SIZE
            if len(rows) < CHUNK_SIZE:
                break

    return StreamingResponse(
        generate_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=articles_export.csv"}
    )


@router.get("/export/json")
async def export_json(
    sector: Optional[str] = None,
    region: Optional[str] = None,
    job_id: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
):
    """Stream articles as newline-delimited JSON."""
    conditions = []
    params = []
    i = 1
    if sector: conditions.append(f"sector = ${i}"); params.append(sector); i += 1
    if region: conditions.append(f"region = ${i}"); params.append(region); i += 1
    if job_id: conditions.append(f"scrape_job_id = ${i}"); params.append(job_id); i += 1
    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    import json as _json
    async def generate():
        offset = 0
        while True:
            async with get_db() as db:
                rows = await db.fetch(f"SELECT * FROM articles {where} ORDER BY id LIMIT 500 OFFSET {offset}", *params)
            if not rows: break
            for r in rows: yield (_json.dumps(r, default=str) + "\n").encode()
            offset += 500
            if len(rows) < 500: break

    return StreamingResponse(generate(), media_type="application/x-ndjson",
                             headers={"Content-Disposition": "attachment; filename=articles.ndjson"})


@router.get("/{article_id}")
async def get_article(article_id: int):
    """Get full article content including body and summary."""
    async with get_db() as db:
        row = await db.fetchrow("SELECT * FROM articles WHERE id=$1", article_id)
        if not row:
            raise HTTPException(404, "Article not found")
        return row
