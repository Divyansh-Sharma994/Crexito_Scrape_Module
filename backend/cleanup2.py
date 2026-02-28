import asyncio
import sys
import os

sys.path.insert(0, r"e:\MAVERICKS\Crexito_Scrape\backend")

from db.database import get_db

async def clean_errors():
    async with get_db() as db:
        await db.execute("DELETE FROM articles WHERE url LIKE '%chrome-error%'")
        # Ensure any failed payloads where the url wasn't overwritten are properly reprocessed
        await db.execute("UPDATE articles SET full_body = NULL WHERE word_count = 0")
        print("Cleaned up chrome-error rows")

if __name__ == "__main__":
    asyncio.run(clean_errors())
