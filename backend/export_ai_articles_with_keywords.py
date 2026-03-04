import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import os
import re

# Paths
DB_PATH = os.path.abspath('news_scraper.db')
OUTPUT_XLSX = os.path.abspath('ai_articles_last3months_india.xlsx')

# Keywords (AI terms only, as requested)
AI_TERMS = [
    "ai",
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "neural network",
    "foundation model",
    "large language model",
    "llm",
    "generative ai",
    "genai",
    "multimodal ai",
    "computer vision",
    "natural language processing",
    "on-device ai",
    "on device ai",
    "edge ai",
    "local inference",
    "offline ai",
    "ai accelerator",
    "inference accelerator",
    "neural processing unit",
    "npu",
    "tops",
    "ai assistant",
    "ai agent",
    "agentic ai",
    "copilot",
    "copilot+",
    "chatgpt",
    "gemini",
    "apple intelligence",
    "galaxy ai",
]

# Date 3 months ago (approx 90 days)
three_months_ago = (datetime.utcnow() - timedelta(days=90)).strftime('%Y-%m-%d')

# Build an FTS query that OR‑joins all AI terms for SQLite FTS5
fts_query = ' OR '.join([f'"{kw}"' for kw in AI_TERMS])

# SQLite DB Path (ensure absolute)
if not os.path.exists(DB_PATH):
    raise FileNotFoundError(f"Database not found at {DB_PATH}")

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Optimized FTS query
query = """
SELECT a.title, a.url, a.full_body, a.author, a.agency, a.published_at, 
       a.sector, a.region, a.word_count, a.summary, a.title_hash, a.scraped_at, a.scrape_job_id
FROM articles a
JOIN articles_fts ON articles_fts.rowid = a.id
WHERE a.sector = 'artificial intelligence'
  AND a.region = 'india'
  AND date(a.published_at) >= date(?)
  AND articles_fts MATCH ?
"""

print(f"Searching for articles matching keywords using FTS5...")
rows = cur.execute(query, (three_months_ago, fts_query)).fetchall()
print(f"Found {len(rows)} matching articles")

# Convert to DataFrame
df = pd.DataFrame([dict(r) for r in rows])

# Export to Excel
if not df.empty:
    df.to_excel(OUTPUT_XLSX, index=False)
    print(f"Exported to {OUTPUT_XLSX}")
else:
    print("No articles found matching the criteria.")

conn.close()
