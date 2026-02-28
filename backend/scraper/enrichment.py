"""
Enrichment engine: Re-scrapes all articles that have bad/missing body text.
Handles:
  1. Google News redirect URLs (news.google.com/rss/articles/CBMi...)
  2. Blank / NULL bodies
  3. Junk content (< 80 words, Google News placeholder, JavaScript errors, paywalls)
"""

import asyncio
import os
import sys
import random
from datetime import datetime
from typing import Optional, List
import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from db.database import get_db
from concurrent.futures import ThreadPoolExecutor

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
LOG_FILE = "scraper.log"

def log(msg: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{timestamp} - [ENRICHMENT] {msg}\n")
        f.flush()
    print(f"ENRICHMENT: {msg}", file=sys.stderr)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:122.0) Gecko/20100101 Firefox/122.0",
]

# Junk patterns that mean we got a redirect/placeholder page instead of the article
JUNK_PATTERNS = [
    "google news",
    "continue reading in the app",
    "enable javascript",
    "consent.google",
    "please enable javascript",
    "subscribe to read",
    "you have reached your article limit",
    "this content is for subscribers",
    "access to this page has been denied",
    "403 forbidden",
    "404 not found",
    "page not found",
    "whatsapp\ntwitter\nfacebook\ne-mail",
    # CAPTCHA / anti-bot pages (archive.ph, Cloudflare, etc.)
    "one more step",
    "please complete the security check",
    "checking your browser",
    "ray id",
    "why do i have to complete a captcha",
    "hcaptcha",
    "recaptcha",
    "just a moment...",
    "attention required",
    "please verify you are a human",
    # Google bot-detection / CAPTCHA page (webcache bypass failure)
    "unusual traffic from your computer network",
    "our systems have detected unusual traffic",
    "the block will expire shortly",
    "webcache.googleusercontent.com",
    "requests coming from your computer network which appear to be in violation",
    # archive.ph anti-bot / failure pages
    "archive.ph/newest",
    "error 429",
    "too many requests",
    "rate limit exceeded",
]

def is_junk_body(body: Optional[str]) -> bool:
    """Returns True if the body text is missing or garbage."""
    if not body or len(body.strip()) < 100:
        return True
    word_count = len(body.split())
    if word_count < 80:
        return True
    body_lower = body.lower()
    return any(pat in body_lower for pat in JUNK_PATTERNS)


async def resolve_redirect_url(browser, url: str) -> str:
    """
    Follow Google News or Bing News redirect URLs using a real browser.
    """
    if "news.google.com" not in url and "bing.com/news/apiclick" not in url:
        return url
    
    context = None
    try:
        context = await browser.new_context(user_agent=random.choice(USER_AGENTS))
        page = await context.new_page()
        
        final_url = url
        
        # Intercept navigation events to capture the real destination URL
        async def handle_request(request):
            nonlocal final_url
            if request.resource_type == "document":
                req_url = request.url
                if "news.google.com" not in req_url and "bing.com/news/apiclick" not in req_url and "bing.com/identity" not in req_url and "login.live.com" not in req_url and req_url.startswith("http"):
                    final_url = req_url
        
        page.on("request", handle_request)
        
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(2500)  # Wait for JS redirects to fire
            current_url = page.url
            if "news.google.com" not in current_url and "bing.com/news/apiclick" not in current_url and "bing.com/identity" not in current_url and "login.live.com" not in current_url and current_url.startswith("http"):
                final_url = current_url
        except Exception:
            pass
        
        return final_url
    except Exception as e:
        log(f"Browser redirect resolution failed for {url[:60]}: {e}")
        return url
    finally:
        if context:
            await context.close()


def extract_body_from_html(html: str) -> str:
    """Parse HTML and extract the best article body text available."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "figure"]):
        tag.decompose()

    for sel in [
        "article",
        '[class*="article-body"]',
        '[class*="article-content"]',
        '[class*="story-body"]',
        '[class*="story-content"]',
        '[class*="post-content"]',
        '[class*="entry-content"]',
        '[itemprop="articleBody"]',
        "main",
        ".content",
    ]:
        el = soup.select_one(sel)
        if el:
            text = el.get_text(separator="\n", strip=True)
            if len(text) > 300:
                return text

    ps = soup.find_all("p")
    paragraphs = "\n".join(p.get_text(strip=True) for p in ps if len(p.get_text(strip=True)) > 50)
    if len(paragraphs) > 300:
        return paragraphs

    return soup.get_text(separator="\n", strip=True)


async def scrape_article_body(page, url: str) -> str:
    """Visit a URL with Playwright and extract clean article text."""
    try:
        await page.route("**/*", lambda r: r.continue_()
                         if r.request.resource_type in ("document", "xhr", "fetch")
                         else r.abort())
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(800)
        try:
            html = await page.content()
        except Exception:
            # If it's navigating, wait and fallback to evaluate
            await page.wait_for_timeout(2000)
            html = await page.evaluate("() => document.documentElement.outerHTML")
            
        return extract_body_from_html(html)
    except Exception as e:
        log(f"Playwright error on {url[:60]}: {type(e).__name__}: {e}")
        return ""


# ─── Paywall Bypass Waterfall ──────────────────────────────────────────────────

# Known paywall domains and their bypass strategies
PAYWALL_DOMAINS = [
    "economictimes.indiatimes.com", "livemint.com", "hindustantimes.com",
    "businessstandard.com", "thehindu.com", "financialexpress.com",
    "wsj.com", "ft.com", "bloomberg.com", "nytimes.com",
    "washingtonpost.com", "theguardian.com", "forbes.com",
    "businessinsider.com", "economist.com", "nature.com",
    "forbesindia.com", "telegraphindia.com", "dnaindia.com",
]

BYPASS_SERVICES = [
    # archive.ph — Cached snapshots of articles
    lambda url: f"https://archive.ph/newest/{url}",
    # removepaywall.com
    lambda url: f"https://www.removepaywall.com/{url}",
]

def is_paywall_domain(url: str) -> bool:
    """Check if a URL is from a known paywall site."""
    return any(domain in url for domain in PAYWALL_DOMAINS)

async def bypass_paywall(browser, url: str) -> str:
    """
    Paywall bypass waterfall strategy.
    Tries 2 bypass services in order, picks the one with most article words.
    Returns the best body text found, or empty string if all fail.
    """
    best_body = ""
    best_word_count = 0

    for i, make_bypass_url in enumerate(BYPASS_SERVICES):
        bypass_url = make_bypass_url(url)
        service_name = ["archive.ph", "removepaywall.com"][i]

        context = None
        try:
            context = await browser.new_context(user_agent=random.choice(USER_AGENTS))
            page = await context.new_page()

            # Allow all resource types for bypass services (they need to fully load)
            await page.goto(bypass_url, wait_until="domcontentloaded", timeout=25000)
            await page.wait_for_timeout(2000)  # Bypass sites need time to render
            try:
                html = await page.content()
            except Exception:
                await page.wait_for_timeout(2000)
                html = await page.evaluate("() => document.documentElement.outerHTML")
                
            body = extract_body_from_html(html)
            word_count = len(body.split()) if body else 0

            if word_count > best_word_count and not is_junk_body(body):
                best_body = body
                best_word_count = word_count
                log(f"  [{service_name}] Got {word_count} words for {url[:50]}")

            # If we get a solid result (>300 words), stop trying
            if best_word_count >= 300:
                break

        except Exception as e:
            log(f"  [{service_name}] Failed for {url[:50]}: {type(e).__name__}")
        finally:
            if context:
                await context.close()

    return best_body


async def fetch_with_paywall_bypass(browser, url: str) -> str:
    """
    Full body extraction strategy:
    1. Try direct scrape
    2. If junk/paywall → trigger bypass waterfall
    3. Return best result
    """
    # Step 1: Direct scrape
    context = await browser.new_context(user_agent=random.choice(USER_AGENTS))
    page = await context.new_page()
    try:
        body = await scrape_article_body(page, url)
    finally:
        await context.close()

    # Step 2: If direct scrape returned good content, use it
    if not is_junk_body(body) and len(body.split()) >= 150:
        return body

    # Step 3: Activate paywall bypass waterfall
    log(f"Activating paywall bypass for {url[:60]}")
    bypass_body = await bypass_paywall(browser, url)

    # Step 4: Return whichever has more content
    direct_words = len(body.split()) if body else 0
    bypass_words = len(bypass_body.split()) if bypass_body else 0

    if bypass_words > direct_words:
        log(f"Bypass won: {bypass_words} words vs {direct_words} direct for {url[:50]}")
        return bypass_body
    return body


async def summarize_with_groq(text: str, client: httpx.AsyncClient) -> Optional[str]:
    if not GROQ_API_KEY or not text or len(text) < 400:
        return None
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": "Summarize this news article in 3 bullet points. Max 60 words total."},
            {"role": "user", "content": text[:4000]},
        ],
        "max_tokens": 150,
    }
    for attempt in range(3):
        try:
            resp = await client.post(url, headers=headers, json=payload, timeout=15)
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            elif resp.status_code == 429:
                await asyncio.sleep(2 ** attempt)
            else:
                break
        except Exception as e:
            log(f"Groq error attempt {attempt+1}: {e}")
            await asyncio.sleep(1)
    return None


async def run_enrichment(job_id: Optional[str] = None, batch_size: int = 5000, concurrency: int = 35):
    """
    Main enrichment runner.
    Finds all articles with bad/missing body text and re-scrapes them.
    Uses Playwright to follow Google News JavaScript redirects to real publisher URLs.
    """
    log(f"Starting body enrichment run. Batch: {batch_size}, Concurrency: {concurrency}")

    async with get_db() as db:
        articles = await db.fetch(f"""
            SELECT id, url, title FROM articles
            WHERE (
                full_body IS NULL
                OR length(full_body) < 100
                OR lower(full_body) LIKE '%google news%'
                OR lower(full_body) LIKE '%continue reading in the app%'
                OR lower(full_body) LIKE '%enable javascript%'
                OR lower(full_body) LIKE '%consent.google%'
                OR lower(full_body) LIKE '%please enable javascript%'
                OR lower(full_body) LIKE '%subscribe to read%'
                OR lower(full_body) LIKE '%access to this page has been denied%'
                OR lower(full_body) LIKE '%unusual traffic from your computer%'
                OR lower(full_body) LIKE '%our systems have detected unusual traffic%'
                OR lower(full_body) LIKE '%webcache.googleusercontent.com%'
                OR lower(full_body) LIKE 'archive.ph%'
                OR (length(full_body) < 500 AND word_count < 80)
            )
            ORDER BY id ASC
            LIMIT $1
        """, batch_size)

    total = len(articles)
    log(f"Found {total} articles needing body enrichment.")

    if not articles:
        log("Nothing to enrich. All articles have good body text.")
        return {"enriched": 0, "failed": 0, "total": 0}

    enriched = 0
    failed = 0
    semaphore = asyncio.Semaphore(concurrency)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"]
        )
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as http_client:

            async def enrich_one(article):
                nonlocal enriched, failed
                async with semaphore:
                    art_id = article["id"]
                    raw_url = article["url"]

                    try:
                        # Step 1: Resolve redirect URLs → real publisher URL
                        real_url = await resolve_redirect_url(browser, raw_url)
                        if real_url != raw_url:
                            log(f"Resolved: {raw_url[:45]} → {real_url[:70]}")

                        # Step 2: Fetch body — direct scrape + paywall bypass waterfall
                        # Automatically tries 12ft.io, archive.ph, Google Cache, etc. if direct fails
                        body = await fetch_with_paywall_bypass(browser, real_url)

                        # Step 3: If still junk after all bypass attempts, count as failed
                        if is_junk_body(body):
                            log(f"Unrecoverable ID:{art_id} [{real_url[:55]}]")
                            failed += 1
                            return

                        # Step 4: Groq summary
                        summary = await summarize_with_groq(body, http_client)
                        word_count = len(body.split())

                        # Step 5: Update DB — store real URL if it was a redirect
                        async with get_db() as db:
                            await db.execute("""
                                UPDATE articles
                                SET full_body  = $1,
                                    summary    = CASE WHEN summary IS NULL THEN $2 ELSE summary END,
                                    word_count = $3,
                                    url        = $4
                                WHERE id = $5
                            """, body, summary, word_count, real_url, art_id)

                        enriched += 1

                    except Exception as e:
                        log(f"ERROR enriching ID:{art_id} {raw_url[:50]}: {type(e).__name__}: {e}")
                        failed += 1

            # Process in batches of 500 to keep memory stable
            batch_size_inner = 500
            for i in range(0, len(articles), batch_size_inner):
                batch = articles[i:i + batch_size_inner]
                
                # Internal counter to update DB more frequently than the full batch
                sub_count = 0
                async def tracked_enrich(a):
                    nonlocal sub_count
                    await enrich_one(a)
                    sub_count += 1
                    if sub_count % 10 == 0:
                        if job_id:
                            try:
                                async with get_db() as prog_db:
                                    await prog_db.execute(
                                        "UPDATE scrape_jobs SET total_scraped=$1 WHERE id=$2",
                                        enriched + failed, job_id
                                    )
                            except Exception:
                                pass

                tasks = [tracked_enrich(a) for a in batch]
                try:
                    # Give a batch of 500 a generous 45-minute hard timeout before forcing a move to the next batch
                    await asyncio.wait_for(asyncio.gather(*tasks), timeout=2700)
                except asyncio.TimeoutError:
                    log(f"BATCH TIMEOUT: Moving to next batch after 45 mins. Progress: {enriched + failed}/{total}")
                
                log(f"Batch {i // batch_size_inner + 1} done. Total processed: {enriched + failed}/{total}")
                
                # Final catch-up update for the batch
                if job_id:
                    try:
                        async with get_db() as prog_db:
                            await prog_db.execute(
                                "UPDATE scrape_jobs SET total_scraped=$1 WHERE id=$2",
                                enriched + failed, job_id
                            )
                    except Exception:
                        pass

        await browser.close()
    
    # Final status update
    if job_id:
        async with get_db() as db:
            await db.execute(
                "UPDATE scrape_jobs SET status='completed', completed_at=CURRENT_TIMESTAMP, total_scraped=$1 WHERE id=$2",
                enriched + failed, job_id
            )

    log(f"✅ Enrichment complete: {enriched} enriched, {failed} irretrievable, out of {total} total.")
    return {"enriched": enriched, "failed": failed, "total": total}

