import asyncio
import os
from playwright.async_api import async_playwright

async def _preflight_check():
    try:
        async with async_playwright() as p:
            print("Launching chromium with new logic...")
            args = ["--disable-dev-shm-usage"] if os.name != "nt" else []
            browser = await p.chromium.launch(
                headless=True,
                args=args
            )
            print("Browser launched.")
            await browser.close()
        return True
    except Exception as e:
        import traceback
        print(f"PRE-FLIGHT FAILED: {type(e).__name__}: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(_preflight_check())
    print(f"Result: {result}")
