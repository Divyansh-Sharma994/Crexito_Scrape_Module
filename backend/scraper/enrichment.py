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

GROQ_API_KEYS = [k.strip() for k in os.getenv("GROQ_API_KEY", "").split(",") if k.strip()]

LOG_FILE = "scraper.log"

def decode_google_news_url(url: str) -> Optional[str]:
    try:
        if "/articles/" not in url: return None
        encoded = url.split("/articles/")[1].split("?")[0]
        padded = encoded + "=="
        decoded = base64.urlsafe_b64decode(padded)
        match = re.search(rb"https?://[^\x00-\x1F\x7F]+", decoded)
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
    "too many requests", "rate limit exceeded",
]

def is_junk_body(body: Optional[str]) -> bool:
    if not body or len(body.strip()) < 100: return True
    word_count = len(body.split())
    if word_count < 80: return True
    body_lower = body.lower()
    return any(pat in body_lower for pat in JUNK_PATTERNS)

async def resolve_redirect_url(browser, url: str) -> str:
    """Follow Google/Bing redirects to real publisher URL."""
    if "news.google.com/rss/articles/" in url:
        return decode_google_news_url(url) or url

    if "bing.com/news/apiclick" not in url:
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

        # 3. CSS Selectors
        for sel in [".author", ".byline", ".entry-author", ".article-author", '[rel="author"]']:
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

    # 4. Fallback BeautifulSoup
    try:
        soup = BeautifulSoup(html, "lxml")
        for t in soup(["script", "style", "nav", "footer", "header", "aside"]): t.decompose()
        for sel in ["article", '[class*="article-body"]', '[class*="story-body"]', "main"]:
            el = soup.select_one(sel)
            if el:
                txt = el.get_text(separator="\n", strip=True)
                if len(txt) > 400: return txt
    except: pass
    return ""

async def scrape_full_data(page, url: str) -> Dict[str, str]:
    """Scrape both text and HTML from a URL."""
    try:
        await page.route("**/*", lambda r: r.continue_() if r.request.resource_type in ("document", "xhr", "fetch") else r.abort())
        await page.goto(url, wait_until="domcontentloaded", timeout=25000)
        await page.wait_for_timeout(1500)
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
            await page.goto(target, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)
            html = await page.content()
            txt = extract_body_from_html(html)
            if len(txt) > len(best["text"]):
                best = {"text": txt, "html": html}
            if len(txt) > 600: break
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

    if not is_junk_body(res["text"]) and len(res["text"].split()) > 200:
        return res
    
    # Bypass
    log(f"Activating bypass for {url[:50]}")
    bypass_res = await bypass_paywall(browser, url)
    if len(bypass_res["text"]) > len(res["text"]):
        return bypass_res
    return res

async def summarize_with_groq(text: str, client: httpx.AsyncClient) -> Optional[str]:
    if not GROQ_API_KEYS or not text or len(text) < 400: return None
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "system", "content": "Summarize this news article in 3 bullet points. Max 60 words total."},
                     {"role": "user", "content": text[:5000]}],
        "max_tokens": 150,
    }
    for attempt in range(2):
        key = random.choice(GROQ_API_KEYS)
        try:
            r = await client.post("https://api.groq.com/openai/v1/chat/completions",
                                  headers={"Authorization": f"Bearer {key}"}, json=payload, timeout=20)
            if r.status_code == 200: return r.json()["choices"][0]["message"]["content"]
            await asyncio.sleep(2)
        except: continue
    return None

async def run_enrichment(job_id: Optional[str] = None, batch_size: int = 1000):
    log(f"Starting enrichment. Batch size: {batch_size}")
    async with get_db() as db:
        articles = await db.fetch("""
            SELECT id, url FROM articles
            WHERE full_body IS NULL OR length(full_body) < 150 OR lower(full_body) LIKE '%javascript%'
            ORDER BY id DESC LIMIT $1
        """, batch_size)
    
    if not articles:
        log("No articles to enrich.")
        return {"enriched":0, "failed":0}

    enriched = 0
    failed = 0
    semaphore = asyncio.Semaphore(8) # Reduced for extreme stability
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
                    browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"])
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
                            log(f"Failed ID:{art_id} - Junk content")
                            failed += 1
                            return

                        # 3. Analyze
                        author = extract_author_from_html(data["html"])
                        summary = await summarize_with_groq(data["text"], http_client)
                        words = len(data["text"].split())
                        
                        async with get_db() as db:
                            await db.execute("""
                                UPDATE articles SET full_body=$1, summary=$2, author=$3, word_count=$4, url=$5
                                WHERE id=$6
                            """, data["text"], summary, author, words, real_url, art_id)
                        
                        enriched += 1
                        if enriched % 10 == 0: log(f"Progress: {enriched} enriched, {failed} failed")
                        
                    except Exception as e:
                        err_msg = str(e)
                        if "Target page, context or browser has been closed" in err_msg or "TargetClosed" in err_msg:
                            browser_restart_needed = True
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
