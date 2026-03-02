import asyncio
from db.database import get_db

async def check():
    async with get_db() as db:
        rows = await db.fetch("SELECT id, author, substr(full_body, 1, 100) as snippet FROM articles WHERE full_body IS NOT NULL LIMIT 5")
        for row in rows:
            print(f"ID: {row['id']}")
            print(f"Author: {row['author']}")
            print(f"Snippet: {row['snippet']}")
            print("-" * 20)

if __name__ == "__main__":
    asyncio.run(check())
