import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from db.database import get_db

async def clean_errors():
    async with get_db() as db:
        await db.execute("DELETE FROM articles WHERE url LIKE 'chrome-error%'")
        print("Cleaned up chrome-error rows")

if __name__ == "__main__":
    asyncio.run(clean_errors())
