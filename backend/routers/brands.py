import uuid
from datetime import date, timedelta
from typing import List
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from db.database import get_db
from scraper.engine import run_brand_scrape

router = APIRouter()

class BrandRequest(BaseModel):
    name: str

@router.get("/")
async def get_brands():
    """List all watched brands."""
    async with get_db() as db:
        return await db.fetch("SELECT * FROM watched_brands ORDER BY name ASC")

@router.post("/")
async def add_brand(req: BrandRequest):
    """Add a new brand to watch list."""
    async with get_db() as db:
        try:
            await db.execute("INSERT INTO watched_brands (name) VALUES ($1)", req.name)
            return {"status": "success", "brand": req.name}
        except Exception as e:
            if "UNIQUE" in str(e) or "already exists" in str(e).lower():
                raise HTTPException(400, "Brand already being watched")
            raise HTTPException(500, str(e))

@router.delete("/{name}")
async def delete_brand(name: str):
    """Stop watching a brand."""
    async with get_db() as db:
        await db.execute("DELETE FROM watched_brands WHERE name=$1", name)
        return {"status": "deleted", "brand": name}

@router.post("/scrape")
async def trigger_brand_scrape(background_tasks: BackgroundTasks, region: str = "india", days: int = 1):
    """Trigger a scrape for all watched brands."""
    async with get_db() as db:
        brands = await db.fetch("SELECT name FROM watched_brands")
        if not brands:
            raise HTTPException(400, "No brands to scrape. Add some first.")
        
        brand_list = [b["name"] for b in brands]
        
        # Guard: check running jobs
        already_running = await db.fetchval(
            "SELECT COUNT(*) FROM scrape_jobs WHERE status='running' AND sector != '__enrichment__'"
        )
        if already_running >= 2:
            raise HTTPException(409, "Server busy. Try again later.")

        job_id = str(uuid.uuid4())
        date_to = date.today()
        date_from = date_to - timedelta(days=days)

        await db.execute("""
            INSERT INTO scrape_jobs (id, sector, region, date_from, date_to, status)
            VALUES ($1, $2, $3, $4, $5, 'pending')
        """, job_id, "brand_tracker", region, date_from, date_to)

        background_tasks.add_task(
            run_brand_scrape,
            job_id=job_id,
            brands=brand_list,
            region=region,
            date_from=date_from,
            date_to=date_to
        )

        return {"job_id": job_id, "status": "queued", "brands": brand_list}
