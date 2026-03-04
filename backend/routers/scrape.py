import uuid
import asyncio
from datetime import date
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from db.database import get_db
from scraper.engine import run_scrape_job, REGION_MAP, SECTOR_KEYWORDS
from scraper.enrichment import run_enrichment

router = APIRouter()

# In-memory enrichment progress tracker
_enrichment_status = {"running": False, "enriched": 0, "failed": 0, "total": 0, "started_at": None}


class ScrapeRequest(BaseModel):
    sector: str
    region: str
    date_from: date
    date_to: date
    search_mode: str = "broad"  # 'broad' or 'smart'


@router.post("/start")
async def start_scrape(req: ScrapeRequest, background_tasks: BackgroundTasks):
    """Kick off a new scrape job with full pre-launch validation."""
    # ── Input validation ─────────────────────────────────────────────────────────
    if req.sector.lower() not in SECTOR_KEYWORDS:
        raise HTTPException(400, f"Unknown sector. Choose from: {sorted(SECTOR_KEYWORDS.keys())}")
    if req.region.lower() not in REGION_MAP:
        raise HTTPException(400, f"Unknown region. Choose from: {sorted(REGION_MAP.keys())}")
    if req.date_from > req.date_to:
        raise HTTPException(400, "date_from must be on or before date_to")

    # ── Guard: max 30-day range ──────────────────────────────────────────────────
    date_span = (req.date_to - req.date_from).days
    if date_span > 30:
        raise HTTPException(
            400,
            f"Date range too large ({date_span} days). Max allowed is 30 days per job. "
            "Split into multiple jobs for longer ranges."
        )

    # ── Guard: no duplicate overlapping jobs ─────────────────────────────────────
    async with get_db() as db:
        already_running = await db.fetchval(
            "SELECT COUNT(*) FROM scrape_jobs WHERE status='running' AND sector != '__enrichment__'"
        )
    if already_running >= 2:
        raise HTTPException(
            409,
            f"Too many jobs running ({already_running}). Wait for existing jobs to finish before starting a new one."
        )

    # ── Create job row immediately (pending) then hand off to background ─────────
    job_id = str(uuid.uuid4())
    async with get_db() as db:
        await db.execute("""
            INSERT INTO scrape_jobs (id, sector, region, date_from, date_to, status, search_mode)
            VALUES ($1, $2, $3, $4, $5, 'pending', $6)
        """, job_id, req.sector.lower(), req.region.lower(), req.date_from, req.date_to, req.search_mode)

    background_tasks.add_task(
        run_scrape_job,
        job_id=job_id,
        sector=req.sector.lower(),
        region=req.region.lower(),
        date_from=req.date_from,
        date_to=req.date_to,
        search_mode=req.search_mode,
    )

    return {
        "job_id": job_id,
        "status": "pending",
        "message": f"Job queued. Scraping {req.sector}/{req.region} for {date_span + 1} day(s).",
        "date_range_days": date_span + 1,
    }


@router.post("/enrich")
async def start_enrichment(background_tasks: BackgroundTasks, batch_size: int = 20000, concurrency: int = 35):
    """
    Re-scrape all articles with bad/missing body text.
    Resolves Google News redirects, clears junk content, extracts real article text.
    Shows up as a job in the Jobs UI.
    """
    if _enrichment_status["running"]:
        return {
            "message": "Enrichment already running.",
            "status": _enrichment_status
        }

    # Get count of articles needing fix
    async with get_db() as db:
        need_fix = await db.fetchval("""
            SELECT COUNT(*) FROM articles
            WHERE full_body IS NULL
               OR length(full_body) < 100
               OR lower(full_body) LIKE '%google news%'
               OR lower(full_body) LIKE '%enable javascript%'
               OR lower(full_body) LIKE '%continue reading in the app%'
               OR (length(full_body) < 500 AND word_count < 80)
        """)

    # Create a job row so it shows in the Jobs UI
    import uuid as _uuid
    from datetime import date as _date
    job_id = str(_uuid.uuid4())
    async with get_db() as db:
        await db.execute("""
            INSERT INTO scrape_jobs (id, sector, region, date_from, date_to, status, total_found)
            VALUES ($1, $2, $3, $4, $5, 'running', $6)
        """, job_id, "__enrichment__", "all", str(_date.today()), str(_date.today()), need_fix)

    async def _run():
        _enrichment_status["running"] = True
        _enrichment_status["started_at"] = _date.today().isoformat()
        _enrichment_status["enriched"] = 0
        _enrichment_status["failed"] = 0
        _enrichment_status["job_id"] = job_id
        try:
            result = await run_enrichment(job_id=job_id, batch_size=batch_size, concurrency=concurrency)
            _enrichment_status.update(result)
            async with get_db() as db:
                await db.execute("""
                    UPDATE scrape_jobs SET status='completed', completed_at=CURRENT_TIMESTAMP,
                    total_scraped=$1 WHERE id=$2
                """, result["enriched"], job_id)
        except Exception as e:
            async with get_db() as db:
                await db.execute("UPDATE scrape_jobs SET status='failed', error=$1 WHERE id=$2", str(e), job_id)
        finally:
            _enrichment_status["running"] = False

    background_tasks.add_task(_run)

    return {
        "job_id": job_id,
        "message": f"Enrichment started. {need_fix} articles queued for body recovery.",
        "articles_to_fix": need_fix,
        "concurrency": concurrency,
    }


class AutomatedScrapeRequest(BaseModel):
    sector: str
    region: str
    search_mode: str = "broad"

@router.post("/automated_daily")
async def start_automated_daily(req: AutomatedScrapeRequest, background_tasks: BackgroundTasks):
    """
    Cron-compatible endpoint. Calculates yesterday's date natively
    and dispatches a job without needing date inputs. Optionally
    triggers enrichment after completion.
    """
    from datetime import date, timedelta
    yesterday = date.today() - timedelta(days=1)
    
    # Check max running jobs
    async with get_db() as db:
        already_running = await db.fetchval(
            "SELECT COUNT(*) FROM scrape_jobs WHERE status='running' AND sector != '__enrichment__'"
        )
    if already_running >= 2:
        raise HTTPException(
            409,
            "Queue full. Cannot inject automated job."
        )

    job_id = str(uuid.uuid4())
    async with get_db() as db:
        await db.execute("""
            INSERT INTO scrape_jobs (id, sector, region, date_from, date_to, status, search_mode)
            VALUES ($1, $2, $3, $4, $5, 'pending', $6)
        """, job_id, req.sector.lower(), req.region.lower(), yesterday, yesterday, req.search_mode)

    from scraper.engine import log
    log(f"🤖 Automated trigger: Initiating {req.sector}/{req.region} for date {yesterday} | Mode: {req.search_mode}")
    
    background_tasks.add_task(
        run_scrape_job,
        job_id=job_id,
        sector=req.sector.lower(),
        region=req.region.lower(),
        date_from=yesterday,
        date_to=yesterday,
        search_mode=req.search_mode,
    )

    return {
        "status": "queued_automated",
        "job_id": job_id,
        "sector": req.sector.lower(),
        "region": req.region.lower(),
        "date_scraped": yesterday.isoformat()
    }


@router.get("/enrich/status")
async def enrichment_status():
    """Live status of the running enrichment job."""
    async with get_db() as db:
        remaining = await db.fetchval("""
            SELECT COUNT(*) FROM articles
            WHERE full_body IS NULL
               OR length(full_body) < 100
               OR lower(full_body) LIKE '%google news%'
               OR lower(full_body) LIKE '%enable javascript%'
               OR lower(full_body) LIKE '%continue reading in the app%'
               OR (length(full_body) < 500 AND word_count < 80)
        """)
        total = await db.fetchval("SELECT COUNT(*) FROM articles")
        with_body = await db.fetchval("SELECT COUNT(*) FROM articles WHERE full_body IS NOT NULL AND length(full_body) > 100")

    return {
        **_enrichment_status,
        "articles_still_needing_fix": remaining,
        "total_articles": total,
        "with_good_body": with_body,
        "body_coverage_pct": round(with_body / total * 100, 1) if total else 0,
    }


@router.get("/job/{job_id}")
async def get_job_status(job_id: str):
    """Get status and progress of a scrape job."""
    async with get_db() as db:
        row = await db.fetchrow("SELECT * FROM scrape_jobs WHERE id=$1", job_id)
        if not row:
            raise HTTPException(404, "Job not found")
        return row


@router.get("/jobs")
async def list_jobs(limit: int = 20):
    """List recent scrape jobs."""
    async with get_db() as db:
        rows = await db.fetch(
            "SELECT * FROM scrape_jobs ORDER BY started_at DESC LIMIT $1", limit
        )
        return rows


@router.delete("/job/{job_id}")
async def delete_job(job_id: str):
    """Delete a job and its articles."""
    async with get_db() as db:
        await db.execute("DELETE FROM articles WHERE scrape_job_id=$1", job_id)
        await db.execute("DELETE FROM scrape_jobs WHERE id=$1", job_id)
    return {"deleted": job_id}


@router.get("/options")
def get_options():
    """Return available sectors and regions."""
    return {
        "sectors": sorted(SECTOR_KEYWORDS.keys()),
        "regions": sorted(REGION_MAP.keys()),
    }
