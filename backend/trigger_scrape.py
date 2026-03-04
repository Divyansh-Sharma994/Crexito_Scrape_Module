import httpx
import asyncio
import json

async def main():
    url = "http://localhost:8000/api/scrape/start"
    payload = {
        "sector": "artificial intelligence",
        "region": "india",
        "date_from": "2026-03-04",
        "date_to": "2026-03-04",
        "search_mode": "broad"
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload)
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.json()}")

if __name__ == "__main__":
    asyncio.run(main())
