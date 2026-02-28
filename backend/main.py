import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import scrape, articles, diagnostics, brands
from db.database import init_db

app = FastAPI(
    title="Global News Intelligence API",
    version="2.0.0",
    description="High-volume news scraper: 8k+ articles/day with multi-engine discovery and Groq AI summaries.",
)

# FIX #12: Dynamic CORS — reads from environment so deployment works without code changes
_raw_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:5174,http://localhost:5175,http://localhost:3000"
)
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await init_db()
    print(f"API started. CORS origins: {ALLOWED_ORIGINS}")


@app.on_event("startup")
async def recover_interrupted_jobs():
    """
    On every restart, clean up jobs that were left in a broken state:
    - 'running'  → crashed mid-scrape (server killed, OOM, etc.)
    - 'pending'  → was queued but FastAPI died before the background task ever started
    Both are marked 'interrupted' so the UI doesn't show them as live forever.
    """
    from db.database import get_db
    try:
        async with get_db() as db:
            result = await db.fetch(
                "SELECT id, status FROM scrape_jobs WHERE status IN ('running', 'pending') AND sector != '__enrichment__'"
            )
            if result:
                for row in result:
                    await db.execute(
                        "UPDATE scrape_jobs SET status='interrupted', error='Server restarted while job was in state: ' || status WHERE id=$1",
                        row["id"]
                    )
                print(f"Recovered {len(result)} stuck job(s) (running/pending) from previous session.")
    except Exception as e:
        print(f"Recovery check error (non-fatal): {e}")


@app.on_event("startup")
async def start_scheduler():
    """
    Initializes the internal scheduler for automated daily tasks.
    Triggers 'yesterday's news' scrape for all active sectors every day at 3:00 AM.
    """
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    from routers.scrape import start_automated_daily, AutomatedScrapeRequest
    from scraper.engine import SECTOR_KEYWORDS, log
    from fastapi import BackgroundTasks

    scheduler = AsyncIOScheduler()

    async def scheduled_job():
        log("⏰ CRON: Starting automated daily job for all sectors...")
        for sector in SECTOR_KEYWORDS.keys():
            try:
                # We simulate a background task context here
                bg = BackgroundTasks()
                await start_automated_daily(
                    AutomatedScrapeRequest(sector=sector, region="india"),
                    bg
                )
                log(f"✅ CRON: Queued {sector} for India region.")
            except Exception as e:
                log(f"❌ CRON: Failed to queue {sector}: {e}")

    # Run every day at 3:00 AM
    scheduler.add_job(scheduled_job, CronTrigger(hour=3, minute=0))
    scheduler.start()
    print("Scheduler started: Automated daily scrapes active (3:00 AM).")


app.include_router(scrape.router, prefix="/api/scrape", tags=["scraping"])
app.include_router(articles.router, prefix="/api/articles", tags=["articles"])
app.include_router(diagnostics.router, prefix="/api/diagnostics", tags=["diagnostics"])
app.include_router(brands.router, prefix="/api/brands", tags=["brands"])


@app.get("/")
def root():
    return {"status": "Global News Intelligence API is running", "version": "2.0.0"}


@app.get("/health")
async def health():
    from db.database import get_db
    try:
        async with get_db() as db:
            count = await db.fetchval("SELECT COUNT(*) FROM articles")
        return {"status": "healthy", "total_articles": count}
    except Exception as e:
        return {"status": "degraded", "error": str(e)}
