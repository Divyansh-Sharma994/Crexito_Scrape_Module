import asyncio
import os
from backend.db import database

async def main():
    await database.init_db()
    print('Database initialized')

if __name__ == '__main__':
    asyncio.run(main())
