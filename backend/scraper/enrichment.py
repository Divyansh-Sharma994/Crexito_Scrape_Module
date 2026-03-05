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
import json
import trafilatura
import base64
import re
from datetime import datetime
from typing import Optional, List, Dict
import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from db.database import get_db
from scraper.llm import summarize_with_groq, extract_metadata_with_ollama, verify_agency_with_ollama

GROQ_API_KEYS = [k.strip() for k in os.getenv("GROQ_API_KEY", "").split(",") if k.strip()]

LOG_FILE = "scraper.log"

def decode_google_news_url(url: str) -> Optional[str]:
    try:
        if "/articles/" not in url: return None
        encoded = url.split("/articles/")[1].split("?")[0]
        padded = encoded + "=="
        decoded = base64.urlsafe_b64decode(padded)
        match = re.search(rb"https?://[a-zA-Z0-9\-\.\_\~\:\/\?\#\[\]\@\!\$\&\'\(\)\*\+\,\;\=\%]+", decoded)
        if match:
            return match.group(0).decode("utf-8", errors="ignore")
    except Exception as e:
        pass
    return None

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
]

JUNK_PATTERNS = [
    "google news", "continue reading in the app", "enable javascript", "consent.google",
    "please enable javascript", "subscribe to read", "you have reached your article limit",
    "this content is for subscribers", "access to this page has been denied", "403 forbidden",
    "404 not found", "page not found", "whatsapp\ntwitter\nfacebook\ne-mail",
    "one more step", "please complete the security check", "checking your browser",
    "ray id", "why do i have to complete a captcha", "hcaptcha", "recaptcha",
    "just a moment...", "attention required", "please verify you are a human",
    "unusual traffic from your computer network", "our systems have detected unusual traffic",
    "the block will expire shortly", "webcache.googleusercontent.com",
    "requests coming from your computer network", "archive.ph/newest", "error 429",
    "too many requests", "rate limit exceeded", "detected unusual traffic",
    "access denied", "robot check", "captcha", "security challenge",
    "javascript is disabled", "please turn on javascript",
    "cookies are disabled", "enable cookies to continue",
]

def is_junk_body(body: Optional[str]) -> bool:
    """Extremely permissive: keep almost everything for future sentiment analysis."""
    if not body or len(body.strip()) < 5: 
        return True
    return False

async def resolve_redirect_url(browser, url: str) -> str:
    """Follow Google/Bing redirects to real publisher URL."""
    if "news.google.com/rss/articles/" in url:
        decoded = decode_google_news_url(url)
        if decoded:
            return decoded
        # fallback to Playwright below if decoding fails

    if "bing.com/news/apiclick" not in url and "news.google.com/rss/articles/" not in url:
        return url
    
    context = None
    try:
        context = await browser.new_context(user_agent=random.choice(USER_AGENTS))
        page = await context.new_page()
        await Stealth().apply_stealth_async(page)
        
        final_url = url
        
        def handle_request(request):
            nonlocal final_url
            if request.resource_type == "document":
                # Only update if it's a real site, not another redirector
                u = request.url
                if all(x not in u for x in ["news.google.com", "apiclick", "identity", "login.live.com"]) and u.startswith("http"):
                    final_url = u
        
        page.on("request", handle_request)
        
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(3000)
            curr = page.url
            if all(x not in curr for x in ["news.google.com", "apiclick", "identity", "login.live.com"]) and curr.startswith("http"):
                final_url = curr
        except: pass
        
        return final_url
    except Exception as e:
        log(f"Redirect resolution failed: {e}")
        return url
    finally:
        if context: await context.close()

def clean_author_text(text: Optional[str]) -> Optional[str]:
    if not text: return None
    text = text.strip()
    if text.startswith('{') or text.startswith('[') or 'function(' in text or 'var ' in text: return None
    if len(text) > 120 or '\n' in text: return None
    if text.lower() in ["admin", "staff", "editor", "contributor", "corporate", "none", "null"]: return None
    return text

def extract_author_from_html(html: str) -> Optional[str]:
    try:
        soup = BeautifulSoup(html, "lxml")
        # 1. JSON-LD
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if item.get("@type") in ["Article", "NewsArticle", "BlogPosting", "WebPage"]:
                        auth_data = item.get("author")
                        if isinstance(auth_data, dict):
                            res = clean_author_text(auth_data.get("name"))
                            if res: return res
                        elif isinstance(auth_data, list) and auth_data:
                            for a in auth_data:
                                name = a.get("name") if isinstance(a, dict) else a
                                res = clean_author_text(name)
                                if res: return res
                        elif isinstance(auth_data, str):
                            res = clean_author_text(auth_data)
                            if res: return res
            except: continue
        
        # 2. Meta Tags
        for attr in ["name", "property"]:
            for val in ["author", "article:author", "og:article:author", "dc.creator", "sailthru.author"]:
                tag = soup.find("meta", {attr: val})
                if tag and tag.get("content"):
                    res = clean_author_text(tag["content"])
                    if res: return res

        # 3. CSS Selectors (Common patterns used globally)
        for sel in [
            ".author", ".byline", ".entry-author", ".article-author", '[rel="author"]',
            '[class*="author-name"]', '[class*="byline-name"]', '.p-author', '.p-name',
            '[itemprop="author"] .name', '.article__author-name', '.caas-author-byline'
        ]:
            el = soup.select_one(sel)
            if el:
                res = clean_author_text(el.get_text(strip=True))
                if res: return res
    except: pass
    return None

def extract_body_from_html(html: str) -> str:
    # 1. Trafilatura bare extraction
    try:
        res = trafilatura.bare_extraction(html)
        if res and res.get('text') and len(res.get('text')) > 400:
            return res.get('text')
    except: pass

    # 2. JSON-LD articleBody
    try:
        soup = BeautifulSoup(html, "lxml")
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if item.get("@type") in ["Article", "NewsArticle", "BlogPosting"]:
                        body = item.get("articleBody")
                        if body and len(body) > 400: return body
            except: continue
    except: pass

    # 3. Trafilatura standard
    try:
        ext = trafilatura.extract(html, include_comments=False, no_fallback=False)
        if ext and len(ext) > 400: return ext
    except: pass

    # 4. Fallback BeautifulSoup (More aggressive)
    try:
        soup = BeautifulSoup(html, "lxml")
        for t in soup(["script", "style", "nav", "footer", "header", "aside", "svg", "form"]): t.decompose()
        # Find the div with the most paragraphs
        best_div = None
        max_p = 0
        for div in soup.find_all(["div", "article", "section"]):
            p_count = len(div.find_all("p"))
            if p_count > max_p:
                max_p = p_count
                best_div = div
        
        if best_div:
            txt = best_div.get_text(separator="\n", strip=True)
            if len(txt) > 400: return txt
    except: pass
    return ""

async def scrape_full_data(page, url: str) -> Dict[str, str]:
    """Scrape both text and HTML from a URL."""
    try:
        await page.route("**/*", lambda r: r.continue_() if r.request.resource_type in ("document", "xhr", "fetch") else r.abort())
        await page.goto(url, wait_until="domcontentloaded", timeout=25000)
        await page.wait_for_timeout(1500)
    except Exception as e:
        log(f"Navigation timeout/error {url[:50]}: {e} - Attempting partial extraction")
        
    try:
        html = await page.content()
        return {"text": extract_body_from_html(html), "html": html}
    except Exception as e:
        log(f"Scrape error {url[:50]}: {e}")
        return {"text": "", "html": ""}

async def bypass_paywall(browser, url: str) -> Dict[str, str]:
    services = [
        ("archive.ph", lambda u: f"https://archive.ph/newest/{u}"),
        ("webcache", lambda u: f"https://webcache.googleusercontent.com/search?q=cache:{u}"),
    ]
    best = {"text": "", "html": ""}
    for name, make_url in services:
        target = make_url(url)
        context = None
        try:
            context = await browser.new_context(user_agent=random.choice(USER_AGENTS))
            page = await context.new_page()
            await Stealth().apply_stealth_async(page)
            try:
                await page.goto(target, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(3000)
            except Exception as e:
                log(f"Navigation timeout/error for bypass {name}: {e}")
            try:
                html = await page.content()
                txt = extract_body_from_html(html)
                if len(txt) > len(best["text"]):
                    best = {"text": txt, "html": html}
                if len(txt) > 600: break
            except Exception as e:
                log(f"Extraction error in bypass {name}: {e}")
        except Exception as e:
            log(f"Bypass {name} failed: {e}")
        finally:
            if context: await context.close()
    return best

async def fetch_with_paywall_bypass(browser, url: str) -> Dict[str, str]:
    """Try direct, then bypass."""
    # Direct
    context = await browser.new_context(user_agent=random.choice(USER_AGENTS))
    page = await context.new_page()
    await Stealth().apply_stealth_async(page)
    res = await scrape_full_data(page, url)
    await context.close()

    if not is_junk_body(res["text"]) and len(res["text"].split()) > 20: # Reduced from 200
        return res
    
    # Bypass
    log(f"Activating bypass for {url[:50]}")
    bypass_res = await bypass_paywall(browser, url)
    if len(bypass_res["text"]) > len(res["text"]):
        return bypass_res
    return res

# Removed redundant summarize_with_groq (now in llm.py)

async def run_enrichment(job_id: Optional[str] = None, batch_size: int = 1000, concurrency: int = 8):
    log(f"Starting enrichment. Batch size: {batch_size}, Concurrency: {concurrency}")
    async with get_db() as db:
        articles = await db.fetch("""
            SELECT id, url, title, agency FROM articles
            WHERE full_body IS NULL OR length(full_body) < 5 OR lower(full_body) LIKE '%javascript%'
            ORDER BY id DESC LIMIT $1
        """, batch_size)
    
    if not articles:
        log("No articles to enrich.")
        return {"enriched":0, "failed":0}

    enriched = 0
    failed = 0
    semaphore = asyncio.Semaphore(concurrency) 
    browser_lock = asyncio.Lock()
    
    browser_restart_needed = False
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"])
        
        async def get_healthy_browser():
            nonlocal browser, browser_restart_needed
            async with browser_lock:
                if not browser or not browser.is_connected() or browser_restart_needed:
                    log("Restarting browser due to crash or disconnect...")
                    try: await browser.close()
                    except: pass
                    browser = await p.chromium.launch(
                headless=True,
                args=["--disable-dev-shm-usage"] if os.name != "nt" else [] 
            )
                    browser_restart_needed = False
            return browser

        async with httpx.AsyncClient(timeout=30) as http_client:
            
            async def enrich_one(item):
                nonlocal enriched, failed, browser_restart_needed
                art_id = item["id"]
                raw_url = item["url"]
                
                async with semaphore:
                    # Health Check & Restart
                    active_browser = await get_healthy_browser()

                    try:
                        # 1. Resolve RSS
                        real_url = await resolve_redirect_url(active_browser, raw_url)
                        
                        # 2. Fetch Data
                        data = await fetch_with_paywall_bypass(active_browser, real_url)
                        
                        if is_junk_body(data["text"]):
                            word_count = len(data["text"].split())
                            char_count = len(data["text"])
                            log(f"Failed ID:{art_id} - Junk content ({word_count} words, {char_count} chars)")
                            failed += 1
                            return

                        # 3. Analyze
                        author = extract_author_from_html(data["html"])
                        agency = item.get("agency")
                        
                        # --- Ollama Magic ---
                        ollama_meta = await extract_metadata_with_ollama(data["text"], url=real_url, context_agency=item.get("agency", ""))
                        
                        # Use Ollama if heuristic failed or to verify
                        if not author and ollama_meta.get("author"):
                            author = ollama_meta["author"]
                        
                        if ollama_meta.get("agency"):
                            agency = ollama_meta["agency"]
                        
                        # Using raw extracted body to speed up (LLM cleaning is slow)
                        final_body = data["text"]
                        
                        # Double-check if agency looks like a redirector/generic
                        generic_agencies = ["google news", "bing news", "msn", "yahoo news", "google"]
                        if agency and any(gen in agency.lower() for gen in generic_agencies):
                            log(f"Agency '{agency}' looks generic. Verifying...")
                            agency = await verify_agency_with_ollama(final_body, agency)
                        
                        words = len(final_body.split())
                        summary = await summarize_with_groq(final_body) if words >= 50 else None
                        
                        async with get_db() as db:
                            await db.execute("""
                                UPDATE articles SET full_body=$1, summary=$2, author=$3, word_count=$4, url=$5, agency=$6
                                WHERE id=$7
                            """, final_body, summary, author, words, real_url, agency, art_id)
                        
                        enriched += 1
                        if enriched % 10 == 0: log(f"Progress: {enriched} enriched, {failed} failed")
                        
                    except Exception as e:
                        err_msg = str(e).lower()
                        # Catch connection closures, driver crashes, and socket errors to trigger a restart
                        if any(x in err_msg for x in ["closed", "driver", "socket", "target page", "context"]):
                            browser_restart_needed = True
                            log(f"⚠️ Browser crash detected. Queuing restart for next item...")
                        log(f"Error ID:{art_id}: {type(e).__name__}: {e}")
                        failed += 1

            # Process in sub-batches of 100
            for i in range(0, len(articles), 100):
                sub_batch = articles[i:i+100]
                tasks = [enrich_one(a) for a in sub_batch]
                await asyncio.gather(*tasks)
                
                # Update Job Table
                if job_id:
                    async with get_db() as db:
                        await db.execute("UPDATE scrape_jobs SET total_scraped=$1 WHERE id=$2", enriched+failed, job_id)

        await browser.close()

    if job_id:
        async with get_db() as db:
            await db.execute("UPDATE scrape_jobs SET status='completed', completed_at=CURRENT_TIMESTAMP WHERE id=$1", job_id)

    log(f"Enrichment Done: {enriched} success, {failed} failed.")
    return {"enriched": enriched, "failed": failed}
