import pytest
import asyncio
import json
from datetime import date
from db.database import get_db
from scraper.engine import update_phase_status, title_hash

# 1. Integration - Test Phase Updates
@pytest.mark.asyncio
async def test_update_phase_status():
    async with get_db() as db:
        job_id = "test-job-123"
        # Since it's a test run, we need to create the job record first to satisfy fkey/update constraints
        await db.execute("""
            INSERT INTO scrape_jobs (id, sector, region, date_from, date_to)
            VALUES ($1, 'technology', 'us', '2026-01-01', '2026-01-02')
        """, job_id)

        # Update phase
        await update_phase_status(db, job_id, "Discovery", "running")

        # Fetch back and parse JSON
        row = await db.fetchrow("SELECT phase_stats FROM scrape_jobs WHERE id=$1", job_id)
        assert row is not None
        stats = json.loads(row["phase_stats"])
        
        assert "Discovery" in stats
        assert stats["Discovery"]["status"] == "running"

        # Update again
        await update_phase_status(db, job_id, "Discovery", "completed")
        row2 = await db.fetchrow("SELECT phase_stats FROM scrape_jobs WHERE id=$1", job_id)
        stats2 = json.loads(row2["phase_stats"])
        assert stats2["Discovery"]["status"] == "completed"

# 2. Unit - Title Hashing dedup validation
def test_title_hash():
    # Title hashing should ignore casing and non-alphanumeric chars
    th1 = title_hash("Breaking: New AI Model Released!")
    th2 = title_hash("breaking new ai model released")
    assert th1 == th2

    th3 = title_hash("Different Title Entirely")
    assert th1 != th3
