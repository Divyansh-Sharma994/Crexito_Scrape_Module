"""
Distributed CLI Runner for News Intelligence Scraper.
Supports:
  1. Discovery Phase: Finds URLs and seeds the Database.
  2. Scrape Phase: Picks a chunk of pending articles and extracts content + summary.
"""

import sys
import asyncio
import argparse
from datetime import datetime, date
from scraper.engine import run_scrape_job, discover_articles, SECTOR_KEYWORDS, SEARCH_MODIFIERS, REGION_MAP, scrape_and_analyze
from db.database import get_db, init_db
import httpx
from playwright.async_api import async_playwright

from datetime import datetime, date, timedelta

async def run_discovery(sector: str, region: str, date_from_str: str, date_to_str: str):
    await init_db()
    date_from = date.fromisoformat(date_from_str)
    date_to = date.fromisoformat(date_to_str)
    
    keywords = SECTOR_KEYWORDS.get(sector.lower(), [sector])
    queries = []
    for kw in keywords:
        for mod in SEARCH_MODIFIERS: queries.append(f'"{kw}" {mod} {region}')
        for city in REGION_MAP.get(region.lower(), {}).get("cities", []): queries.append(f'"{kw}" {city}')

    geo = REGION_MAP.get(region.lower(), {"geo": "US"})["geo"]
    
    all_discovered = []
    current_day = date_from
    while current_day <= date_to:
        discovered = await discover_articles(queries, current_day, geo)
        all_discovered.extend(discovered)
        current_day += timedelta(days=1)
    
    print(f"DISCOVERY_COUNT={len(all_discovered)}")
    
    async with get_db() as db:
        job_id = f"dist-{int(datetime.now().timestamp())}"
        await db.execute("INSERT INTO scrape_jobs (id, sector, region, date_from, date_to, status, total_found) VALUES ($1,$2,$3,$4,$5,$6,$7)",
                         job_id, sector, region, date_from_str, date_to_str, f"discovery_complete", len(all_discovered))
        
        for article in all_discovered:
            await db.execute("""
                INSERT INTO articles (title, url, agency, published_at, sector, region, scrape_job_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7) ON CONFLICT (url) DO NOTHING
            """, article["title"], article["url"], article["agency"], article["published_at"], sector, region, job_id)
    
    print(f"JOB_ID={job_id}")

async def run_worker(job_id: str, chunk_index: int, total_chunks: int):
    await init_db()
    async with get_db() as db:
        # Fetch a slice of articles for this job that haven't been scraped yet
        all_pending = await db.fetch("SELECT * FROM articles WHERE scrape_job_id=$1 AND full_body IS NULL", job_id)
        
        chunk_size = len(all_pending) // total_chunks
        start = chunk_index * chunk_size
        end = start + chunk_size if chunk_index < total_chunks - 1 else len(all_pending)
        
        my_chunk = all_pending[start:end]
        print(f"Worker {chunk_index}/{total_chunks} picking up {len(my_chunk)} articles.")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
            async with httpx.AsyncClient() as groq_client:
                # Higher concurrency for cloud workers
                semaphore = asyncio.Semaphore(10)
                scraped_counter = [0]
                
                async def sem_scrape(article):
                    async with semaphore:
                        await scrape_and_analyze(article, browser, db, job_id, article["sector"], article["region"], groq_client, scraped_counter)
                
                tasks = [sem_scrape(a) for a in my_chunk]
                await asyncio.gather(*tasks)
            await browser.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["discovery", "worker"], required=True)
    parser.add_argument("--sector", default="artificial intelligence")
    parser.add_argument("--region", default="india")
    parser.add_argument("--date_from", default=date.today().isoformat())
    parser.add_argument("--date_to", default=date.today().isoformat())
    parser.add_argument("--job_id", help="Job ID for workers")
    parser.add_argument("--index", type=int, help="Matrix chunk index")
    parser.add_argument("--total", type=int, help="Total Matrix chunks")
    
    args = parser.parse_args()
    
    if args.mode == "discovery":
        asyncio.run(run_discovery(args.sector, args.region, args.date_from, args.date_to))
    elif args.mode == "worker":
        if not args.job_id: print("Error: job_id required for workers"); sys.exit(1)
        asyncio.run(run_worker(args.job_id, args.index, args.total))
