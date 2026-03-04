import asyncio
import os
import sys
from scraper.llm import extract_metadata_with_ollama, verify_agency_with_ollama
from scraper.enrichment import decode_google_news_url, resolve_redirect_url, fetch_with_paywall_bypass
from playwright.async_api import async_playwright

async def verify_quality(test_url: str):
    print(f"--- Verification for URL: {test_url} ---")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # 1. Resolve redirect
        print("Resolving redirect...")
        real_url = await resolve_redirect_url(browser, test_url)
        print(f"Real URL: {real_url}")
        
        # 2. Fetch content
        print("Fetching content (Trafilatura)...")
        data = await fetch_with_paywall_bypass(browser, real_url)
        raw_text = data.get("text", "")
        print(f"Raw Text Length: {len(raw_text)}")
        
        # 3. Ollama Metadata & Cleaning
        print("Processing with Ollama (Metadata + Cleaning)...")
        res = await extract_metadata_with_ollama(raw_text)
        
        author = res.get("author")
        agency = res.get("agency")
        cleaned_body = res.get("cleaned_body", "")
        
        # 4. Verify Agency if generic
        if agency and "google" in agency.lower():
            print("Generic agency detected, re-verifying...")
            agency = await verify_agency_with_ollama(cleaned_body, agency)
            
        print("\n=== RESULTS ===")
        print(f"Author: {author}")
        print(f"Agency: {agency}")
        print(f"Cleaned Body Length: {len(cleaned_body)}")
        print(f"Snippet: {cleaned_body[:200]}...")
        print("===============")
        
        await browser.close()

if __name__ == "__main__":
    # Use the URL found in previous step or a hardcoded one
    url = sys.argv[1] if len(sys.argv) > 1 else "https://news.google.com/rss/articles/CBMisAFBVV95cUxPZlRfR2F1dXZrLUZZY2RWY0YyQUVzS1ltRFNFUVY3cWlkZjRhX2hncXhCem1BWHJ0b1M0XzNGeS1tVWhzQ25XMVExTzRSZ1lEazhXUkNFSWlFZmR3SzhfMWZxeGowQ0dNVTljX3FrclNjczZtVnphYkI0bmZpNWxMMm44RXRKdk9jM3pEcF92XzV4YzhreHdndC02bmR1bURVdnkzS0R6M04zczE0b0ZaS29zeDk?oc=5"
    asyncio.run(verify_quality(url))
