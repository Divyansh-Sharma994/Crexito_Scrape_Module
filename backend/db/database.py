import os
import re
import asyncpg
import aiosqlite
from typing import Optional, Union, List, Any
from contextlib import asynccontextmanager

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///news_scraper.db")

_pg_pool: Optional[asyncpg.Pool] = None

# ─── Schema Definitions ────────────────────────────────────────────────────────

SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    url         TEXT UNIQUE NOT NULL,
    full_body   TEXT,
    author      TEXT,
    agency      TEXT,
    published_at TEXT,
    sector      TEXT NOT NULL,
    region      TEXT NOT NULL,
    language    TEXT DEFAULT 'en',
    scraped_at  TEXT DEFAULT CURRENT_TIMESTAMP,
    scrape_job_id TEXT,
    word_count  INTEGER,
    summary     TEXT,
    sentiment   TEXT,
    tags        TEXT,
    title_hash  TEXT
);
CREATE TABLE IF NOT EXISTS scrape_jobs (
    id          TEXT PRIMARY KEY,
    sector      TEXT NOT NULL,
    region      TEXT NOT NULL,
    date_from   TEXT NOT NULL,
    date_to     TEXT NOT NULL,
    status      TEXT DEFAULT 'pending',
    total_found INTEGER DEFAULT 0,
    total_scraped INTEGER DEFAULT 0,
    started_at  TEXT DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    error       TEXT
);

-- FIX #1: Indexes for fast filtering
CREATE INDEX IF NOT EXISTS idx_articles_sector       ON articles(sector);
CREATE INDEX IF NOT EXISTS idx_articles_region       ON articles(region);
CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles(published_at);
CREATE INDEX IF NOT EXISTS idx_articles_job          ON articles(scrape_job_id);
CREATE INDEX IF NOT EXISTS idx_articles_word_count   ON articles(word_count);
CREATE INDEX IF NOT EXISTS idx_articles_title_hash   ON articles(title_hash);
CREATE TABLE IF NOT EXISTS watched_brands (
    name        TEXT PRIMARY KEY,
    added_at    TEXT DEFAULT CURRENT_TIMESTAMP,
    last_scraped TEXT
);
-- FIX #1: Full-Text Search virtual table for fast body search
CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(title, full_body, content=articles, content_rowid=id);
"""

POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id          SERIAL PRIMARY KEY,
    title       TEXT NOT NULL,
    url         TEXT UNIQUE NOT NULL,
    full_body   TEXT,
    author      TEXT,
    agency      TEXT,
    published_at TIMESTAMPTZ,
    sector      TEXT NOT NULL,
    region      TEXT NOT NULL,
    language    TEXT DEFAULT 'en',
    scraped_at  TIMESTAMPTZ DEFAULT NOW(),
    scrape_job_id TEXT,
    word_count  INTEGER,
    summary     TEXT,
    sentiment   TEXT,
    tags        TEXT,
    title_hash  TEXT
);
CREATE TABLE IF NOT EXISTS scrape_jobs (
    id          TEXT PRIMARY KEY,
    sector      TEXT NOT NULL,
    region      TEXT NOT NULL,
    date_from   DATE NOT NULL,
    date_to     DATE NOT NULL,
    status      TEXT DEFAULT 'pending',
    total_found INTEGER DEFAULT 0,
    total_scraped INTEGER DEFAULT 0,
    started_at  TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    error       TEXT
);
CREATE INDEX IF NOT EXISTS idx_articles_sector       ON articles(sector);
CREATE INDEX IF NOT EXISTS idx_articles_region       ON articles(region);
CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles(published_at);
CREATE INDEX IF NOT EXISTS idx_articles_job          ON articles(scrape_job_id);
CREATE INDEX IF NOT EXISTS idx_articles_title_hash   ON articles(title_hash);
CREATE TABLE IF NOT EXISTS watched_brands (
    name        TEXT PRIMARY KEY,
    added_at    TIMESTAMPTZ DEFAULT NOW(),
    last_scraped TIMESTAMPTZ
);
"""

# ─── Init ─────────────────────────────────────────────────────────────────────

async def init_db():
    if DATABASE_URL.startswith("sqlite"):
        db_path = DATABASE_URL.replace("sqlite:///", "")
        async with aiosqlite.connect(db_path) as db:
            # FIX #5: Enable WAL mode for concurrent read/write without locking
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA synchronous=NORMAL")
            await db.execute("PRAGMA cache_size=-64000")  # 64MB cache
            await db.execute("PRAGMA temp_store=MEMORY")
            
            # Execute schema statements one at a time (SQLite limitation)
            for stmt in SQLITE_SCHEMA.strip().split(";"):
                stmt = stmt.strip()
                if stmt:
                    try:
                        await db.execute(stmt)
                    except Exception as e:
                        # Ignore "already exists" on virtual tables
                        if "already exists" not in str(e).lower():
                            print(f"Schema warning: {e}")

            # ─── Auto-migration: add any missing columns to existing tables ────
            EXPECTED_COLUMNS = {
                "articles": [
                    ("title_hash", "TEXT"),
                    ("sentiment", "TEXT"),
                    ("tags", "TEXT"),
                    ("summary", "TEXT"),
                ],
            }
            for table, columns in EXPECTED_COLUMNS.items():
                async with db.execute(f"PRAGMA table_info({table})") as cursor:
                    existing = {row[1] for row in await cursor.fetchall()}
                for col_name, col_type in columns:
                    if col_name not in existing:
                        try:
                            await db.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
                            print(f"Migration: added column '{col_name}' to '{table}'")
                        except Exception as e:
                            if "duplicate column" not in str(e).lower():
                                print(f"Migration warning: {e}")

            await db.commit()
    else:
        global _pg_pool
        if _pg_pool is None:
            _pg_pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=20)
        async with _pg_pool.acquire() as conn:
            await conn.execute(POSTGRES_SCHEMA)
    print(f"Database initialized ({'SQLite+WAL+FTS' if DATABASE_URL.startswith('sqlite') else 'PostgreSQL'})")



# ─── Connection Abstraction Layer ──────────────────────────────────────────────

class DBConnection:
    def __init__(self, conn):
        self.conn = conn
        self.is_sqlite = DATABASE_URL.startswith("sqlite")

    def _normalize(self, query: str) -> str:
        """Convert $1,$2 placeholders to ? for SQLite. Also ILIKE -> LIKE."""
        if self.is_sqlite:
            query = re.sub(r'\$\d+', '?', query)
            query = query.replace("ILIKE", "LIKE")
        return query

    async def execute(self, query: str, *args):
        query = self._normalize(query)
        if self.is_sqlite:
            await self.conn.execute(query, args)
            await self.conn.commit()
        else:
            await self.conn.execute(query, *args)

    async def fetch(self, query: str, *args) -> List[dict]:
        query = self._normalize(query)
        if self.is_sqlite:
            async with self.conn.execute(query, args) as cursor:
                rows = await cursor.fetchall()
                if not rows: return []
                cols = [d[0] for d in cursor.description]
                return [dict(zip(cols, row)) for row in rows]
        else:
            rows = await self.conn.fetch(query, *args)
            return [dict(r) for r in rows]

    async def fetchrow(self, query: str, *args) -> Optional[dict]:
        query = self._normalize(query)
        if self.is_sqlite:
            async with self.conn.execute(query, args) as cursor:
                row = await cursor.fetchone()
                if not row: return None
                cols = [d[0] for d in cursor.description]
                return dict(zip(cols, row))
        else:
            row = await self.conn.fetchrow(query, *args)
            return dict(row) if row else None

    async def fetchval(self, query: str, *args) -> Any:
        query = self._normalize(query)
        if self.is_sqlite:
            async with self.conn.execute(query, args) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None
        else:
            return await self.conn.fetchval(query, *args)


@asynccontextmanager
async def get_db():
    if DATABASE_URL.startswith("sqlite"):
        db_path = DATABASE_URL.replace("sqlite:///", "")
        async with aiosqlite.connect(db_path) as conn:
            # Ensure WAL is on for every connection
            await conn.execute("PRAGMA journal_mode=WAL")
            await conn.execute("PRAGMA synchronous=NORMAL")
            yield DBConnection(conn)
    else:
        global _pg_pool
        if _pg_pool is None:
            _pg_pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=20)
        async with _pg_pool.acquire() as conn:
            yield DBConnection(conn)
