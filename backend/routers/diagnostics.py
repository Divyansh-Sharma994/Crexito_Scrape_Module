import os
import httpx
from fastapi import APIRouter
from db.database import get_db

router = APIRouter()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

@router.get("/health")
async def get_system_health():
    """Returns real-time diagnostics of all core services and recent logs."""
    status = {
        "database": {"status": "unknown"}, 
        "groq_api": {"status": "unknown"}, 
        "playwright": {"status": "unknown"}, 
        "jobs": {"status": "unknown"}
    }
    overall = "healthy"
    
    # 1. Database Check
    try:
        async with get_db() as db:
            await db.execute("SELECT 1")
        status["database"] = {"status": "online", "message": "Connected and responding"}
    except Exception as e:
        status["database"] = {"status": "offline", "message": str(e)}
        overall = "degraded"

    # 2. Groq API Check (Live check to retrieve rate limits)
    if GROQ_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # Do a minimal 5-token ping to grab rate limit headers without wasting much cost
                res = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                    json={"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": "ping"}], "max_tokens": 5}
                )
                headers = res.headers
                
                if res.status_code == 200:
                    status["groq_api"] = {
                        "status": "online",
                        "remaining_reqs": headers.get("x-ratelimit-remaining-requests", "N/A"),
                        "remaining_tokens": headers.get("x-ratelimit-remaining-tokens", "N/A"),
                        "reset_reqs": headers.get("x-ratelimit-reset-requests", "N/A"),
                        "reset_tokens": headers.get("x-ratelimit-reset-tokens", "N/A"),
                        "message": "Connected and authenticated"
                    }
                elif res.status_code == 429:
                    status["groq_api"] = {
                        "status": "rate_limited",
                        "reset_reqs": headers.get("x-ratelimit-reset-requests", "N/A"),
                        "reset_tokens": headers.get("x-ratelimit-reset-tokens", "N/A"),
                        "message": "Currently Rate Limited (429)"
                    }
                    overall = "degraded"
                else:
                    status["groq_api"] = {"status": "error", "message": f"HTTP {res.status_code}: {res.text[:100]}"}
                    overall = "degraded"
        except Exception as e:
            status["groq_api"] = {"status": "offline", "message": str(e)}
            overall = "degraded"
    else:
        status["groq_api"] = {"status": "offline", "message": "GROQ_API_KEY environment variable missing"}
        overall = "degraded"

    # 3. Playwright Engine Check
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            # Test a rapid headless launch to ensure dependencies exist and aren't zombied
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"]
            )
            await browser.close()
            status["playwright"] = {"status": "online", "message": "Chromium engine healthy"}
    except Exception as e:
        status["playwright"] = {"status": "offline", "message": str(e)}
        overall = "degraded"

    # 4. Jobs / Workers Check
    try:
        async with get_db() as db:
            failed = await db.fetchval("SELECT COUNT(*) FROM scrape_jobs WHERE status IN ('failed', 'interrupted', 'partial')")
            running = await db.fetchval("SELECT COUNT(*) FROM scrape_jobs WHERE status = 'running'")
            total = await db.fetchval("SELECT COUNT(*) FROM scrape_jobs")
            
            job_status = "online"
            msg = "All workers healthy"
            if failed > 0:
                if (failed / max(total, 1)) > 0.3:
                    job_status = "degraded"
                    overall = "degraded"
                msg = f"{failed} jobs encountered errors. {running} jobs currently queued/running."
                
            status["jobs"] = {
                "status": job_status,
                "failed_count": failed,
                "running_count": running,
                "message": msg
            }
    except Exception:
        pass
        
    # 5. Fast-tail system logs for recent anomalies 
    recent_errors = []
    try:
        # Check the last 1MB of the scraper log instead of loading the whole 15MB file into RAM
        log_path = "scraper.log"
        if os.path.exists(log_path):
            file_size = os.path.getsize(log_path)
            read_size = min(file_size, 1024 * 1024) # read max 1MB
            
            with open(log_path, "rb") as f:
                f.seek(-read_size, os.SEEK_END)
                lines = f.read().decode("utf-8", errors="ignore").splitlines()
                
                # Reverse look for error-indicating lines
                for line in reversed(lines):
                    lower = line.lower()
                    if "error" in lower or "fatal" in lower or "limit" in lower or "failed" in lower or "warning" in lower:
                        recent_errors.append(line.strip())
                    if len(recent_errors) >= 30: # Max 30 recent error lines
                        break
    except Exception:
        pass

    return {
        "overall": overall,
        "components": status,
        "recent_log_errors": recent_errors
    }
