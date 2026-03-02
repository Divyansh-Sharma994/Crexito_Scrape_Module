import asyncio
import os
import random
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

async def main():
    print("Launching playwright...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled"
            ]
        )
        print("Browser launched.")
        for i in range(5):
            print(f"Test {i}...")
            context = await browser.new_context()
            page = await context.new_page()
            await Stealth().apply_stealth_async(page)
            print(f"Stealth applied {i}.")
            try:
                await page.goto("https://bot.sannysoft.com/", timeout=10000)
                print(f"Page loaded {i}.")
            except Exception as e:
                print(f"Error {i}: {e}")
            finally:
                await context.close()
        await browser.close()
        print("Done.")

if __name__ == "__main__":
    asyncio.run(main())
