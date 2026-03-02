import asyncio
import sys
import os
import httpx
from playwright.async_api import async_playwright
from db.database import get_db, init_db
from scraper.enrichment import resolve_redirect_url, fetch_with_paywall_bypass, extract_author_from_html
from scraper.engine import title_hash

async def test_db():
    print("Testing Database connection...")
    try:
        await init_db()
        async with get_db() as db:
            res = await db.fetchval("SELECT 1")
            if res == 1:
                print("✅ Database connection OK.")
            else:
                print("❌ Database returned unexpected value.")
    except Exception as e:
        print(f"❌ Database connection FAILED: {e}")

async def test_browser():
    print("Testing Playwright + Stealth...")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
            context = await browser.new_context()
            page = await context.new_page()
            
            # Test stealth
            from playwright_stealth import Stealth
            await Stealth().apply_stealth_async(page)
            
            await page.goto("https://bot.sannysoft.com/", wait_until="networkidle")
            # We don't need to check results, just ensure it doesn't crash
            print("✅ Playwright + Stealth initialized OK.")
            await browser.close()
    except Exception as e:
        print(f"❌ Playwright + Stealth FAILED: {e}")

async def test_redirect_resolution():
    print("Testing Google News redirect resolution...")
    # A known Google News URL (if possible)
    test_url = "https://news.google.com/rss/articles/CBMiRGh0dHBzOi8vd3d3LmNuYmMuY29tLzIwMjQvMDMvMDIvYXBwbGUtY2FuY2VscS1lbGVjdHJpYy1jYXItcHJvamVjdC5odG1s0gFIaHR0cHM6Ly93d3cuY25iYy5jb20vYW1wLzIwMjQvMDMvMDIvYXBwbGUtY2FuY2VscS1lbGVjdHJpYy1jYXItcHJvamVjdC5odG1s?oc=5"
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
            res = await resolve_redirect_url(browser, test_url)
            if "cnbc.com" in res:
                print(f"✅ Redirect resolution OK: {res}")
            else:
                print(f"❌ Redirect resolution returned unexpected URL: {res}")
            await browser.close()
    except Exception as e:
        print(f"❌ Redirect resolution FAILED: {e}")

async def test_enrichment_logic():
    print("Testing Enrichment logic (trafilatura + author extraction)...")
    html = """
    <html>
        <head>
            <meta name="author" content="John Doe">
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "NewsArticle",
                "author": {"@type": "Person", "name": "Jane Smith"},
                "articleBody": "This is a very long article body that should be extracted correctly. """ + "word " * 500 + """"
            }
            </script>
        </head>
        <body>
            <article>
                <p>Real content starts here.</p>
            </article>
        </body>
    </html>
    """
    from scraper.enrichment import extract_body_from_html, extract_author_from_html
    body = extract_body_from_html(html)
    author = extract_author_from_html(html)
    
    if "Real content" in body or "word" in body:
        print("✅ Body extraction OK.")
    else:
        print(f"❌ Body extraction FAILED: {body[:100]}...")
        
    if author == "Jane Smith" or author == "John Doe":
        print(f"✅ Author extraction OK: {author}")
    else:
        print(f"❌ Author extraction FAILED: {author}")

async def main():
    print("=== STARTING INTEGRATION TESTS ===")
    await test_db()
    await test_browser()
    await test_redirect_resolution()
    await test_enrichment_logic()
    print("=== TESTS COMPLETE ===")

if __name__ == "__main__":
    asyncio.run(main())
